#!/usr/bin/env python3
"""
Apply disciplinary sanctions
======================================

Implements:

1) Late withdrawal AFTER_DRAW:
   - Record WO on first scheduled match (Matches.match_status_id = 3)
   - Insert 2-month suspension (PlayerSuspensions.reason_match_status_id = 3)
   - Set Players.status_id = 4

2) Disqualification (backfill safety):
   - For Matches.match_status_id = 6, ensure 6-month suspension exists
   - Set Players.status_id = 4
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from typing import Optional, Tuple, List, Dict

from src.modules.db_connection import DatabaseConnection
from scripts.services.match_service import apply_result_and_advance, ResultPayload


LATE_WITHDRAWAL_TYPE = "AFTER_DRAW"
MATCH_STATUS_WO = 3
MATCH_STATUS_DQ = 6
PLAYER_STATUS_SUSPENDED = 4


def _resolve_draw_id(cur, tournament_id: int, age_category_id: int, gender_id: int) -> Optional[int]:
    cur.execute(
        """
        SELECT draw_id
        FROM Draws
        WHERE tournament_id = %s
          AND age_category_id = %s
          AND gender_id = %s
        """,
        (tournament_id, age_category_id, gender_id),
    )
    row = cur.fetchone()
    return row["draw_id"] if row else None


def _resolve_first_match_for_player(cur, draw_id: int, player_id: int) -> Optional[Dict]:
    # First scheduled match = earliest round where the player appears
    cur.execute(
        """
        SELECT *
        FROM Matches
        WHERE draw_id = %s
          AND (player1_id = %s OR player2_id = %s)
        ORDER BY round_id ASC, match_number ASC
        LIMIT 1
        """,
        (draw_id, player_id, player_id),
    )
    row = cur.fetchone()
    return row


def _resolve_opponent_id(match_row: Dict, player_id: int) -> Optional[int]:
    p1 = match_row.get("player1_id")
    p2 = match_row.get("player2_id")
    if p1 == player_id:
        return p2
    if p2 == player_id:
        return p1
    return None


def _ensure_suspension(
    cur,
    player_id: int,
    tournament_id: int,
    reason_match_status_id: int,
    months: int,
    suspension_start,
) -> None:
    # Idempotency: do nothing if the same suspension already exists
    cur.execute(
        """
        SELECT 1
        FROM PlayerSuspensions
        WHERE player_id = %s
          AND tournament_id = %s
          AND reason_match_status_id = %s
        """,
        (player_id, tournament_id, reason_match_status_id),
    )
    if cur.fetchone() is not None:
        return

    # suspension_start MUST be match_date (date portion) for DB-path parity with file-based generation
    cur.execute(
        """
        INSERT INTO PlayerSuspensions (
            suspension_id,
            player_id,
            tournament_id,
            reason_match_status_id,
            suspension_start,
            suspension_end
        )
        SELECT
            COALESCE(MAX(suspension_id), 0) + 1,
            %s,
            %s,
            %s,
            %s::date,
            (%s::date + (%s || ' months')::interval)::date
        FROM PlayerSuspensions
        """,
        (player_id, tournament_id, reason_match_status_id, suspension_start, suspension_start, months),
    )

    # Mark player suspended
    cur.execute(
        """
        UPDATE Players
        SET status_id = %s
        WHERE player_id = %s
        """,
        (PLAYER_STATUS_SUSPENDED, player_id),
    )


def apply_late_withdrawal_sanctions(db: DatabaseConnection) -> int:
    """
    Returns count of processed late-withdrawal entries.
    """
    processed = 0

    with db.connection.cursor() as cur:
        cur.execute(
            """
            SELECT entry_id, player_id, tournament_id, age_category_id, gender_id
            FROM Entries
            WHERE withdrawal_type = %s
              AND withdrawn_at IS NOT NULL
            ORDER BY tournament_id, entry_id
            """,
            (LATE_WITHDRAWAL_TYPE,),
        )
        entries = cur.fetchall()

    for e in entries:
        entry_id = e["entry_id"]
        player_id = e["player_id"]
        tournament_id = e["tournament_id"]
        age_category_id = e["age_category_id"]
        gender_id = e["gender_id"]

        with db.connection.cursor() as cur:
            # Skip if a WO-based suspension already exists for this entry’s tournament
            cur.execute(
                """
                SELECT 1
                FROM PlayerSuspensions
                WHERE player_id = %s
                  AND tournament_id = %s
                  AND reason_match_status_id = %s
                """,
                (player_id, tournament_id, MATCH_STATUS_WO),
            )
            already = cur.fetchone() is not None
            if already:
                continue

            draw_id = _resolve_draw_id(cur, tournament_id, age_category_id, gender_id)
            if draw_id is None:
                # No draw found for that tournament/category/gender
                continue

            match_row = _resolve_first_match_for_player(cur, draw_id, player_id)
            if match_row is None:
                # No match row found (draw not generated or player not placed)
                continue

            opponent_id = _resolve_opponent_id(match_row, player_id)
            if opponent_id is None:
                # Cannot apply WO without opponent
                continue

            # Apply WO using existing match propagation logic
            payload = ResultPayload(
                match_id=match_row["match_id"],
                match_status_id=MATCH_STATUS_WO,
                winner_id=opponent_id,
            )
            apply_result_and_advance(draw_id, payload)

            # Apply 2-month suspension + suspended status
            _ensure_suspension(
                cur,
                player_id,
                tournament_id,
                MATCH_STATUS_WO,
                months=2,
                suspension_start=match_row["match_date"],
            )

            db.connection.commit()
            processed += 1

    return processed


def backfill_disqualification_sanctions(db: DatabaseConnection) -> int:
    """
    Returns count of DQ matches that resulted in a newly inserted suspension.
    """
    inserted = 0

    with db.connection.cursor() as cur:
        cur.execute(
            """
            SELECT m.match_id, m.draw_id, m.player1_id, m.player2_id, m.winner_id, m.match_date
            FROM Matches m
            WHERE m.match_status_id = %s
            ORDER BY m.match_id
            """,
            (MATCH_STATUS_DQ,),
        )
        dq_matches = cur.fetchall()

    for m in dq_matches:
        p1 = m["player1_id"]
        p2 = m["player2_id"]
        w = m["winner_id"]
        md = m["match_date"]

        # DQ implies a started match: player1_id, player2_id, winner_id, match_date must be present
        if p1 is None or p2 is None or w is None or md is None:
            continue

        # winner_id must be one of the match players to infer the DQ player
        if w not in (p1, p2):
            continue

        dq_player_id = p2 if w == p1 else p1

        with db.connection.cursor() as cur:
            # Resolve tournament_id from draw
            cur.execute(
                """
                SELECT tournament_id
                FROM Draws
                WHERE draw_id = %s
                """,
                (m["draw_id"],),
            )
            row = cur.fetchone()
            if row is None:
                continue
            tournament_id = row["tournament_id"]

            # Check whether the DQ suspension already exists
            cur.execute(
                """
                SELECT 1
                FROM PlayerSuspensions
                WHERE player_id = %s
                  AND tournament_id = %s
                  AND reason_match_status_id = %s
                """,
                (dq_player_id, tournament_id, MATCH_STATUS_DQ),
            )
            exists = cur.fetchone() is not None
            if exists:
                continue

            _ensure_suspension(
                cur,
                dq_player_id,
                tournament_id,
                MATCH_STATUS_DQ,
                months=6,
                suspension_start=md,
            )
            db.connection.commit()
            inserted += 1

    return inserted


def main() -> None:
    db = DatabaseConnection()
    if not db.connect():
        raise RuntimeError("Database connection failed")

    try:
        lw = apply_late_withdrawal_sanctions(db)
        dq = backfill_disqualification_sanctions(db)
        print(f"LateWithdrawalProcessed={lw}")
        print(f"DisqualificationBackfilled={dq}")
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
