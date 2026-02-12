#!/usr/bin/env python3
"""
ITF PointsHistory Calculation Script
====================================

This script calculates points earned by players in tournaments
and populates the PointsHistory table.

Key Business Rules:
1. First-match losers receive 0 points (regardless of tournament category or round)
2. First match determined by checking Matches table for wins
3. Points awarded based on:
   - Tournament category (MT1000, MT700, MT400, MT200, MT100)
   - Stage reached (determined by the round of the losing match, or by the final)
4. All players receive a PointsHistory record (even with 0 points)

IMPORTANT:
- The Matches.round_id values in your data are *per-draw sequential round numbers* (e.g., 1/2/3 for QF/SF/F),
  not the global MatchRounds identifiers (R64/R32/R16/QF/SF/F).
- Therefore, stage_result_id must be inferred from the number of rounds present in the draw.

Author: Malik Hamdane
Date: January 2026
"""

from typing import Dict, List, Tuple
from datetime import datetime, time, timedelta


# Match status IDs (MatchStatus.match_status_id)
STATUS_WALKOVER_NOSHOW = 3
STATUS_DISQUALIFIED = 6


# Stage Result IDs (StageResults.id)
STAGE_WINNER = 1
STAGE_FINALIST = 2
STAGE_SEMI_FINALIST = 3
STAGE_QUARTER_FINALIST = 4
STAGE_LAST_16 = 5
STAGE_LAST_32 = 6
STAGE_LAST_64 = 7


def _build_round_ranks(draw_id: int, matches: List[Dict]) -> Tuple[Dict[int, int], List[int]]:
    """
    Build a per-draw ordering of round_id values from Matches.

    Example (8-player draw stored as 1/2/3):
      round_ids present: [1, 2, 3]
      ranks: {1:1, 2:2, 3:3}
      => rank 3 is Final for that draw
    """
    round_ids = sorted({
        m["round_id"]
        for m in matches
        if m.get("draw_id") == draw_id and m.get("round_id") is not None
    })
    ranks = {rid: idx + 1 for idx, rid in enumerate(round_ids)}
    return ranks, round_ids


def _stage_from_loss_round_rank(loss_round_rank: int, total_rounds: int) -> int:
    """
    Convert a player's elimination round (by draw-relative rank) into StageResults.id.

    distance_from_final:
      1 => Semi-finalist
      2 => Quarter-finalist
      3 => Last 16
      4 => Last 32
      5 => Last 64

    Winner/Finalist are handled separately from the final match itself.
    """
    distance_from_final = total_rounds - loss_round_rank
    mapping = {
        1: STAGE_SEMI_FINALIST,
        2: STAGE_QUARTER_FINALIST,
        3: STAGE_LAST_16,
        4: STAGE_LAST_32,
        5: STAGE_LAST_64,
    }
    return mapping.get(distance_from_final, STAGE_LAST_64)


def get_player_stage_from_matches(
    player_id: int,
    draw_id: int,
    matches: List[Dict]
) -> tuple:
    """
    Determine what stage a player reached based on actual match results.

    Logic (draw-relative, derived from Matches):
    1) Infer the round progression for this draw from distinct round_id values present in Matches.
    2) Identify the final match (highest draw-relative round rank).
    3) If the player is in the final:
         - winner => Winner (1)
         - loser  => Finalist (2)
    4) Otherwise:
         - determine the highest round where the player lost; map that to StageResults.id.
    5) First-match loss rule:
         - if the player has 0 wins in the draw, points will be 0 (handled by calculate_points_history),
           but stage_result_id remains correct (typically the round they lost in).

    Returns:
        Tuple of (stage_result_id, is_first_match_loss)
    """
    # Matches for this draw
    draw_matches = [m for m in matches if m.get("draw_id") == draw_id]
    if not draw_matches:
        return (STAGE_LAST_64, True)

    round_ranks, round_ids = _build_round_ranks(draw_id, draw_matches)
    if not round_ids:
        return (STAGE_LAST_64, True)

    total_rounds = len(round_ids)
    final_round_id = round_ids[-1]

    # Matches for this player in this draw
    player_matches = [
        m for m in draw_matches
        if m.get("player1_id") == player_id or m.get("player2_id") == player_id
    ]

    if not player_matches:
        # No recorded matches => treat as no wins, lowest stage
        return (STAGE_LAST_64, True)

    total_wins = sum(1 for m in player_matches if m.get("winner_id") == player_id)
    is_first_match_loss = (total_wins == 0)

    # Identify the final match (highest round in the draw). There should be exactly one.
    final_matches = [m for m in draw_matches if m.get("round_id") == final_round_id]
    final_match = final_matches[0] if final_matches else None

    if final_match:
        p1 = final_match.get("player1_id")
        p2 = final_match.get("player2_id")
        w = final_match.get("winner_id")

        if player_id == w:
            return (STAGE_WINNER, is_first_match_loss)

        if player_id in (p1, p2) and player_id != w:
            return (STAGE_FINALIST, is_first_match_loss)

    # Not winner/finalist: find the highest round where the player lost
    def _round_rank(m: Dict) -> int:
        return round_ranks.get(m.get("round_id"), 0)

    losses = []
    for m in player_matches:
        w = m.get("winner_id")
        if w is None:
            continue
        if w != player_id:
            losses.append(m)

    if losses:
        last_loss = max(losses, key=_round_rank)
        loss_rank = _round_rank(last_loss)
        stage_result_id = _stage_from_loss_round_rank(loss_rank, total_rounds)
        return (stage_result_id, is_first_match_loss)

    # Fallback: player has matches but no recorded loss and was not detected in final
    # This should not normally occur; treat as highest reached round.
    reached_rank = max((_round_rank(m) for m in player_matches), default=1)
    stage_result_id = _stage_from_loss_round_rank(reached_rank, total_rounds)
    return (stage_result_id, is_first_match_loss)


def _is_player_disqualified_in_draw(player_id: int, draw_id: int, matches: List[Dict]) -> bool:
    """Return True if the player was disqualified in this draw.

    Rules.md requirement:
    - Disqualification (match_status_id = 6) implies the match started.
    - Disqualified players earn 0 points for that tournament.

    Implementation:
    - If any match in this draw has match_status_id = 6 and the player is one of the participants,
      treat the player as disqualified for points purposes.
    """
    for m in matches:
        if m.get("draw_id") != draw_id:
            continue
        if m.get("match_status_id") != STATUS_DISQUALIFIED:
            continue
        p1 = m.get("player1_id")
        p2 = m.get("player2_id")
        w = m.get("winner_id")
        if (player_id == p1 or player_id == p2) and player_id != w:
            return True
    return False


def _is_player_zero_points_status_in_draw(player_id: int, draw_id: int, matches: List[Dict]) -> bool:
    """Return True if the player must receive 0 points for this draw due to match status.

    Rules.md requirement (tournament-level penalty):
    - match_status_id = 6 (Disqualified): player earns 0 points for the tournament.
    - match_status_id = 3 (No-show / Walkover after draw): player earns 0 points for the tournament
      (suspension is handled separately in PlayerSuspensions).

    Implementation:
    - If any match in this draw has match_status_id in (3, 6) and the player is a participant,
      treat the player as a 0-point player for PointsHistory in this tournament.
    """
    for m in matches:
        if m.get("draw_id") != draw_id:
            continue
        if m.get("match_status_id") not in (STATUS_WALKOVER_NOSHOW, STATUS_DISQUALIFIED):
            continue
        p1 = m.get("player1_id")
        p2 = m.get("player2_id")
        w = m.get("winner_id")
        if (player_id == p1 or player_id == p2) and player_id != w:
            return True
    return False


def calculate_points_history(
    draw_id: int,
    tournament_id: int,
    age_category_id: int,
    category_id: int,  # Tournament category (1-5)
    points_rules: Dict[tuple, int],  # (category_id, stage_result_id) -> points
    tournament_end_date,
    matches: List[Dict],  # All match records for this draw
    player_ids: List[int],  # All players in this draw
    next_ph_id: int
) -> List[Dict]:
    """
    Calculate PointsHistory records for a single draw based on actual match results.

    CRITICAL RULES:
    1) Players who lose their first match receive 0 points.
       This is determined by checking the Matches table for wins.
    2) Players who are disqualified (match_status_id = 6) receive 0 points for the tournament.
    3) Players with no-show / walkover after draw (match_status_id = 3) receive 0 points for the tournament.
    """
    created_at = datetime.combine(tournament_end_date, time(0, 0, 0)) + timedelta(days=1, hours=20)

    points_history = []

    for player_id in player_ids:
        stage_result_id, is_first_match_loss = get_player_stage_from_matches(
            player_id, draw_id, matches
        )

        # Tournament-level penalties (Rules.md):
        # - match_status_id = 6 (Disqualified) => 0 points for the tournament
        # - match_status_id = 3 (No-show / Walkover after draw) => 0 points for the tournament
        is_zero_points_status = _is_player_zero_points_status_in_draw(player_id, draw_id, matches)

        if is_zero_points_status:
            points_earned = 0
        elif is_first_match_loss:
            points_earned = 0
        else:
            points_earned = points_rules.get((category_id, stage_result_id), 0)

        points_history.append({
            "id": next_ph_id,
            "player_id": player_id,
            "tournament_id": tournament_id,
            "age_category_id": age_category_id,
            "stage_result_id": stage_result_id,
            "points_earned": points_earned,
            "tournament_end_date": tournament_end_date,
            "created_at": created_at
        })
        next_ph_id += 1

    return points_history
