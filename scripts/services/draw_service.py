#!/usr/bin/env python3
"""
Draw service (production workflow)
==================================

Purpose:
- Generate a draw from real Entries:
  - Insert Draws
  - Insert DrawPlayers using existing seeding/position logic.

Depends on:
- db_connection.DatabaseConnection
- generate_draw_players.generate_draw_players (existing algorithm)
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List

from src.modules.db_connection import DatabaseConnection
from scripts.generation.generate_draw_players import generate_draw_players

from src.modules.ranking_window import (
    draw_publication_dt_for_tournament_week,
    entry_deadline_dt_for_tournament_week,
)


class DrawServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class DrawGenerationRequest:
    tournament_id: int
    age_category_id: int
    gender_id: int
    draw_status_id: int
    has_supertiebreak: bool
    draw_generated_at: datetime
    is_active: bool = True


def generate_draw_from_entries(req: DrawGenerationRequest) -> Dict[str, Any]:
    """
    Create Draws + DrawPlayers from the Entries table for (tournament, age, gender).

    Returns:
        Dict containing draw_id and counts.
    """
    db = DatabaseConnection()
    if not db.connect():
        raise DrawServiceError("Database connection failed")

    try:
        # Pull eligible entries for this draw context
        entries = db.query_params(
            """
            SELECT entry_id, tournament_id, player_id, age_category_id, gender_id,
                   entry_points, entry_timestamp
            FROM Entries
            WHERE tournament_id = %s
              AND age_category_id = %s
              AND gender_id = %s
            ORDER BY entry_points DESC, entry_timestamp ASC
            """,
            (req.tournament_id, req.age_category_id, req.gender_id),
        )

        if not entries or len(entries) < 6:
            raise DrawServiceError(f"Insufficient entries: {0 if not entries else len(entries)} (min 6)")

        tmeta = db.query_params(
            "SELECT tournament_year, tournament_week FROM Tournaments WHERE tournament_id = %s",
            (req.tournament_id,),
        )
        if not tmeta:
            raise DrawServiceError(f"Tournament not found: {req.tournament_id}")

        ty = int(tmeta[0]["tournament_year"])
        tw = int(tmeta[0]["tournament_week"])
        draw_deadline = draw_publication_dt_for_tournament_week(ty, tw)

        entry_deadline = entry_deadline_dt_for_tournament_week(ty, tw)
        if req.draw_generated_at < entry_deadline:
            raise DrawServiceError(
                f"Draw blocked: entry deadline {entry_deadline} has not passed yet"
            )

        if req.draw_generated_at > draw_deadline:
            raise DrawServiceError(
                f"Draw blocked: generated_at {req.draw_generated_at} is after deadline {draw_deadline}"
            )

        # Seeding rules are reference data
        seeding_rules = db.query("SELECT * FROM SeedingRules ORDER BY min_players, max_players")
        seeding_rules = [r for r in seeding_rules if int(r["min_players"]) <= len(entries) <= int(r["max_players"])]

        # Allocate draw_id if not SERIAL (safe fallback)
        row = db.query("SELECT COALESCE(MAX(draw_id), 0) + 1 AS next_id FROM Draws")
        draw_id = int(row[0]["next_id"]) if row else 1

        # Insert Draws
        cur = db.connection.cursor()
        cur.execute(
            """
            INSERT INTO Draws
              (draw_id, tournament_id, age_category_id, gender_id,
               draw_status_id, num_players, has_supertiebreak, draw_generated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                draw_id,
                req.tournament_id,
                req.age_category_id,
                req.gender_id,
                req.draw_status_id,
                len(entries),
                req.has_supertiebreak,
                req.draw_generated_at,
            ),
        )

        # Generate DrawPlayers rows using existing algorithm
        # --- AMENDMENT (Rules.md): tournaments 1–2 are NOT SEEDED; first seeding applies from tournament_id = 3 ---
        disable_seeding = req.tournament_id in (1, 2)

        draw_players = generate_draw_players(
            draw_id=draw_id,
            entries=entries,
            draw_generated_timestamp=req.draw_generated_at,
            seeding_rules=seeding_rules,
            disable_seeding=disable_seeding,
        )

        # Insert DrawPlayers (schema-driven)
        insert_sql = """
            INSERT INTO DrawPlayers
              (draw_id, player_id, draw_position, has_bye, entry_points, entry_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        for dp in draw_players:
            cur.execute(
                insert_sql,
                (
                    draw_id,
                    dp.get("player_id"),
                    dp.get("draw_position"),
                    dp.get("has_bye"),
                    dp.get("entry_points"),
                    dp.get("entry_timestamp"),
                ),
            )

        # Insert DrawSeed rows for seeded players
        if not disable_seeding:
            seed_sql = """
                       INSERT INTO DrawSeed
                           (draw_id, player_id, seed_number, seeding_points, is_actual_seeding)
                       VALUES (%s, %s, %s, %s, %s) \
                       """
            seeded_entries = sorted(entries, key=lambda e: -int(e.get("entry_points", 0)))
            rule = seeding_rules[0] if seeding_rules else {}
            num_seeds = int(rule.get("num_seeds", 0))
            for seed_num, entry in enumerate(seeded_entries[:num_seeds], start=1):
                cur.execute(
                    seed_sql,
                    (
                        draw_id,
                        int(entry["player_id"]),
                        seed_num,
                        int(entry.get("entry_points", 0)),
                        True,
                    ),
                )

        db.connection.commit()
        cur.close()

        return {
            "draw_id": draw_id,
            "entries_used": len(entries),
            "draw_players_created": len(draw_players),
        }

    except Exception:
        try:
            db.connection.rollback()
        except Exception:
            pass
        raise
    finally:
        db.disconnect()
