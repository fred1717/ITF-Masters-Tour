#!/usr/bin/env python3
"""
ITF Tournament Entries Generation Script
========================================

This script generates tournament entries (player registrations)
and populates the Entries table.

Key Business Rules:
1. Entry deadline: Tuesday 10:00 UTC for tournament starting following week
2. Draw size limits: Minimum 6 players (tournament cancelled), maximum 64 players
3. Players can enter multiple age categories at same tournament
4. Each entry has unique entry_id
5. Entries recorded with timestamp (first-come-first-served for seeding tiebreaker)
6. Age category restrictions: One ranking per age group, no lower category entries

Author: Malik Hamdane
Date: January 2026
"""

from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from src.modules.ranking_window import iso_week_of, entry_deadline_dt_for_tournament_week
from src.modules import rules_engine as R
import random


def calculate_entry_deadline(tournament_start_date: datetime) -> datetime:
    """
    Calculate entry deadline for a tournament.

    ITF Rule: Entry deadline is Tuesday 10:00 UTC for tournament
    starting the following week.

    Process:
    1. Find Monday of tournament week
    2. Go back 7 days to previous week's Monday
    3. Add 1 day to get Tuesday
    4. Set time to 10:00 UTC

    Args:
        tournament_start_date: Date tournament begins (typically Monday)

    Returns:
        Entry deadline datetime (Tuesday 10:00 UTC, week before tournament)
    """
    # Convert tournament start date -> ISO year/week, then apply Rules.md deadline
    if isinstance(tournament_start_date, datetime):
        d = tournament_start_date.date()
    else:
        d = tournament_start_date

    iso = iso_week_of(d)
    return entry_deadline_dt_for_tournament_week(iso.iso_year, iso.iso_week)


def build_eligible_players(
        *,
        tournament_year: int,
        tournament_start_date: datetime,
        players: List[Dict],  # rows with player_id, gender_id, birth_year
        draws: List[Dict],  # rows with age_category_id, gender_id
        age_category_rules: Tuple[R.AgeCategoryRule, ...],
        player_suspensions: List[Dict],
        entry_deadline: datetime,
) -> Dict[Tuple[int, int], List[int]]:
    """Build eligible_players mapping while enforcing Rules.md.

    Enforced rules:
    - Calendar-year eligibility (age = tournament_year - birth_year).
    - Superior age group exclusion (only the highest eligible age category is allowed).
    - Suspended players cannot enter (checked at entry_deadline timestamp).
    """
    # Index players for quick lookups
    by_gender: Dict[int, List[Dict]] = {}
    for p in players:
        gid = int(p["gender_id"])
        by_gender.setdefault(gid, []).append(p)

    eligible: Dict[Tuple[int, int], List[int]] = {}

    for d in draws:
        age_category_id = int(d["age_category_id"])
        gender_id = int(d["gender_id"])

        out_ids: List[int] = []
        for p in by_gender.get(gender_id, []):
            player_id = int(p["player_id"])
            birth_year = int(p["birth_year"])

            # Eligibility within tournament calendar year
            # (Rules.md: calendar-year age, not as-of a specific day)
            try:
                # Must be eligible for requested category…
                # …and must not be eligible for a superior category
                allowed = R.enforce_superior_age_group_exclusion(
                    birth_year=birth_year,
                    tournament_year=tournament_year,
                    requested_age_category_id=age_category_id,
                    categories=age_category_rules,
                )
            except Exception:
                # Not eligible for any category
                continue

            if not allowed:
                continue

            # Suspended players cannot enter (checked at entry deadline)
            if R.is_player_suspended(player_id=player_id, at_dt=entry_deadline, suspensions=player_suspensions):
                continue

            out_ids.append(player_id)

        eligible[(age_category_id, gender_id)] = out_ids

    return eligible


def generate_entries(
        tournament_id: int,
        tournament_start_date: datetime,
        eligible_players: Dict[Tuple[int, int], List[int]],  # (age_cat, gender) -> [player_ids]
        next_entry_id: int,
        *,
        tournament_year: int | None = None,
        players: List[Dict] | None = None,
        draws: List[Dict] | None = None,
        age_category_rules: Tuple[R.AgeCategoryRule, ...] | None = None,
        player_suspensions: List[Dict] | None = None,
) -> List[Dict]:
    """
    Generate tournament entries for all draws.

    Args:
        tournament_id: Tournament ID
        tournament_start_date: When tournament starts
        eligible_players: Players eligible for each (age_category, gender)
        next_entry_id: Next available entry ID

    Returns:
        List of Entries records
    """
    entry_deadline = calculate_entry_deadline(tournament_start_date)

    # Rules.md enforcement (eligibility + superior age group exclusion + suspensions)
    if tournament_year is not None and players is not None and draws is not None and age_category_rules is not None and player_suspensions is not None:
        eligible_players = build_eligible_players(
            tournament_year=int(tournament_year),
            tournament_start_date=tournament_start_date,
            players=players,
            draws=draws,
            age_category_rules=age_category_rules,
            player_suspensions=player_suspensions,
            entry_deadline=entry_deadline,
        )

    # Entry window: Players can enter from 30 days before deadline up to deadline
    entry_window_start = entry_deadline - timedelta(days=30)

    entries = []

    for (age_category_id, gender_id), player_ids in eligible_players.items():
        # Validate draw size constraints
        num_players = len(player_ids)
        if num_players > 64:
            print(f"WARNING: Draw (age={age_category_id}, gender={gender_id}) has "
                  f"{num_players} players. Max 64 allowed. Truncating to first 64.")
            player_ids = player_ids[:64]

        # Simulate players entering at different times
        # Most players enter in the last 2 weeks before deadline
        for player_id in player_ids:
            # Random entry time within the window
            # Weight towards last 14 days (70% of entries)
            if random.random() < 0.7:
                # Last 14 days
                days_before_deadline = random.randint(0, 14)
            else:
                # Earlier (15-30 days before)
                days_before_deadline = random.randint(15, 30)

            hours_offset = random.randint(0, 23)
            minutes_offset = random.randint(0, 59)

            entry_time = entry_deadline - timedelta(
                days=days_before_deadline,
                hours=hours_offset,
                minutes=minutes_offset
            )

            entries.append({
                'entry_id': next_entry_id,
                'player_id': player_id,
                'tournament_id': tournament_id,
                'age_category_id': age_category_id,
                'gender_id': gender_id,
                'entry_timestamp': entry_time,
                'withdrawn_at': None,
                'withdrawal_type': None,
            })
            next_entry_id += 1

    return entries


def validate_entries(
        entries: List[Dict],
        tournament_id: int
) -> Tuple[bool, List[str]]:
    """
    Validate tournament entries meet requirements.

    CRITICAL RULES:
    1. Minimum 6 players required per draw (tournament cancelled if < 6)
    2. Maximum 64 players per draw
    3. All entries before deadline

    Args:
        entries: List of entry records
        tournament_id: Tournament ID

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Group entries by draw (age_category, gender)
    draws = {}
    for entry in entries:
        if entry['tournament_id'] == tournament_id:
            key = (entry['age_category_id'], entry['gender_id'])
            if key not in draws:
                draws[key] = []
            draws[key].append(entry)

    # Check draw size constraints
    for (age_cat, gender), draw_entries in draws.items():
        num_players = len(draw_entries)

        age_name = "60" if age_cat == 1 else "65"
        gender_name = "Men" if gender == 1 else "Women"

        if num_players < 6:
            errors.append(
                f"{gender_name} {age_name}: Only {num_players} entries "
                f"(minimum 6 required - TOURNAMENT CANCELLED)"
            )

        if num_players > 64:
            errors.append(
                f"{gender_name} {age_name}: {num_players} entries "
                f"(maximum 64 allowed)"
            )

    return (len(errors) == 0, errors)


def validate_entry_deadline(
        entries: List[Dict],
        tournament_start_date: datetime
) -> Tuple[bool, List[str]]:
    """
    Validate that all entries are before the deadline.

    Args:
        entries: List of entry records
        tournament_start_date: When tournament starts

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    entry_deadline = calculate_entry_deadline(tournament_start_date)

    for entry in entries:
        entry_time = entry['entry_timestamp']

        # Normalise to UTC when comparing naive datetimes
        et = entry_time if entry_time.tzinfo else entry_time.replace(tzinfo=R.UTC)
        dl = entry_deadline if entry_deadline.tzinfo else entry_deadline.replace(tzinfo=R.UTC)

        if et > dl:
            errors.append(
                f"Entry {entry['entry_id']} (player {entry['player_id']}) "
                f"submitted at {entry_time} after deadline {entry_deadline}"
            )

    return (len(errors) == 0, errors)


def main():
    """Example usage of Entries generation."""

    print("=" * 80)
    print("TOURNAMENT ENTRIES GENERATION - ITF RULES")
    print("=" * 80)

    # Example: Nice MT700 Open 2025 (starts Monday Jan 6, 2025)
    tournament_id = 1
    tournament_start = datetime(2025, 1, 6, 10, 0)

    # Calculate entry deadline
    deadline = calculate_entry_deadline(tournament_start)
    print(f"\nTournament: Nice MT700 Open 2025")
    print(f"Start Date: {tournament_start.strftime('%Y-%m-%d %A')}")
    print(f"Entry Deadline: {deadline.strftime('%Y-%m-%d %A %H:%M UTC')}")

    # Verify deadline calculation
    expected_deadline = datetime(2024, 12, 31, 10, 0)  # Tuesday before
    if deadline == expected_deadline:
        print(f"✓ Deadline calculation correct")
    else:
        print(f"✗ Deadline mismatch: expected {expected_deadline}, got {deadline}")

    # Example: Eligible players
    # Men 60: 16 players, Men 65: 8 players, Women 60: 12 players
    eligible_players = {
        (1, 1): list(range(100, 116)),  # Men 60: 16 players
        (2, 1): list(range(200, 208)),  # Men 65: 8 players
        (1, 2): list(range(300, 312)),  # Women 60: 12 players
    }

    # Generate entries
    entries = generate_entries(
        tournament_id=tournament_id,
        tournament_start_date=tournament_start,
        eligible_players=eligible_players,
        next_entry_id=1
    )

    print(f"\nGenerated {len(entries)} total entries:")

    # Group and display by draw
    draws = {}
    for entry in entries:
        key = (entry['age_category_id'], entry['gender_id'])
        if key not in draws:
            draws[key] = []
        draws[key].append(entry)

    draw_names = {
        (1, 1): "Men 60",
        (2, 1): "Men 65",
        (1, 2): "Women 60",
        (2, 2): "Women 65"
    }

    for key in sorted(draws.keys()):
        draw_entries = draws[key]
        draw_name = draw_names.get(key, f"Age {key[0]}, Gender {key[1]}")
        print(f"  {draw_name}: {len(draw_entries)} entries")

    # Validate entries
    print(f"\n{'=' * 80}")
    print("VALIDATION - DRAW SIZE")
    print("=" * 80)

    is_valid, errors = validate_entries(entries, tournament_id)

    if is_valid:
        print("✓ All draws meet size requirements (6-64 players)")
    else:
        print("✗ VALIDATION FAILED:")
        for error in errors:
            print(f"  - {error}")

    # Validate deadline
    print(f"\n{'=' * 80}")
    print("VALIDATION - ENTRY DEADLINE")
    print("=" * 80)

    is_valid, errors = validate_entry_deadline(entries, tournament_start)

    if is_valid:
        print(f"✓ All entries before deadline ({deadline.strftime('%Y-%m-%d %H:%M UTC')})")
    else:
        print("✗ DEADLINE VIOLATIONS:")
        for error in errors:
            print(f"  - {error}")

    # Example with insufficient entries
    print(f"\n{'=' * 80}")
    print("EXAMPLE: INVALID TOURNAMENT (insufficient entries)")
    print("=" * 80)

    # Only 3 players in Men 60
    invalid_eligible = {
        (1, 1): [100, 101, 102],  # Only 3 players - INVALID
        (1, 2): list(range(300, 308)),  # Women 60: 8 players - OK
    }

    invalid_entries = generate_entries(
        tournament_id=2,
        tournament_start_date=datetime(2025, 2, 10, 10, 0),
        eligible_players=invalid_eligible,
        next_entry_id=1000
    )

    is_valid, errors = validate_entries(invalid_entries, 2)

    if not is_valid:
        print("\n✗ Tournament must be CANCELLED:")
        for error in errors:
            print(f"  - {error}")

    # Show entry timing distribution
    print(f"\n{'=' * 80}")
    print("ENTRY TIMESTAMPS (showing first 5 Men 60 entries)")
    print("=" * 80)

    men_60_entries = [e for e in entries if e['age_category_id'] == 1 and e['gender_id'] == 1]
    men_60_entries.sort(key=lambda x: x['entry_timestamp'])

    print("\nEntry order (affects seeding when rankings are equal):")
    for i, entry in enumerate(men_60_entries[:5], 1):
        days_before = (deadline - entry['entry_timestamp']).days
        print(f"{i}. Player {entry['player_id']}: "
              f"{entry['entry_timestamp'].strftime('%Y-%m-%d %H:%M')} "
              f"({days_before} days before deadline)")


if __name__ == '__main__':
    random.seed(42)  # For reproducible results
    main()
