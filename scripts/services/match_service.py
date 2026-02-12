#!/usr/bin/env python3
"""
Match service (production workflow)
===================================

Purpose:
- Create bracket skeleton matches (no results) from DrawPlayers.
- Apply a result (validated) and propagate the winner to the next round.

Key rule:
- A BYE is a missing bracket slot (no DrawPlayers row for that draw_position).
- The flag DrawPlayers.has_bye means "this player receives a bye in the first round",
  not "this player is a Bye placeholder".
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from dataclasses import dataclass
from datetime import date
from typing import Dict, Any, Optional

from src.modules.db_connection import DatabaseConnection
from scripts.validation.validate_tennis_matches import TennisMatchValidator


class MatchServiceError(RuntimeError):
    pass


def _draw_size_from_num_entries(num_entries: int) -> int:
    if num_entries <= 8:
        return 8
    if num_entries <= 16:
        return 16
    if num_entries <= 32:
        return 32
    return 64


def _starting_round_id(draw_size: int) -> int:
    # 8 -> QF, 16 -> R16, 32 -> R32, 64 -> R64
    return {8: 4, 16: 3, 32: 2, 64: 1}.get(draw_size, 1)


def _matches_in_round(draw_size: int, round_offset: int) -> int:
    # round_offset 0 = first round, then halves each round
    return (draw_size // 2) // (2 ** round_offset)


def create_match_skeleton(draw_id: int, tournament_start_date: date) -> Dict[str, Any]:
    """
    Create match skeleton rows for a draw.

    Rules:
    - First round player slots are filled strictly from draw positions:
        (1 vs 2), (3 vs 4), (5 vs 6), (7 vs 8) for an 8-slot bracket, etc.
    - Byes are represented by missing draw positions, i.e., NULL player slots.
    - DrawPlayers.has_bye must NOT null-out a real player.
    """
    db = DatabaseConnection()
    if not db.connect():
        raise MatchServiceError("Database connection failed")

    try:
        draw_players = db.query_params(
            """
            SELECT player_id, draw_position, has_bye
            FROM DrawPlayers
            WHERE draw_id = %s
            ORDER BY draw_position ASC
            """,
            (draw_id,),
        )
        if not draw_players:
            raise MatchServiceError(f"No DrawPlayers found for draw_id {draw_id}")

        num_entries = len(draw_players)
        draw_size = _draw_size_from_num_entries(num_entries)
        start_round_id = _starting_round_id(draw_size)

        # Map draw_position -> player_id (missing positions => BYE slots)
        pos_to_player: Dict[int, int] = {int(dp["draw_position"]): int(dp["player_id"]) for dp in draw_players}

        # Allocate match_id if not SERIAL (safe fallback)
        row = db.query("SELECT COALESCE(MAX(match_id), 0) + 1 AS next_id FROM Matches")
        next_match_id = int(row[0]["next_id"]) if row else 1

        cur = db.connection.cursor()
        created = 0
        round_offset = 0
        round_id = start_round_id

        while True:
            mcount = _matches_in_round(draw_size, round_offset)
            if mcount < 1:
                break

            for i in range(mcount):
                p1_id = None
                p2_id = None

                if round_offset == 0:
                    # First round: fixed bracket pairs by position
                    pos1 = (2 * i) + 1
                    pos2 = (2 * i) + 2
                    p1_id = pos_to_player.get(pos1)
                    p2_id = pos_to_player.get(pos2)

                cur.execute(
                    """
                    INSERT INTO Matches
                      (match_id, draw_id, round_id, match_number,
                       player1_id, player2_id,
                       match_date, match_status_id,
                       winner_id,
                       set1_player1, set1_player2, set1_tiebreak_player1, set1_tiebreak_player2,
                       set2_player1, set2_player2, set2_tiebreak_player1, set2_tiebreak_player2,
                       set3_player1, set3_player2, set3_tiebreak_player1, set3_tiebreak_player2,
                       set3_supertiebreak_player1, set3_supertiebreak_player2)
                    VALUES
                      (%s, %s, %s, %s,
                       %s, %s,
                       %s, %s,
                       %s,
                       NULL, NULL, NULL, NULL,
                       NULL, NULL, NULL, NULL,
                       NULL, NULL, NULL, NULL,
                       NULL, NULL)
                    """,
                    (
                        next_match_id,
                        draw_id,
                        round_id,
                        i + 1,          # round-local index
                        p1_id,
                        p2_id,
                        tournament_start_date,
                        1,              # Scheduled
                        None,
                    ),
                )

                created += 1
                next_match_id += 1

            if mcount == 1:
                break

            round_offset += 1
            round_id += 1

        # Auto-advance bye winners to next round
        cur.execute(
            """
            SELECT match_id, match_number, player1_id, player2_id
            FROM Matches
            WHERE draw_id = %s
              AND round_id = %s
              AND (player1_id IS NULL OR player2_id IS NULL)
              AND NOT (player1_id IS NULL AND player2_id IS NULL)
            """,
            (draw_id, start_round_id),
        )
        bye_matches = cur.fetchall()
        for bm in bye_matches:
            winner_id = bm[2] if bm[3] is None else bm[3]
            mn = bm[1]
            next_mn = (mn + 1) // 2
            next_rid = start_round_id + 1
            if mn % 2 == 1:
                cur.execute(
                    "UPDATE Matches SET player1_id = %s WHERE draw_id = %s AND round_id = %s AND match_number = %s",
                    (winner_id, draw_id, next_rid, next_mn),
                )
            else:
                cur.execute(
                    "UPDATE Matches SET player2_id = %s WHERE draw_id = %s AND round_id = %s AND match_number = %s",
                    (winner_id, draw_id, next_rid, next_mn),
                )
        db.connection.commit()
        cur.close()

        return {"draw_id": draw_id, "draw_size": draw_size, "matches_created": created}

    except Exception:
        try:
            db.connection.rollback()
        except Exception:
            pass
        raise
    finally:
        db.disconnect()


@dataclass(frozen=True)
class ResultPayload:
    match_id: int
    match_status_id: int
    winner_id: int
    set1_player1: Optional[int] = None
    set1_player2: Optional[int] = None
    set1_tiebreak_player1: Optional[int] = None
    set1_tiebreak_player2: Optional[int] = None
    set2_player1: Optional[int] = None
    set2_player2: Optional[int] = None
    set2_tiebreak_player1: Optional[int] = None
    set2_tiebreak_player2: Optional[int] = None
    set3_player1: Optional[int] = None
    set3_player2: Optional[int] = None
    set3_tiebreak_player1: Optional[int] = None
    set3_tiebreak_player2: Optional[int] = None
    set3_supertiebreak_player1: Optional[int] = None
    set3_supertiebreak_player2: Optional[int] = None


def apply_result_and_advance(draw_id: int, payload: ResultPayload) -> Dict[str, Any]:
    """
    Apply a validated result to a match and propagate the winner to the next round.

    Mapping rule:
    - match_number is treated as round-local index (created by create_match_skeleton).
    - next round match_number = ceil(current_match_number / 2)
    - winner slot: player1 for odd current_match_number, player2 for even.
    """
    validator = TennisMatchValidator()

    match_dict = {
        "match_status_id": payload.match_status_id,
        "set1_player1": payload.set1_player1,
        "set1_player2": payload.set1_player2,
        "set1_tiebreak_player1": payload.set1_tiebreak_player1,
        "set1_tiebreak_player2": payload.set1_tiebreak_player2,
        "set2_player1": payload.set2_player1,
        "set2_player2": payload.set2_player2,
        "set2_tiebreak_player1": payload.set2_tiebreak_player1,
        "set2_tiebreak_player2": payload.set2_tiebreak_player2,
        "set3_player1": payload.set3_player1,
        "set3_player2": payload.set3_player2,
        "set3_tiebreak_player1": payload.set3_tiebreak_player1,
        "set3_tiebreak_player2": payload.set3_tiebreak_player2,
        "set3_supertiebreak_player1": payload.set3_supertiebreak_player1,
        "set3_supertiebreak_player2": payload.set3_supertiebreak_player2,
    }

    ok, errors = validator.validate_match(match_dict)
    if not ok:
        raise MatchServiceError(f"Score validation failed: {errors}")

    # Validate winner consistency with set scores
    sets_p1 = 0
    sets_p2 = 0
    for s in ("set1", "set2", "set3"):
        sp1 = match_dict.get(f"{s}_player1")
        sp2 = match_dict.get(f"{s}_player2")
        if sp1 is not None and sp2 is not None:
            if sp1 > sp2:
                sets_p1 += 1
            elif sp2 > sp1:
                sets_p2 += 1

    db = DatabaseConnection()
    if not db.connect():
        raise MatchServiceError("Database connection failed")

    try:
        rows = db.query_params(
            """
            SELECT match_id, draw_id, round_id, match_number, player1_id, player2_id
            FROM Matches
            WHERE match_id = %s AND draw_id = %s
            """,
            (payload.match_id, draw_id),
        )
        if not rows:
            raise MatchServiceError(f"Match not found: match_id={payload.match_id}, draw_id={draw_id}")

        m = rows[0]
        round_id = int(m["round_id"])
        match_number = int(m["match_number"])

        cur = db.connection.cursor()

        # Update current match
        cur.execute(
            """
            UPDATE Matches
            SET match_status_id = %s,
                winner_id = %s,
                set1_player1 = %s, set1_player2 = %s, set1_tiebreak_player1 = %s, set1_tiebreak_player2 = %s,
                set2_player1 = %s, set2_player2 = %s, set2_tiebreak_player1 = %s, set2_tiebreak_player2 = %s,
                set3_player1 = %s, set3_player2 = %s, set3_tiebreak_player1 = %s, set3_tiebreak_player2 = %s,
                set3_supertiebreak_player1 = %s, set3_supertiebreak_player2 = %s
            WHERE match_id = %s AND draw_id = %s
            """,
            (
                payload.match_status_id,
                payload.winner_id,
                payload.set1_player1, payload.set1_player2, payload.set1_tiebreak_player1, payload.set1_tiebreak_player2,
                payload.set2_player1, payload.set2_player2, payload.set2_tiebreak_player1, payload.set2_tiebreak_player2,
                payload.set3_player1, payload.set3_player2, payload.set3_tiebreak_player1, payload.set3_tiebreak_player2,
                payload.set3_supertiebreak_player1, payload.set3_supertiebreak_player2,
                payload.match_id,
                draw_id,
            ),
        )

        # Disqualification sanction (match_status_id = 6)
        if payload.match_status_id == 6:
            if payload.winner_id not in (m["player1_id"], m["player2_id"]):
                raise ValueError("DQ requires winner_id to be one of the match players")

            dq_player_id = m["player2_id"] if payload.winner_id == m["player1_id"] else m["player1_id"]

            # Resolve tournament and start date from draw
            cur.execute(
                """
                SELECT d.tournament_id, t.start_date
                FROM Draws d
                JOIN Tournaments t ON t.tournament_id = d.tournament_id
                WHERE d.draw_id = %s
                """,
                (draw_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"draw_id not found: {draw_id}")

            tournament_id = row["tournament_id"]
            start_date = row["start_date"]

            # Prevent duplicates (idempotent behaviour)
            cur.execute(
                """
                SELECT 1
                FROM PlayerSuspensions
                WHERE player_id = %s
                  AND tournament_id = %s
                  AND reason_match_status_id = 6
                """,
                (dq_player_id, tournament_id),
            )
            exists = cur.fetchone() is not None

            if not exists:
                # Insert suspension (6 months)
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
                        6,
                        %s,
                        %s + INTERVAL '6 months'
                    FROM PlayerSuspensions
                    """,
                    (dq_player_id, tournament_id, start_date, start_date),
                )

                # Mark player suspended
                cur.execute(
                    """
                    UPDATE Players
                    SET status_id = 4
                    WHERE player_id = %s
                    """,
                    (dq_player_id,),
                )

        # No-show / walkover sanction (match_status_id = 3)
        if payload.match_status_id == 3:
            if payload.winner_id not in (m["player1_id"], m["player2_id"]):
                raise ValueError("Walkover requires winner_id to be one of the match players")

            wo_player_id = m["player2_id"] if payload.winner_id == m["player1_id"] else m["player1_id"]

            cur.execute(
                """
                SELECT d.tournament_id, t.start_date
                FROM Draws d
                         JOIN Tournaments t ON t.tournament_id = d.tournament_id
                WHERE d.draw_id = %s
                """,
                (draw_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"draw_id not found: {draw_id}")

            tournament_id = row[0]
            start_date = row[1]

            cur.execute(
                """
                SELECT 1
                FROM PlayerSuspensions
                WHERE player_id = %s
                  AND tournament_id = %s
                  AND reason_match_status_id = 3
                """,
                (wo_player_id, tournament_id),
            )
            exists = cur.fetchone() is not None

            if not exists:
                cur.execute(
                    """
                    INSERT INTO PlayerSuspensions (suspension_id,
                                                   player_id,
                                                   tournament_id,
                                                   reason_match_status_id,
                                                   suspension_start,
                                                   suspension_end)
                    SELECT COALESCE(MAX(suspension_id), 0) + 1,
                           %s,
                           %s,
                           3,
                           %s,
                           %s + INTERVAL '2 months'
                    FROM PlayerSuspensions
                    """,
                    (wo_player_id, tournament_id, start_date, start_date),
                )

                cur.execute(
                    """
                    UPDATE Players
                    SET status_id = 4
                    WHERE player_id = %s
                    """,
                    (wo_player_id,),
                )

# Advance winner
        next_round_id = round_id + 1
        next_match_number = (match_number + 1) // 2
        winner_to_player1 = (match_number % 2) == 1

        if winner_to_player1:
            cur.execute(
                """
                UPDATE Matches
                SET player1_id = %s
                WHERE draw_id = %s AND round_id = %s AND match_number = %s
                """,
                (payload.winner_id, draw_id, next_round_id, next_match_number),
            )
        else:
            cur.execute(
                """
                UPDATE Matches
                SET player2_id = %s
                WHERE draw_id = %s AND round_id = %s AND match_number = %s
                """,
                (payload.winner_id, draw_id, next_round_id, next_match_number),
            )

        db.connection.commit()
        cur.close()

        return {
            "draw_id": draw_id,
            "match_id": payload.match_id,
            "advanced_to_round_id": next_round_id,
            "advanced_to_match_number": next_match_number,
        }

    except Exception:
        try:
            db.connection.rollback()
        except Exception:
            pass
        raise
    finally:
        db.disconnect()
