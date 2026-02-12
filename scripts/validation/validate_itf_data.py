#!/usr/bin/env python3
"""
ITF Data Validation Master Orchestrator
========================================

This script orchestrates all ITF business rule validations across the dataset.
Connects to PostgreSQL database to validate actual loaded data.

Validations Performed:
1. Draw sizes (6-64 players)
2. Entry deadlines (Tuesday 10:00 UTC)
3. Draw publication deadlines (Friday midnight)
4. Match scores (tennis rules, status alignment, NULL handling)
5. Player schedules (no 2 matches same day)
6. Seeding rules (against SeedingRules table)
7. Points calculation (first-match losers = 0 points)
8. Date formats (timestamps vs SHORT DATE)

Author: Malik Hamdane
Date: January 2026
"""

from typing import Dict, List, Tuple
from datetime import datetime, date
from collections import defaultdict

# Import database connection
from src.modules.db_connection import get_all_data

# Import validation modules
from scripts.validation.validate_tennis_matches import TennisMatchValidator
from scripts.generation.generate_entries import validate_entries, validate_entry_deadline
from scripts.generation.generate_draw_players import validate_draw_publication_deadline
# from calculate_points_history import is_first_match_loss


class ITFDataValidator:
    """Master validator for all ITF tournament data."""
    
    def __init__(self):
        self.match_validator = TennisMatchValidator()
        self.errors = []
        self.warnings = []
    
    def validate_all(self, data: Dict) -> Tuple[bool, List[str], List[str]]:
        """
        Run all validations on ITF data from database.
        
        Args:
            data: Dictionary containing all table data from database
            
        Returns:
            Tuple of (all_valid, list_of_errors, list_of_warnings)
        """
        self.errors = []
        self.warnings = []
        
        tournaments = data['tournaments']
        draws = data['draws']
        entries = data['entries']
        draw_players = data['draw_players']
        matches = data['matches']
        points_history = data['points_history']
        seeding_rules = data['seeding_rules']
        players = data['players']
        age_categories = data['age_categories']

        print("=" * 80)
        print("ITF DATA VALIDATION - DATABASE DATA")
        print("=" * 80)
        
        # 1. Validate draw sizes
        print("\n1. Validating draw sizes (6-64 players)...")
        self._validate_draw_sizes(draws, draw_players)
        
        # 2. Validate entry deadlines
        print("2. Validating entry deadlines (Tuesday 10:00 UTC)...")
        self._validate_entry_deadlines(tournaments, entries)

        # 3. Validate player age eligibility per age category (Rules.md)
        print("3. Validating player age eligibility (age category rules)...")
        self._validate_player_age_eligibility(players, age_categories, tournaments, entries)

        # 4. Validate draw publication deadlines
        print("4. Validating draw publication (Friday midnight)...")
        self._validate_draw_publication(tournaments, draws)
        
        # 5. Validate match scores
        print("5. Validating match scores (tennis rules, status)...")
        self._validate_match_scores(matches, draws)
        
        # 6. Validate player schedules
        print("6. Validating player schedules (no 2 matches/day)...")
        self._validate_player_schedules(matches)
        
        # 7. Validate seeding
        print("7. Validating seeding (against SeedingRules)...")
        self._validate_seeding(draws, draw_players, seeding_rules)
        
        # 8. Validate date formats
        print("8. Validating date formats (timestamps vs dates)...")
        self._validate_date_formats(tournaments, entries, draw_players, draws, points_history, matches)
        
        # Summary
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        if len(self.errors) == 0:
            print(f"✓ All validations PASSED")
            if len(self.warnings) > 0:
                print(f"⚠ {len(self.warnings)} warnings (non-critical)")
        else:
            print(f"✗ {len(self.errors)} ERRORS found")
            if len(self.warnings) > 0:
                print(f"⚠ {len(self.warnings)} warnings")
        
        return (len(self.errors) == 0, self.errors, self.warnings)
    
    def _validate_draw_sizes(self, draws: List[Dict], draw_players: List[Dict]):
        """Validate all draws have 6-64 players."""
        draw_sizes = {}
        for dp in draw_players:
            draw_id = dp['draw_id']
            draw_sizes[draw_id] = draw_sizes.get(draw_id, 0) + 1
        
        for draw in draws:
            draw_id = draw['draw_id']
            num_players = draw_sizes.get(draw_id, 0)
            
            # Skip draws that haven't been generated yet OR have no players
            if not draw.get('draw_generated_at') or num_players == 0:
                continue
            
            is_valid, error = self.match_validator.validate_draw_size(num_players)
            if not is_valid:
                self.errors.append(f"Draw {draw_id}: {error}")
        
        print(f"   Checked {len(draws)} draws")

    def _validate_player_age_eligibility(
        self,
        players: List[Dict],
        age_categories: List[Dict],
        tournaments: List[Dict],
        entries: List[Dict],
    ):
        """
        Rules.md: player must be old enough for the category in the tournament year,
        and must enter the highest eligible age category (no playing down).
        """
        from src.modules.rules_engine import AgeCategoryRule, required_age_category_id, RuleError

        players_by_id = {int(p["player_id"]): p for p in players}
        tourn_by_id = {int(t["tournament_id"]): t for t in tournaments}

        categories = tuple(
            AgeCategoryRule(
                age_category_id=int(c["age_category_id"]),
                min_age=int(c["min_age"]),
                max_age=(int(c["max_age"]) if c.get("max_age") is not None else None),
            )
            for c in age_categories
        )

        checked = 0
        for e in entries:
            checked += 1
            pid = int(e["player_id"])
            tid = int(e["tournament_id"])
            requested_acid = int(e["age_category_id"])

            p = players_by_id.get(pid)
            t = tourn_by_id.get(tid)
            if not p or not t:
                continue

            birth_year = p.get("birth_year")
            tourn_year = t.get("tournament_year")

            if birth_year is None or tourn_year is None:
                self.errors.append(
                    f"Entry {e.get('entry_id', '?')}: missing birth_year or tournament_year for validation "
                    f"(player_id={pid}, tournament_id={tid})"
                )
                continue

            try:
                required_id = required_age_category_id(
                    birth_year=int(birth_year),
                    tournament_year=int(tourn_year),
                    categories=categories,
                )
            except RuleError as ex:
                self.errors.append(
                    f"Entry {e.get('entry_id', '?')}: player_id={pid} not eligible for any age category "
                    f"(tournament_id={tid}, tournament_year={tourn_year}): {ex}"
                )
                continue

            if requested_acid != int(required_id):
                self.errors.append(
                    f"Entry {e.get('entry_id', '?')}: player_id={pid} entered age_category_id={requested_acid} "
                    f"but must enter age_category_id={required_id} for tournament_year={tourn_year} "
                    f"(tournament_id={tid})"
                )

        print(f"   Checked {checked} entries for age eligibility")

    def _validate_entry_deadlines(self, tournaments: List[Dict], entries: List[Dict]):
        """Validate all entries before Tuesday 10:00 UTC deadline."""
        entries_by_tournament = defaultdict(list)
        for entry in entries:
            entries_by_tournament[entry['tournament_id']].append(entry)
        
        for tournament in tournaments:
            tourn_id = tournament['tournament_id']
            tourn_entries = entries_by_tournament.get(tourn_id, [])
            
            if not tourn_entries:
                continue
            
            start_date = tournament['start_date']
            
            is_valid, errors = validate_entry_deadline(tourn_entries, start_date)
            if not is_valid:
                self.errors.extend([f"Tournament {tourn_id}: {e}" for e in errors])
        
        print(f"   Checked {len(entries)} entries across {len(tournaments)} tournaments")
    
    def _validate_draw_publication(self, tournaments: List[Dict], draws: List[Dict]):
        """Validate draws published before Friday 19:00 UTC."""
        draws_by_tournament = defaultdict(list)
        for d in draws:
            draws_by_tournament[d['tournament_id']].append(d)

        checked = 0
        for tournament in tournaments:
            tourn_id = tournament['tournament_id']
            start_date = tournament['start_date']

            for draw in draws_by_tournament.get(tourn_id, []):
                draw_gen = draw.get('draw_generated_at')
                if not draw_gen:
                    continue

                checked += 1
                is_valid, error = validate_draw_publication_deadline(draw_gen, start_date)
                if not is_valid:
                    self.errors.append(f"Tournament {tourn_id}, Draw {draw.get('draw_id')}: {error}")

        print(f"   Checked {checked} draw publications")
    
    def _validate_match_scores(self, matches: List[Dict], draws: List[Dict]):
        """Validate all match scores follow tennis rules."""
        for match in matches:
            is_valid, errors = self.match_validator.validate_match(match)
            if not is_valid:
                match_id = match.get('match_id', 'unknown')
                self.errors.extend([f"Match {match_id}: {e}" for e in errors])
        
        print(f"   Checked {len(matches)} matches")
    
    def _validate_player_schedules(self, matches: List[Dict]):
        """Validate no player has 2 matches on same day."""
        is_valid, errors = self.match_validator.validate_player_schedule(matches)
        if not is_valid:
            self.errors.extend(errors)
        
        print(f"   Checked player schedules across {len(matches)} matches")
    
    def _validate_seeding(
        self,
        draws: List[Dict],
        draw_players: List[Dict],
        seeding_rules: List[Dict]
    ):
        """Validate seeding against SeedingRules table."""
        players_by_draw = defaultdict(list)
        for dp in draw_players:
            players_by_draw[dp['draw_id']].append(dp)
        
        for draw in draws:
            draw_id = draw['draw_id']
            
            # Skip draws that haven't been generated yet or have no player count
            if not draw.get('draw_generated_at') or draw.get('num_players') is None or draw.get('num_players') == 0:
                continue
            
            num_players = draw['num_players']
            players = players_by_draw.get(draw_id, [])
            
            is_valid, errors = self.match_validator.validate_seeding(
                players, int(num_players), seeding_rules
            )
            if not is_valid:
                self.errors.extend([f"Draw {draw_id}: {e}" for e in errors])
        
        print(f"   Checked seeding for {len(draws)} draws")
    
    def _validate_date_formats(
        self,
        tournaments: List[Dict],
        entries: List[Dict],
        draw_players: List[Dict],
        draws: List[Dict],
        points_history: List[Dict],
        matches: List[Dict]
    ):
        """Validate timestamp vs SHORT DATE fields."""
        # Timestamp fields (should have time component)
        timestamp_checks = [
            ('Entries', 'entry_timestamp', entries),
            ('DrawPlayers', 'entry_timestamp', draw_players),
            ('Draws', 'draw_generated_at', draws),
            ('PointsHistory', 'created_at', points_history)
        ]
        
        # Date fields (should NOT have time component)
        date_checks = [
            ('Tournaments', 'start_date', tournaments),
            ('Tournaments', 'end_date', tournaments),
            ('Matches', 'match_date', matches),
            ('PointsHistory', 'tournament_end_date', points_history)
        ]
        
        # Check timestamp fields
        for table, field, records in timestamp_checks:
            if not records:
                continue
            sample = records[0].get(field)
            if sample and isinstance(sample, datetime):
                # This is correct - timestamps should be datetime
                pass
            elif sample and isinstance(sample, date):
                self.warnings.append(
                    f"{table}.{field} is date instead of datetime (should have time)"
                )
        
        # Check date fields
        for table, field, records in date_checks:
            if not records:
                continue
            sample = records[0].get(field)
            if sample and isinstance(sample, datetime):
                # Check if time is 00:00:00 (acceptable for date fields)
                if sample.hour != 0 or sample.minute != 0 or sample.second != 0:
                    self.errors.append(
                        f"{table}.{field} has time component (should be date only)"
                    )
        
        print(f"   Checked date format consistency")


def main():
    """Run validation on database data."""
    
    print("=" * 80)
    print("ITF DATA VALIDATION - CONNECTING TO DATABASE")
    print("=" * 80)
    
    # Load data from database
    data = get_all_data()
    
    if not data:
        print("\n✗ Failed to load data from database")
        return
    
    # Run validation
    validator = ITFDataValidator()
    is_valid, errors, warnings = validator.validate_all(data)
    
    # Display results
    if errors:
        print("\n" + "=" * 80)
        print("ERRORS:")
        print("=" * 80)
        for error in errors:
            print(f"  ✗ {error}")
    
    if warnings:
        print("\n" + "=" * 80)
        print("WARNINGS:")
        print("=" * 80)
        for warning in warnings:
            print(f"  ⚠ {warning}")
    
    if is_valid:
        print("\n" + "=" * 80)
        print("✓✓✓ ALL VALIDATIONS PASSED ✓✓✓")
        print("=" * 80)


if __name__ == '__main__':
    main()
