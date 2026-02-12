# scripts/services/view_service.py
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from typing import Any, Dict, List, Optional, Tuple

from src.modules.db_connection import DatabaseConnection


def format_player(
    first_name: Optional[str],
    last_name: Optional[str],
    seed_number: Optional[int],
    is_bye: bool,
) -> str:
    """
    Player display formatting.

    Rules:
    - If a slot is empty (no player_id), render as "Bye".
    - If a name is missing for any other reason, render as "TBD".
    - If seeded, render as: "Name (1)"
    """
    if is_bye:
        return "Bye"

    name = " ".join([p for p in [first_name, last_name] if p]).strip()
    if not name:
        return "TBD"

    if seed_number is None:
        return name

    return f"{name} ({seed_number})"


def _format_set(g1: Optional[int], g2: Optional[int], tb1: Optional[int], tb2: Optional[int]) -> Optional[str]:
    """
    Format one set as:
      6-3
      7-6(5)   (loser TB points in parentheses)
    """
    if g1 is None or g2 is None:
        return None

    s = f"{g1}-{g2}"

    # Tie-break display: 7-6(5) where (5) is the loser tie-break points
    if (g1, g2) in [(7, 6), (6, 7)] and tb1 is not None and tb2 is not None:
        loser_tb = tb2 if g1 > g2 else tb1
        s = f"{s}({loser_tb})"

    return s


def format_score(match_row: Dict[str, Any]) -> str:
    """
    Compact score formatting:
      6-3 7-6(5)
      6-7(5) 7-6(3) [10-8]
    """
    set1 = _format_set(
        match_row.get("set1_player1"), match_row.get("set1_player2"),
        match_row.get("set1_tiebreak_player1"), match_row.get("set1_tiebreak_player2")
    )
    set2 = _format_set(
        match_row.get("set2_player1"), match_row.get("set2_player2"),
        match_row.get("set2_tiebreak_player1"), match_row.get("set2_tiebreak_player2")
    )
    set3 = _format_set(
        match_row.get("set3_player1"), match_row.get("set3_player2"),
        match_row.get("set3_tiebreak_player1"), match_row.get("set3_tiebreak_player2")
    )

    stb1 = match_row.get("set3_supertiebreak_player1")
    stb2 = match_row.get("set3_supertiebreak_player2")
    stb = f"[{stb1}-{stb2}]" if stb1 is not None and stb2 is not None else None

    parts = [p for p in [set1, set2, set3, stb] if p]
    return " ".join(parts)


def format_score_for_winner(match_row: Dict[str, Any]) -> str:
    """Format score from winner's perspective."""
    winner_id = match_row.get("winner_id")
    p2_id = match_row.get("player2_id")
    if winner_id and p2_id and int(winner_id) == int(p2_id):
        swapped = dict(match_row)
        for s in ("set1", "set2", "set3"):
            swapped[f"{s}_player1"], swapped[f"{s}_player2"] = match_row.get(f"{s}_player2"), match_row.get(f"{s}_player1")
            swapped[f"{s}_tiebreak_player1"], swapped[f"{s}_tiebreak_player2"] = match_row.get(f"{s}_tiebreak_player2"), match_row.get(f"{s}_tiebreak_player1")
        swapped["set3_supertiebreak_player1"], swapped["set3_supertiebreak_player2"] = match_row.get("set3_supertiebreak_player2"), match_row.get("set3_supertiebreak_player1")
        return format_score(swapped)
    return format_score(match_row)


def _draw_size_from_num_players(num_players: int) -> int:
    if num_players <= 8:
        return 8
    if num_players <= 16:
        return 16
    if num_players <= 32:
        return 32
    return 64


def _starting_round_id(draw_size: int) -> int:
    # MatchRounds in load_itf_data.sql:
    # 1=R64, 2=R32, 3=R16, 4=QF, 5=SF, 6=F
    return {8: 4, 16: 3, 32: 2, 64: 1}.get(draw_size, 1)


def _round_sort_key(round_code: str) -> int:
    # Bracket-style pages: Final at top.
    return {
        "F": 1,
        "SF": 2,
        "QF": 3,
        "R16": 4,
        "R32": 5,
        "R64": 6,
    }.get(round_code, 99)


def _pairings_for_draw_size_8() -> List[Tuple[int, int]]:
    """
    Standard 8-slot bracket pairing by draw_position:
      1 vs 8
      4 vs 5
      3 vs 6
      2 vs 7
    """
    return [(1, 8), (4, 5), (3, 6), (2, 7)]


def get_draw_matches(draw_id: int) -> List[Dict[str, Any]]:
    """
    Returns rows ready for draw rendering.

    Fixes:
    - Avoid duplicated "Bye" by not also forcing match_status_description="Bye" when a slot is Bye.
    - For small draws (<=8 players), render a full QF/SF/F skeleton even when Matches contains
      only partial/legacy rows (e.g. stored as R64/R32/R16).
    """
    db = DatabaseConnection()
    if not db.connect():
        raise RuntimeError("Database connection failed")

    # Draw context
    draw_row = db.query_params(
        """
        SELECT draw_id, num_players
        FROM Draws
        WHERE draw_id = %s
        """,
        (draw_id,),
    )
    if not draw_row:
        db.disconnect()
        return []

    num_players = int(draw_row[0]["num_players"])
    draw_size = _draw_size_from_num_players(num_players)
    start_round_id = _starting_round_id(draw_size)

    # DrawPlayers map
    dps = db.query_params(
        """
        SELECT draw_id, player_id, draw_position
        FROM DrawPlayers
        WHERE draw_id = %s
        """,
        (draw_id,),
    )
    pos_to_player_id: Dict[int, int] = {int(r["draw_position"]): int(r["player_id"]) for r in dps}

    # Recorded matches (whatever exists in DB)
    sql_matches = """
        SELECT
            m.match_id,
            m.draw_id,
            mr.code AS round_code,
            mr.label AS round_label,
            m.round_id,
            m.match_number,
            m.match_date,

            m.match_status_id,
            ms.code AS match_status_code,
            ms.description AS match_status_description,

            m.player1_id,
            p1.first_name AS p1_first_name,
            p1.last_name  AS p1_last_name,
            ds1.seed_number AS p1_seed,

            m.player2_id,
            p2.first_name AS p2_first_name,
            p2.last_name  AS p2_last_name,
            ds2.seed_number AS p2_seed,

            m.winner_id,

            m.set1_player1, m.set1_player2, m.set1_tiebreak_player1, m.set1_tiebreak_player2,
            m.set2_player1, m.set2_player2, m.set2_tiebreak_player1, m.set2_tiebreak_player2,
            m.set3_player1, m.set3_player2, m.set3_tiebreak_player1, m.set3_tiebreak_player2,
            m.set3_supertiebreak_player1, m.set3_supertiebreak_player2
        FROM Matches m
        JOIN MatchRounds mr
            ON mr.round_id = m.round_id
        JOIN MatchStatus ms
            ON ms.match_status_id = m.match_status_id
        LEFT JOIN Players p1
            ON p1.player_id = m.player1_id
        LEFT JOIN Players p2
            ON p2.player_id = m.player2_id
        LEFT JOIN DrawSeed ds1
            ON ds1.draw_id = m.draw_id AND ds1.player_id = m.player1_id
        LEFT JOIN DrawSeed ds2
            ON ds2.draw_id = m.draw_id AND ds2.player_id = m.player2_id
        WHERE m.draw_id = %s
    """
    recorded = db.query_params(sql_matches, (draw_id,))

    # Small-draw skeleton mode (currently required to fix draw 208 behaviour)
    if draw_size == 8:
        # Build QF (4), SF (5), F (6) skeletons
        rounds = [
            {"round_id": 4, "round_code": "QF", "round_label": "Quarter-Final", "match_count": 4},
            {"round_id": 5, "round_code": "SF", "round_label": "Semi-Final", "match_count": 2},
            {"round_id": 6, "round_code": "F",  "round_label": "Final",         "match_count": 1},
        ]

        # Index recorded matches by (round_id, match_number) first
        rec_by_key: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for r in recorded:
            rid = int(r.get("round_id"))
            mn = int(r.get("match_number"))
            rec_by_key[(rid, mn)] = r

        # Detect legacy “small draw saved as R64/R32/R16” pattern:
        # start_round_id=4 expected, but recorded rounds are <4 and count looks like a winner path.
        legacy_small_draw = (
            len(recorded) in (1, 2, 3)
            and any(int(r.get("round_id")) < start_round_id for r in recorded)
        )

        legacy_chain: List[Dict[str, Any]] = []
        if legacy_small_draw:
            # Remap in date order onto QF -> SF -> F
            legacy_chain = sorted(recorded, key=lambda x: (x.get("match_date") or "", int(x.get("match_number") or 0)))

        # QF pairing by draw_position for display
        qf_pairs = _pairings_for_draw_size_8()

        out: List[Dict[str, Any]] = []
        legacy_i = 0

        match_id_virtual = 0  # virtual ID for skeleton rows that do not exist in DB

        for rnd in rounds:
            rid = int(rnd["round_id"])
            rcode = rnd["round_code"]
            rlabel = rnd["round_label"]
            mcount = int(rnd["match_count"])

            for mn in range(1, mcount + 1):
                base: Dict[str, Any] = {
                    "match_id": None,
                    "draw_id": draw_id,
                    "round_code": rcode,
                    "round_label": rlabel,
                    "round_id": rid,
                    "match_number": mn,
                    "match_date": None,

                    "match_status_id": 1,
                    "match_status_code": "SCHED",
                    "match_status_description": "Scheduled",

                    "player1_id": None,
                    "p1_first_name": None,
                    "p1_last_name": None,
                    "p1_seed": None,

                    "player2_id": None,
                    "p2_first_name": None,
                    "p2_last_name": None,
                    "p2_seed": None,

                    "winner_id": None,

                    "set1_player1": None, "set1_player2": None, "set1_tiebreak_player1": None, "set1_tiebreak_player2": None,
                    "set2_player1": None, "set2_player2": None, "set2_tiebreak_player1": None, "set2_tiebreak_player2": None,
                    "set3_player1": None, "set3_player2": None, "set3_tiebreak_player1": None, "set3_tiebreak_player2": None,
                    "set3_supertiebreak_player1": None, "set3_supertiebreak_player2": None,
                }

                # Fill QF slots from DrawPlayers
                if rcode == "QF":
                    a_pos, b_pos = qf_pairs[mn - 1]
                    base["player1_id"] = pos_to_player_id.get(a_pos)
                    base["player2_id"] = pos_to_player_id.get(b_pos)

                # Use recorded match if present (correctly keyed)
                rec = rec_by_key.get((rid, mn))
                if rec:
                    base.update(rec)

                # Legacy remap: assign recorded chain onto QF/SF/F sequentially
                if legacy_small_draw and rec is None and legacy_i < len(legacy_chain):
                    if (rcode == "QF" and legacy_i == 0) or (rcode == "SF" and legacy_i == 1) or (rcode == "F" and legacy_i == 2):
                        base.update(legacy_chain[legacy_i])
                        base["round_id"] = rid
                        base["round_code"] = rcode
                        base["round_label"] = rlabel
                        base["match_number"] = mn
                        legacy_i += 1

                # Compute display lines + bye handling
                p1_is_bye = base.get("player1_id") is None
                p2_is_bye = base.get("player2_id") is None
                is_bye_match = p1_is_bye or p2_is_bye

                base["player1_display"] = format_player(base.get("p1_first_name"), base.get("p1_last_name"), base.get("p1_seed"), p1_is_bye)
                base["player2_display"] = format_player(base.get("p2_first_name"), base.get("p2_last_name"), base.get("p2_seed"), p2_is_bye)

                if is_bye_match:
                    # Prevent duplicated "Bye" (slot already shows Bye)
                    base["match_status_code"] = "BYE"
                    base["match_status_description"] = ""
                    base["score_display"] = ""
                else:
                    base["score_display"] = format_score_for_winner(base)

                if base.get("match_id") is None:
                    match_id_virtual += 1
                    base["match_id"] = -match_id_virtual  # negative IDs to avoid clashing with DB IDs

                out.append(base)

        # Sort like the existing bracket view
        out.sort(key=lambda r: (_round_sort_key(r.get("round_code") or ""), int(r.get("match_number") or 0)))

        db.disconnect()
        return out

    # Default behaviour (non-8 draw): keep the existing DB-driven view
    db.disconnect()

    # Post-processing (existing logic, with “Bye duplication” fix)
    for r in recorded:
        p1_is_bye = r.get("player1_id") is None
        p2_is_bye = r.get("player2_id") is None
        is_bye_match = p1_is_bye or p2_is_bye

        r["player1_display"] = format_player(r.get("p1_first_name"), r.get("p1_last_name"), r.get("p1_seed"), p1_is_bye)
        r["player2_display"] = format_player(r.get("p2_first_name"), r.get("p2_last_name"), r.get("p2_seed"), p2_is_bye)

        if is_bye_match:
            r["match_status_code"] = "BYE"
            r["match_status_description"] = ""
            r["score_display"] = ""
        else:
            r["score_display"] = format_score_for_winner(r)

    recorded.sort(key=lambda r: (_round_sort_key(r.get("round_code") or ""), int(r.get("match_number") or 0)))
    return recorded
