#!/usr/bin/env python3
"""
ITF Match Generation Script
===========================

This script generates tennis match results with valid scores
and populates the Matches table.

Key Business Rules:
1. Matches follow knockout bracket structure
2. All set scores must be valid tennis scores
3. Winner advances to next round
4. Match dates progress through tournament week
5. Byes automatically advance players
6. Third set format determined by Draws.has_supertiebreak
7. Matches created with match_status_id=2 (Completed)
8. No player plays 2 matches on same day
9. round_id reflects tournament stage (1=R64, 2=R32, 3=R16, 4=QF, 5=SF, 6=F)

Valid Tennis Scores:
- Sets: 6-0, 6-1, 6-2, 6-3, 6-4, 7-5, 7-6
- Tie-breaks: First to 7, must win by 2
- Super tie-break: First to 10, must win by 2

Author: Malik Hamdane
Date: January 2026
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta, date
import random
import csv

# Import validation to verify generated scores
from scripts.validation.validate_tennis_matches import TennisMatchValidator

# Match scheduling (no player plays twice on the same day)
from src.modules.match_scheduler import schedule_match_dates

# Import score generator

# --- Score generation (delegated) -------------------------------------------

_SCOREGEN_IMPORT_ERROR = None
try:
    # Canonical location: src/modules/score_generator.py
    from src.modules.score_generator import ScoreGenerator  # type: ignore
except Exception as _e:
    ScoreGenerator = None  # type: ignore
    _SCOREGEN_IMPORT_ERROR = _e


def _require_score_generator() -> "ScoreGenerator":
    """
    Score generation MUST be delegated to score_generator.py (Rules.md source of truth).
    """
    if ScoreGenerator is None:
        raise RuntimeError(
            f"ScoreGenerator import failed from canonical location src/modules/score_generator.py: {_SCOREGEN_IMPORT_ERROR}"
        )

    return ScoreGenerator()


def calculate_round_id_for_draw(draw_size: int, round_number: int) -> int:
    """
    Calculate correct round_id based on draw size and round number.

    Round IDs represent tournament stages:
    1 = R64, 2 = R32, 3 = R16, 4 = QF, 5 = SF, 6 = Final

    Args:
        draw_size: Number of players (8, 16, 32, or 64)
        round_number: Round number (1 = first round, 2 = second round, etc.)

    Returns:
        round_id for this round
    """
    # Map draw size to starting round_id
    start_round_id = {
        8: 4,   # 8 players start at QF
        16: 3,  # 16 players start at R16
        32: 2,  # 32 players start at R32
        64: 1   # 64 players start at R64
    }

    starting_id = start_round_id.get(draw_size, 1)
    return starting_id + (round_number - 1)


def _pick_match_status_id() -> int:
    """
    Choose match_status_id for generated results.

    Score generation rules are enforced in src/modules/score_generator.py (Rules.md source of truth).
    Here, only status selection occurs for matches that are actually played.

    Rules.md global events are handled separately:
      - Post-draw no-show (0.5% of players) maps to match_status_id=3 and is applied to the player's
        first scheduled match by generate_knockout_matches().
      - Pre-draw withdrawal (0.1% of draws) must be applied before draw generation.

    Additional rule (agreed implementation detail):
      - Disqualification rate: 0.2% of played matches (match_status_id=6). The match must have started
        in normal conditions, so a partial score is generated (handled by score_generator.py).

    Current defaults for played matches:
      - Completed (2) dominates
      - Retired (4) occurs rarely
      - Disqualified (6) is very rare
    """
    r = random.random()

    # 0.2% disqualification (DQ) once match started
    if r < 0.002:
        return 6  # disqualified

    # 3% retirements
    if r < 0.002 + 0.03:
        return 4  # retired

    return 2      # completed


def _blank_score_fields() -> Dict[str, Optional[int]]:
    return {
        'set1_player1': None, 'set1_player2': None,
        'set1_tiebreak_player1': None, 'set1_tiebreak_player2': None,
        'set2_player1': None, 'set2_player2': None,
        'set2_tiebreak_player1': None, 'set2_tiebreak_player2': None,
        'set3_player1': None, 'set3_player2': None,
        'set3_tiebreak_player1': None, 'set3_tiebreak_player2': None,
        'set3_supertiebreak_player1': None, 'set3_supertiebreak_player2': None,
    }


def select_pre_draw_withdrawal_player_id(
    draw_players: List[Dict],
    *,
    probability: float = 0.001,
    rng: Optional[random.Random] = None
) -> Optional[int]:
    """
    Pre-draw withdrawal event (Rules.md):
      - In 0.1% cases (1 out of 1000), a player defaults between the entry deadline and the draw.

    This event must be applied BEFORE DrawPlayers seeding/positions are finalised.
    Matches generation MUST NOT mutate draw composition or seeding. Therefore, this function
    only selects a withdrawn player_id (or None) so that the caller can:
      - remove the player from Entries
      - adjust seeding (only if the withdrawn player would have been seeded)
      - regenerate DrawPlayers and DrawSeed accordingly
    """
    r = rng.random() if rng else random.random()
    if r >= probability:
        return None

    if not draw_players:
        return None

    picker = rng.choice if rng else random.choice
    return int(picker(draw_players)['player_id'])


def _pick_post_draw_no_show_players(
    draw_players: List[Dict],
    *,
    probability: float = 0.005,
    rng: Optional[random.Random] = None
) -> set:
    """
    Post-draw default / no-show event (Rules.md):
      - In 0.5% cases, a player will not show up or default AFTER the draw has been made.
      - This maps to match_status_id=3 (walkover / no-show) in the player’s first scheduled match.
    """
    if probability <= 0:
        return set()

    rrandom = rng.random if rng else random.random
    no_show = set()
    for p in draw_players:
        pid = int(p['player_id'])
        if rrandom() < probability:
            no_show.add(pid)
    return no_show


def _pick_weighted_winner_slot(
    player1_id: int,
    player2_id: int,
    *,
    ranking_positions: Optional[Dict[int, int]] = None,
    better_rank_win_probability: float = 2.0 / 3.0,
    rng: Optional[random.Random] = None
) -> int:
    """
    Winner selection rule (Rules.md):
      - The better ranked player (lower ranking position number) wins 2/3 of matches.

    If ranking positions are missing for either player, a 50/50 winner is chosen.
    """
    picker_random = rng.random if rng else random.random

    if not ranking_positions:
        return 1 if picker_random() < 0.5 else 2

    r1 = ranking_positions.get(int(player1_id))
    r2 = ranking_positions.get(int(player2_id))

    if r1 is None or r2 is None or r1 == r2:
        return 1 if picker_random() < 0.5 else 2

    better_slot = 1 if r1 < r2 else 2
    worse_slot = 2 if better_slot == 1 else 1

    return better_slot if picker_random() < better_rank_win_probability else worse_slot


def _swap_score_fields(score_fields: Dict[str, Optional[int]]) -> Dict[str, Optional[int]]:
    """
    Swap *_player1 and *_player2 score fields to flip the winner while preserving a valid scoreline.
    """
    swapped = {}
    for k, v in score_fields.items():
        if k.endswith('_player1'):
            k2 = k[:-8] + '_player2'
            swapped[k] = score_fields.get(k2)
            continue
        if k.endswith('_player2'):
            k2 = k[:-8] + '_player1'
            swapped[k] = score_fields.get(k2)
            continue
        swapped[k] = v
    return swapped

def _generate_score_and_winner(has_supertiebreak: bool, match_status_id: int) -> Tuple[Dict[str, Optional[int]], int]:
    """
    Returns:
      - score fields dict (Matches columns)
      - winner slot (1 or 2)

    Note:
      - match_status_id=6 (Disqualified) must represent a started match. A partial score is required.
        The score_generator.py module is expected to implement disqualification partial-scoring rules.
        If a dedicated API is not available, retired-match generation is used as a fallback to guarantee
        a started-match scoreline.
    """
    generator = _require_score_generator()

    # score_generator.py MUST implement Rules.md, including:
    # - tie-break weight distributions (including deuce extensions)
    # - super tie-break distributions (including deuce extensions)
    # - retired partial scoring (no later sets)
    # - completed match scoring (2 sets or 3rd set / super tie-break depending on draw)
    # - disqualified partial scoring (started match), if exposed by the generator API
    if match_status_id == 2:
        out = generator.generate_completed_match(has_supertiebreak=has_supertiebreak)
        return out.score, int(out.winner_slot)

    if match_status_id == 4:
        out = generator.generate_retired_match(has_supertiebreak=has_supertiebreak)
        return out.score, int(out.winner_slot)

    if match_status_id == 6:
        if hasattr(generator, "generate_disqualified_match"):
            out = generator.generate_disqualified_match(has_supertiebreak=has_supertiebreak)
            return out.score, int(out.winner_slot)

        out = generator.generate_retired_match(has_supertiebreak=has_supertiebreak)
        return out.score, int(out.winner_slot)

    # Walkover / cancelled: scores must be NULL; winner is still required to advance bracket.
    winner_slot = 1 if random.random() < 0.5 else 2
    return _blank_score_fields(), winner_slot


def generate_knockout_matches(
    draw_id: int,
    draw_players: List[Dict],
    tournament_start_date,
    has_supertiebreak: bool,
    next_match_id: int = 1,
    ranking_positions: Optional[Dict[int, int]] = None,
    *,
    post_draw_no_show_probability: float = 0.005,
    better_rank_win_probability: float = 2.0 / 3.0,
    rng: Optional[random.Random] = None
) -> List[Dict]:
    """
    Generate knockout bracket matches with results.

    Args:
        draw_id: Draw identifier
        draw_players: List of DrawPlayers dicts with player_id, draw_position, has_bye
        tournament_start_date: Tournament start date (datetime/date)
        has_supertiebreak: Whether third set uses super tie-break
        next_match_id: Starting match_id
        ranking_positions: Optional map {player_id: ranking_position} for the relevant WeeklyRanking publication
        post_draw_no_show_probability: Probability per player of a post-draw no-show (Rules.md: 0.5%)
        better_rank_win_probability: Probability that the better ranked player wins (Rules.md: 2/3)
        rng: Optional random.Random for deterministic generation

    Returns:
        List of match records ready for insert/export
    """
    matches: List[Dict] = []

    # Sort players by draw_position
    current_round_players = sorted(draw_players, key=lambda x: x['draw_position'])
    draw_size = len(current_round_players)

    post_draw_no_show_players = _pick_post_draw_no_show_players(
        current_round_players,
        probability=post_draw_no_show_probability,
        rng=rng
    )

    validator = TennisMatchValidator()

    round_number = 1
    base_match_date: date = tournament_start_date.date() if isinstance(tournament_start_date, datetime) else tournament_start_date

    while len(current_round_players) > 1:
        next_round_players: List[Dict] = []
        round_id = calculate_round_id_for_draw(draw_size, round_number)
        round_date: date = base_match_date + timedelta(days=round_number - 1)

        for i in range(0, len(current_round_players), 2):
            if i + 1 >= len(current_round_players):
                next_round_players.append(current_round_players[i])
                continue

            player1 = current_round_players[i]
            player2 = current_round_players[i + 1]

            if player1.get('has_bye'):
                next_round_players.append(player2)
                continue
            if player2.get('has_bye'):
                next_round_players.append(player1)
                continue

            player1_id = player1['player_id']
            player2_id = player2['player_id']

            desired_winner_slot = _pick_weighted_winner_slot(
                int(player1_id),
                int(player2_id),
                ranking_positions=ranking_positions,
                better_rank_win_probability=better_rank_win_probability,
                rng=rng
            )

            player1_no_show = int(player1_id) in post_draw_no_show_players
            player2_no_show = int(player2_id) in post_draw_no_show_players

            max_attempts = 50

            if player1_no_show or player2_no_show:
                match_status_id = 3  # walkover / no-show (post-draw event)
                if player1_no_show and not player2_no_show:
                    desired_winner_slot = 2
                if player2_no_show and not player1_no_show:
                    desired_winner_slot = 1
                score_fields = _blank_score_fields()
                winner_slot = desired_winner_slot
                is_valid, errors = True, []
            else:
                match_status_id = _pick_match_status_id()

                # Generate score + winner (Rules.md implemented in score_generator.py)
                score_fields, winner_slot = _generate_score_and_winner(
                    has_supertiebreak=has_supertiebreak,
                    match_status_id=match_status_id
                )

                # Force winner according to ranking rule by swapping score fields if required.
                if winner_slot != desired_winner_slot:
                    score_fields = _swap_score_fields(score_fields)
                    winner_slot = desired_winner_slot

                # Validate score against current validation rules
                temp_match = {'match_status_id': match_status_id, **score_fields}
                is_valid, errors = validator.validate_match(temp_match)

                attempts = 0
                while not is_valid and attempts < max_attempts:
                    score_fields, winner_slot = _generate_score_and_winner(
                        has_supertiebreak=has_supertiebreak,
                        match_status_id=match_status_id
                    )
                    if winner_slot != desired_winner_slot:
                        score_fields = _swap_score_fields(score_fields)
                        winner_slot = desired_winner_slot
                    temp_match = {'match_status_id': match_status_id, **score_fields}
                    is_valid, errors = validator.validate_match(temp_match)
                    attempts += 1

            match_data: Dict[str, object] = {
                'match_id': next_match_id,
                'draw_id': draw_id,
                'round_id': round_id,
                'match_number': len(matches) + 1,
                'player1_id': player1_id,
                'player2_id': player2_id,
                'match_date': round_date,
                'match_status_id': match_status_id,
                'winner_id': None,
            }
            if not is_valid:
                print(f"Warning: Could not generate valid score after {max_attempts} attempts. Errors: {errors}")

            winner = player1 if winner_slot == 1 else player2
            match_data['winner_id'] = player1_id if winner_slot == 1 else player2_id

            match_data.update(score_fields)

            matches.append(match_data)  # type: ignore[arg-type]
            next_match_id += 1

            next_round_players.append(winner)

        current_round_players = next_round_players
        round_number += 1

    # Enforce scheduling constraint: no player plays twice on the same day (Rules.md)
    matches = schedule_match_dates(matches, tournament_start_date=base_match_date)

    return matches


def format_score(match: Dict) -> str:
    """Format match score for display."""
    parts = []
    for set_num in range(1, 4):
        p1 = match.get(f'set{set_num}_player1')
        p2 = match.get(f'set{set_num}_player2')
        if p1 is None:
            break

        score_str = f"{p1}-{p2}"

        tb1 = match.get(f'set{set_num}_tiebreak_player1')
        if tb1 is not None:
            tb2 = match.get(f'set{set_num}_tiebreak_player2')
            score_str += f"({tb1}-{tb2})"

        stb1 = match.get(f'set{set_num}_supertiebreak_player1')
        if stb1 is not None:
            stb2 = match.get(f'set{set_num}_supertiebreak_player2')
            score_str += f"[{stb1}-{stb2}]"

        parts.append(score_str)

    return " ".join(parts)


def main():
    """Example usage."""
    draw_players = [
        {'player_id': 100 + i, 'draw_position': i + 1, 'has_bye': False}
        for i in range(16)
    ]

    matches = generate_knockout_matches(
        draw_id=1,
        draw_players=draw_players,
        tournament_start_date=datetime(2025, 1, 6),
        has_supertiebreak=True,
        next_match_id=1
    )

    print(f"Generated {len(matches)} matches for 16-player draw")
    print("\nSample matches:")
    for match in matches[:5]:
        print(f"Match {match['match_number']}: Round {match['round_id']}, {format_score(match)}")

    with open('matches_generated.csv', 'w', newline='') as f:
        fieldnames = list(matches[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matches)

    print("\n✓ Exported to matches_generated.csv")


if __name__ == '__main__':
    main()
