#!/usr/bin/env python3
"""
Match scheduler
===============

This module assigns match_date values while enforcing:

- No player plays two matches on the same day.

This is a scheduling constraint only. It must not alter match outcomes, scores,
or bracket structure.

Inputs:
- matches: list of match dicts (as produced by scripts/generation/generate_matches.py)
- tournament_start_date: date of tournament start (date object)

Required match dict keys:
- player1_id
- player2_id
- round_id
- match_number
- match_date (may be set; will be overwritten deterministically)

Output:
- Same list object (returned), with match_date updated.

Rules.md alignment:
- Round dates progress across the tournament week.
- If a clash occurs (a player already scheduled on that day), the match is pushed
  forward by whole days until the constraint is satisfied.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional


def _as_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def schedule_match_dates(matches: List[Dict], tournament_start_date: date) -> List[Dict]:
    """
    Assign match dates enforcing: no player plays twice on the same day.

    Strategy:
    - Sort matches by (round_id, match_number) so earlier rounds schedule first.
    - Default desired date: tournament_start_date + (round_id - 1) days.
    - If either player is already scheduled on that date, push forward day-by-day.
    """
    last_date_by_player: Dict[int, date] = {}

    def sort_key(m: Dict):
        return (int(m.get("round_id", 0)), int(m.get("match_number", 0)), int(m.get("match_id", 0)))

    for m in sorted(matches, key=sort_key):
        p1 = _as_int(m.get("player1_id"))
        p2 = _as_int(m.get("player2_id"))

        if p1 is None or p2 is None:
            raise ValueError(f"Scheduling requires both player1_id and player2_id (match_id={m.get('match_id')})")

        round_id = int(m.get("round_id", 0))
        desired = tournament_start_date + timedelta(days=max(0, round_id - 1))

        while (last_date_by_player.get(p1) == desired) or (last_date_by_player.get(p2) == desired):
            desired = desired + timedelta(days=1)

        m["match_date"] = desired
        last_date_by_player[p1] = desired
        last_date_by_player[p2] = desired

    return matches
