#!/usr/bin/env python3
"""
ITF WeeklyRanking Calculation Script
====================================

This script calculates weekly tennis rankings based on tournament results
and populates the WeeklyRanking table.

Key Business Rules (Rules.md):
1. Rankings based on 52-week rolling window
2. Only best 4 tournament results count toward total points
3. Separate rankings for each (age_category, gender) combination
4. Rankings are published every Monday at 20:00 UTC (Coordinated Universal Time)
5. Ranking week N includes tournaments in ISO weeks (N-52) .. (N-1), inclusive

Author: Malik Hamdane
Date: January 2026
"""

from typing import Dict, List
from collections import defaultdict

from src.modules.ranking_window import IsoWeek, add_iso_weeks


def _iso_to_abs(w: IsoWeek) -> int:
    """Convert ISO week to a sortable integer key."""
    return int(w.iso_year) * 100 + int(w.iso_week)


def calculate_weekly_ranking(
    ranking_year: int,
    ranking_week: int,
    points_history: List[Dict],          # All PointsHistory records
    tournaments: Dict[int, Dict],        # tournament_id -> {year, week}
    player_gender: Dict[int, int],       # player_id -> gender_id
) -> List[Dict]:
    """
    Calculate rankings for a specific week.

    CRITICAL RULES:
    1) 52-week window: only tournaments from ISO weeks (N-52) .. (N-1) count (inclusive).
    2) Best 4 results: sum only the best 4 tournament results per player.

    Args:
        ranking_year: ISO year of the ranking (e.g., 2026)
        ranking_week: ISO week number of the ranking (1-52/53)
        points_history: PointsHistory records (points_earned must already reflect penalties, e.g., 0 points)
        tournaments: Tournament metadata (ISO year/week per tournament_id)
        player_gender: Player gender mapping

    Returns:
        List of WeeklyRanking records (dicts)
    """

    # Rules.md: ranking week N includes tournaments in ISO weeks (N-52) .. (N-1)
    window_start_week = add_iso_weeks(ranking_year, ranking_week, -52)
    window_end_week = add_iso_weeks(ranking_year, ranking_week, -1)

    start_abs = _iso_to_abs(window_start_week)
    end_abs = _iso_to_abs(window_end_week)

    # Collect all tournament points within window
    # Key: (player_id, age_category_id, gender_id)
    # Value: List of points_earned from each tournament (one row per draw result)
    player_tournament_points = defaultdict(list)

    for ph in points_history:
        tournament_id = ph["tournament_id"]
        if tournament_id not in tournaments:
            continue

        t_year = int(tournaments[tournament_id]["year"])
        t_week = int(tournaments[tournament_id]["week"])
        t_abs = t_year * 100 + t_week

        if not (start_abs <= t_abs <= end_abs):
            continue

        player_id = int(ph["player_id"])
        age_cat = int(ph["age_category_id"])
        gender_id = player_gender.get(player_id)

        # Eligibility/penalties must already be reflected in points_earned (e.g., 0 points).
        if gender_id:
            key = (player_id, age_cat, int(gender_id))
            player_tournament_points[key].append(int(ph["points_earned"]))

    # Calculate total points (best 4 results only)
    weekly_rankings = []

    for (player_id, age_cat, gender_id), points_list in player_tournament_points.items():
        best_4 = sorted(points_list, reverse=True)[:4]
        total_points = sum(best_4)

        weekly_rankings.append({
            "player_id": player_id,
            "age_category_id": age_cat,
            "gender_id": gender_id,
            "ranking_year": ranking_year,
            "ranking_week": ranking_week,
            "total_points": total_points,
            "rank_position": 0,  # assigned next
        })

    # Assign rank positions within each category (age_category_id, gender_id)
    rankings_by_category = defaultdict(list)
    for wr in weekly_rankings:
        key = (wr["age_category_id"], wr["gender_id"])
        rankings_by_category[key].append(wr)

    for _, rankings in rankings_by_category.items():
        rankings.sort(key=lambda x: x["total_points"], reverse=True)
        for rank, wr in enumerate(rankings, 1):
            wr["rank_position"] = rank

    return weekly_rankings


if __name__ == "__main__":
    # This module is designed to be imported by generation/recalculation scripts.
    # A full CLI runner is intentionally not included here.
    raise SystemExit(0)
