#!/usr/bin/env python3
"""
Entry service (production workflow)
===================================

Purpose:
- Insert a single entry into Entries with deadline enforcement.

Depends on:
- db_connection.DatabaseConnection (existing project module)
- generate_entries.calculate_entry_deadline (existing rules function)

Notes:
- This module is intended to be called from Flask routes (or admin CLI).
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

from src.modules.db_connection import DatabaseConnection
from src.modules.ranking_window import entry_deadline_dt_for_tournament_week

from src.modules.rules_engine import AgeCategoryRule, required_age_category_id, RuleError


@dataclass(frozen=True)
class EntryRequest:
    tournament_id: int
    player_id: int
    age_category_id: int
    gender_id: int
    entry_points: int
    entry_timestamp: datetime


class EntryServiceError(RuntimeError):
    pass


def create_entry(req: EntryRequest) -> Dict[str, Any]:
    """
    Insert a single entry into Entries after enforcing the entry deadline.

    Returns:
        Inserted row (or a minimal dict containing identifiers).
    """
    db = DatabaseConnection()
    if not db.connect():
        raise EntryServiceError("Database connection failed")

    try:
        # Tournament start date required for deadline rule
        tourn = db.query_params(
            "SELECT tournament_id, start_date FROM Tournaments WHERE tournament_id = %s",
            (req.tournament_id,),
        )
        if not tourn:
            raise EntryServiceError(f"Tournament not found: {req.tournament_id}")

        tourn_meta = db.query_params(
            "SELECT tournament_id, tournament_year, tournament_week FROM Tournaments WHERE tournament_id = %s",
            (req.tournament_id,),
        )
        if not tourn_meta:
            raise EntryServiceError(f"Tournament not found: {req.tournament_id}")

        tournament_year = int(tourn_meta[0]["tournament_year"])
        tournament_week = int(tourn_meta[0]["tournament_week"])

        deadline = entry_deadline_dt_for_tournament_week(tournament_year, tournament_week)

        if req.entry_timestamp > deadline:
            raise EntryServiceError(
                f"Entry blocked: timestamp {req.entry_timestamp} is after deadline {deadline}"
            )

        # Rules.md: player must be eligible for the age category,
        # and must enter the highest eligible age category (no playing down).
        player_rows = db.query_params(
            "SELECT player_id, birth_year FROM Players WHERE player_id = %s",
            (req.player_id,),
        )
        if not player_rows:
            raise EntryServiceError(f"Player not found: {req.player_id}")
        birth_year = player_rows[0].get("birth_year")
        if birth_year is None:
            raise EntryServiceError(f"Player {req.player_id} has no birth_year")

        tourn_year_rows = db.query_params(
            "SELECT tournament_id, tournament_year FROM Tournaments WHERE tournament_id = %s",
            (req.tournament_id,),
        )
        tournament_year = tourn_year_rows[0].get("tournament_year")
        if tournament_year is None:
            raise EntryServiceError(f"Tournament {req.tournament_id} has no tournament_year")

        ac_rows = db.query(
            "SELECT age_category_id, min_age, max_age FROM AgeCategory ORDER BY min_age ASC"
        )

        categories_list = []
        for r in ac_rows:
            if r.get("max_age") is None:
                raise EntryServiceError("AgeCategory.max_age is NULL but Rules.md requires it")
            categories_list.append(
                AgeCategoryRule(
                    age_category_id=int(r["age_category_id"]),
                    min_age=int(r["min_age"]),
                    max_age=int(r["max_age"]),
                )
            )

        categories = tuple(categories_list)

        try:
            required_id = required_age_category_id(
                birth_year=int(birth_year),
                tournament_year=int(tournament_year),
                categories=categories,
            )
        except RuleError as e:
            raise EntryServiceError(str(e))

        if int(req.age_category_id) != int(required_id):
            raise EntryServiceError(
                f"Entry blocked: player {req.player_id} must enter age_category_id={required_id} "
                f"for tournament_year={tournament_year} (requested {req.age_category_id})"
            )

        # Optional: prevent duplicate entry for same (tournament, player, age, gender)
        dup = db.query_params(
            """
            SELECT 1
            FROM Entries
            WHERE tournament_id = %s
              AND player_id = %s
              AND age_category_id = %s
              AND gender_id = %s
            LIMIT 1
            """,
            (req.tournament_id, req.player_id, req.age_category_id, req.gender_id),
        )
        if dup:
            raise EntryServiceError("Duplicate entry already exists for this draw context")

        # Allocate entry_id if not SERIAL (safe fallback)
        row = db.query("SELECT COALESCE(MAX(entry_id), 0) + 1 AS next_id FROM Entries")
        next_id = int(row[0]["next_id"]) if row else 1

        cur = db.connection.cursor()
        cur.execute(
            """
            INSERT INTO Entries
              (entry_id, tournament_id, player_id, age_category_id, gender_id,
               entry_points, entry_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                next_id,
                req.tournament_id,
                req.player_id,
                req.age_category_id,
                req.gender_id,
                req.entry_points,
                req.entry_timestamp,
            ),
        )
        db.connection.commit()
        cur.close()

        return {
            "entry_id": next_id,
            "tournament_id": req.tournament_id,
            "player_id": req.player_id,
            "age_category_id": req.age_category_id,
            "gender_id": req.gender_id,
            "entry_points": req.entry_points,
            "entry_timestamp": req.entry_timestamp,
        }

    except Exception:
        try:
            db.connection.rollback()
        except Exception:
            pass
        raise
    finally:
        db.disconnect()
