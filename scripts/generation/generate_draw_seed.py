#!/usr/bin/env python3
"""
generate_draw_seed.py

Populate DrawSeed for one or more draws.

Authoritative sources:
- create_itf_schema.sql (DrawSeed columns + PK)
- Rules.md (seeding rules + is_actual_seeding semantics)

Planned seeding:
- is_actual_seeding = FALSE
- Based on DrawPlayers.entry_points (descending), tie-break DrawPlayers.entry_timestamp (ascending)
- tournament_id 1 and 2 must have NO SEEDING (no DrawSeed rows)

Actual seeding:
- is_actual_seeding = TRUE
- Optional mode (--actual) intended for post-withdrawal substitutions
  (Rules.md: only matters between Tuesday 10:00 UTC and Friday 19:00 UTC)

Safety:
- Never assumes column names beyond those in create_itf_schema.sql.
- Will refuse to run if required tables/columns are missing.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from db_connection import DatabaseConnection


# ----------------------------
# Data helpers
# ----------------------------

@dataclass(frozen=True)
class SeedingRule:
    min_players: int
    max_players: int
    num_seeds: int


REQUIRED_DRAWSEED_COLUMNS = {
    "draw_id",
    "player_id",
    "seed_number",
    "seeding_points",
    "is_actual_seeding",
}


def _fetch_table_columns(db: DatabaseConnection, table_name: str) -> List[str]:
    rows = db.query_params(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name.lower(),),
    )
    return [r["column_name"] for r in rows]


def _assert_columns(db: DatabaseConnection, table_name: str, required: Sequence[str]) -> None:
    cols = set(_fetch_table_columns(db, table_name))
    missing = [c for c in required if c not in cols]
    if missing:
        raise RuntimeError(
            f"Schema mismatch: table '{table_name}' missing columns: {missing}. "
            f"Existing columns: {sorted(cols)}"
        )


def _load_seeding_rules(db: DatabaseConnection) -> List[SeedingRule]:
    _assert_columns(db, "SeedingRules", ["min_players", "max_players", "num_seeds"])
    rows = db.query("SELECT min_players, max_players, num_seeds FROM SeedingRules ORDER BY min_players, max_players")
    rules: List[SeedingRule] = []
    for r in rows:
        rules.append(
            SeedingRule(
                min_players=int(r["min_players"]),
                max_players=int(r["max_players"]),
                num_seeds=int(r["num_seeds"]),
            )
        )
    if not rules:
        raise RuntimeError("SeedingRules is empty; cannot determine number of seeds.")
    return rules


def _get_num_seeds(num_entries: int, rules: List[SeedingRule]) -> int:
    for rule in rules:
        if rule.min_players <= num_entries <= rule.max_players:
            return rule.num_seeds
    raise RuntimeError(f"No SeedingRules row matches num_entries={num_entries}.")


def _draw_ids_to_process(db: DatabaseConnection, draw_id: Optional[int]) -> List[int]:
    if draw_id is not None:
        return [draw_id]

    # Only draws that already have DrawPlayers (otherwise seeding cannot be determined)
    _assert_columns(db, "DrawPlayers", ["draw_id"])
    rows = db.query("SELECT DISTINCT draw_id FROM DrawPlayers ORDER BY draw_id")
    return [int(r["draw_id"]) for r in rows]


def _tournament_id_for_draw(db: DatabaseConnection, draw_id: int) -> int:
    _assert_columns(db, "Draws", ["draw_id", "tournament_id"])
    rows = db.query_params("SELECT tournament_id FROM Draws WHERE draw_id = %s", (draw_id,))
    if not rows:
        raise RuntimeError(f"Draw {draw_id} not found in Draws.")
    return int(rows[0]["tournament_id"])


def _seeded_players_for_draw(db: DatabaseConnection, draw_id: int, num_seeds: int) -> List[Tuple[int, int]]:
    """
    Returns list of (player_id, seeding_points) for seeds 1..num_seeds.
    seeding_points comes from DrawPlayers.entry_points.
    """
    _assert_columns(db, "DrawPlayers", ["draw_id", "player_id", "entry_points", "entry_timestamp"])

    rows = db.query_params(
        """
        SELECT player_id, entry_points, entry_timestamp
        FROM DrawPlayers
        WHERE draw_id = %s
        """,
        (draw_id,),
    )
    if not rows:
        raise RuntimeError(f"No DrawPlayers rows found for draw_id={draw_id}.")

    # Validate required fields exist and are usable
    parsed: List[Tuple[int, int, str]] = []
    for r in rows:
        if r.get("entry_points") is None:
            raise RuntimeError(f"DrawPlayers.entry_points is NULL for draw_id={draw_id}, player_id={r.get('player_id')}.")
        if r.get("entry_timestamp") is None:
            raise RuntimeError(f"DrawPlayers.entry_timestamp is NULL for draw_id={draw_id}, player_id={r.get('player_id')}.")
        parsed.append((int(r["player_id"]), int(r["entry_points"]), str(r["entry_timestamp"])))

    # Sort: points desc, timestamp asc
    parsed.sort(key=lambda x: (-x[1], x[2]))

    if num_seeds <= 0:
        return []

    top = parsed[:num_seeds]
    return [(player_id, points) for (player_id, points, _ts) in top]


def _delete_existing_seed_rows(
    db: DatabaseConnection,
    draw_id: int,
    is_actual: bool,
    overwrite: bool,
) -> int:
    """
    Deletes:
    - if overwrite=True: delete DrawSeed rows for draw_id matching is_actual flag
    - if overwrite=False: delete nothing
    """
    if not overwrite:
        return 0

    _assert_columns(db, "DrawSeed", list(REQUIRED_DRAWSEED_COLUMNS))

    with db.connection.cursor() as cur:
        cur.execute(
            """
            DELETE FROM DrawSeed
            WHERE draw_id = %s AND is_actual_seeding = %s
            """,
            (draw_id, is_actual),
        )
        return int(cur.rowcount)


def _planned_rows_exist(db: DatabaseConnection, draw_id: int) -> bool:
    _assert_columns(db, "DrawSeed", list(REQUIRED_DRAWSEED_COLUMNS))
    rows = db.query_params(
        """
        SELECT 1
        FROM DrawSeed
        WHERE draw_id = %s AND is_actual_seeding = FALSE
        LIMIT 1
        """,
        (draw_id,),
    )
    return bool(rows)


def _insert_drawseed_rows(
    db: DatabaseConnection,
    draw_id: int,
    seeded_players: List[Tuple[int, int]],
    is_actual: bool,
) -> int:
    """
    Insert DrawSeed rows for seeds 1..N.
    """
    if not seeded_players:
        return 0

    _assert_columns(db, "DrawSeed", list(REQUIRED_DRAWSEED_COLUMNS))

    with db.connection.cursor() as cur:
        inserted = 0
        for idx, (player_id, points) in enumerate(seeded_players, start=1):
            cur.execute(
                """
                INSERT INTO DrawSeed
                  (draw_id, player_id, seed_number, seeding_points, is_actual_seeding)
                VALUES
                  (%s, %s, %s, %s, %s)
                ON CONFLICT (draw_id, player_id) DO UPDATE
                  SET seed_number = EXCLUDED.seed_number,
                      seeding_points = EXCLUDED.seeding_points,
                      is_actual_seeding = EXCLUDED.is_actual_seeding
                """,
                (draw_id, player_id, idx, points, is_actual),
            )
            inserted += 1
        return inserted


def generate_draw_seed(
    draw_id: int,
    overwrite: bool,
    is_actual: bool,
    skip_if_planned_exists: bool,
) -> Dict[str, int]:
    db = DatabaseConnection()
    if not db.connect():
        raise RuntimeError("Database connection failed.")

    try:
        # Hard schema checks (fail fast)
        _assert_columns(db, "DrawSeed", list(REQUIRED_DRAWSEED_COLUMNS))
        _assert_columns(db, "Draws", ["draw_id", "tournament_id"])
        _assert_columns(db, "DrawPlayers", ["draw_id", "player_id", "entry_points", "entry_timestamp"])
        rules = _load_seeding_rules(db)

        tournament_id = _tournament_id_for_draw(db, draw_id)

        # Rules.md: tournaments 1 and 2 have NO SEEDING
        if tournament_id in (1, 2):
            return {
                "draw_id": draw_id,
                "tournament_id": tournament_id,
                "deleted": 0,
                "inserted": 0,
                "skipped_no_seeding_rule": 1,
                "skipped_planned_exists": 0,
            }

        if (not is_actual) and skip_if_planned_exists and _planned_rows_exist(db, draw_id):
            return {
                "draw_id": draw_id,
                "tournament_id": tournament_id,
                "deleted": 0,
                "inserted": 0,
                "skipped_no_seeding_rule": 0,
                "skipped_planned_exists": 1,
            }

        # Determine number of seeds from SeedingRules using number of entries (= DrawPlayers count)
        num_entries_rows = db.query_params("SELECT COUNT(*) AS c FROM DrawPlayers WHERE draw_id = %s", (draw_id,))
        num_entries = int(num_entries_rows[0]["c"]) if num_entries_rows else 0
        if num_entries < 6 or num_entries > 64:
            raise RuntimeError(f"Invalid num_entries for draw_id={draw_id}: {num_entries} (expected 6..64).")

        num_seeds = _get_num_seeds(num_entries, rules)

        # Planned/actual seeding rows
        seeded = _seeded_players_for_draw(db, draw_id, num_seeds)

        deleted = _delete_existing_seed_rows(db, draw_id, is_actual=is_actual, overwrite=overwrite)
        inserted = _insert_drawseed_rows(db, draw_id, seeded, is_actual=is_actual)

        db.connection.commit()

        return {
            "draw_id": draw_id,
            "tournament_id": tournament_id,
            "deleted": deleted,
            "inserted": inserted,
            "skipped_no_seeding_rule": 0,
            "skipped_planned_exists": 0,
        }

    except Exception:
        try:
            db.connection.rollback()
        except Exception:
            pass
        raise
    finally:
        db.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DrawSeed rows from DrawPlayers and SeedingRules.")
    parser.add_argument("--draw-id", type=int, default=None, help="Process a single draw_id. Default: all draws with DrawPlayers.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing rows for the selected is_actual_seeding flag.")
    parser.add_argument("--actual", action="store_true", help="Generate actual seeding (is_actual_seeding=TRUE). Default: planned seeding (FALSE).")
    parser.add_argument(
        "--skip-if-planned-exists",
        action="store_true",
        help="Planned mode only: if planned seeding exists, skip that draw instead of updating.",
    )
    args = parser.parse_args()

    db = DatabaseConnection()
    if not db.connect():
        raise RuntimeError("Database connection failed.")
    try:
        draw_ids = _draw_ids_to_process(db, args.draw_id)
    finally:
        db.disconnect()

    total_deleted = 0
    total_inserted = 0
    skipped_no_seeding = 0
    skipped_planned = 0

    mode_label = "ACTUAL" if args.actual else "PLANNED"
    print(f"Generating DrawSeed ({mode_label}) for {len(draw_ids)} draw(s).")

    for did in draw_ids:
        result = generate_draw_seed(
            draw_id=did,
            overwrite=args.overwrite,
            is_actual=args.actual,
            skip_if_planned_exists=args.skip_if_planned_exists,
        )
        total_deleted += result["deleted"]
        total_inserted += result["inserted"]
        skipped_no_seeding += result["skipped_no_seeding_rule"]
        skipped_planned += result["skipped_planned_exists"]

        print(
            f"draw_id={result['draw_id']} tournament_id={result['tournament_id']} "
            f"deleted={result['deleted']} inserted={result['inserted']} "
            f"skipped_no_seeding={result['skipped_no_seeding_rule']} skipped_planned_exists={result['skipped_planned_exists']}"
        )

    print(
        f"Done. deleted={total_deleted} inserted={total_inserted} "
        f"skipped_no_seeding={skipped_no_seeding} skipped_planned_exists={skipped_planned}"
    )


if __name__ == "__main__":
    main()
