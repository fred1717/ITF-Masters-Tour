#!/usr/bin/env python3
"""
ITF Tennis Match Validation Script
===================================

This script validates tennis match data against ITF business rules.
Returns validation results (True/False + errors) - does NOT update database.

Business Rules Enforced:
1. Draw size: 6-64 players (minimum 6, maximum 64)
2. Set scores must follow tennis rules (6-0 to 6-4, 7-5, 7-6 only)
3. Tie-break scores must follow tie-break rules (first to 7, win by 2)
4. Super tie-break scores must follow super tie-break rules (first to 10, win by 2)
5. Match status determines which score fields are allowed
6. Complete matches must have at least 2 sets
7. Matches may have a third set or super tie-break
8. Retired matches may have partial set scores and may end during Set 1 or Set 2
9. Invalid combinations are rejected (e.g., tie-break score without 7-6 set)

Author: Malik Hamdane
Date: January 2026
"""

from typing import Dict, List, Tuple, Optional


class TennisMatchValidator:
    """Validates tennis match scores according to ITF rules."""

    # Match status IDs (from MatchStatus table)
    STATUS_SCHEDULED = 1
    STATUS_COMPLETED = 2
    STATUS_WALKOVER = 3
    STATUS_RETIRED = 4
    STATUS_CANCELLED = 5
    STATUS_DISQUALIFIED = 6

    @staticmethod
    def validate_draw_size(num_players: int) -> Tuple[bool, Optional[str]]:
        """
        Validate that a draw has valid player count.

        ITF Rule: Minimum 6 players, maximum 64 players.

        Args:
            num_players: Number of players in the draw

        Returns:
            Tuple of (is_valid, error_message)
        """
        if num_players < 6:
            return False, f"Draw has {num_players} players. Minimum 6 required (tournament cancelled)"
        if num_players > 64:
            return False, f"Draw has {num_players} players. Maximum 64 allowed"
        return True, None

    @staticmethod
    def validate_set_score(player1_games: int, player2_games: int) -> bool:
        """
        Validate that a set score follows tennis rules.

        Valid scores: 6-0, 6-1, 6-2, 6-3, 6-4, 7-5, 7-6
        (and reverse for other player)

        Invalid examples:
        - 6-5 (not won by 2 games)
        - 6-8 or 8-6 (can't have more than 7 games)
        - 7-7 (impossible)
        """
        if player1_games is None or player2_games is None:
            return False

        # No player can have more than 7 games in a set
        if player1_games > 7 or player2_games > 7:
            return False

        # 7-7 is impossible
        if player1_games == 7 and player2_games == 7:
            return False

        # Use whitelist of valid scores
        valid_scores = [
            (6, 0), (6, 1), (6, 2), (6, 3), (6, 4),
            (7, 5), (7, 6),
            (0, 6), (1, 6), (2, 6), (3, 6), (4, 6),
            (5, 7), (6, 7)
        ]

        return (player1_games, player2_games) in valid_scores

    # --- AMENDMENT (Rules.md): partial scores for retired matches (retire can occur in Set 1/2/3) ---
    @staticmethod
    def validate_partial_set_score(player1_games: int, player2_games: int) -> bool:
        """
        Partial (incomplete) set score for retirement cases.
        - integers 0..6
        - not equal
        - not 6-6
        - not a completed set score
        """
        if player1_games is None or player2_games is None:
            return False
        if not isinstance(player1_games, int) or not isinstance(player2_games, int):
            return False
        if player1_games < 0 or player2_games < 0:
            return False
        if player1_games > 6 or player2_games > 6:
            return False
        if player1_games == player2_games:
            return False
        if player1_games == 6 and player2_games == 6:
            return False
        if TennisMatchValidator.validate_set_score(player1_games, player2_games):
            return False
        return True

    @staticmethod
    def validate_partial_tiebreak_score(tb_player1: int, tb_player2: int) -> bool:
        """
        Partial tie-break score for retirement cases.
        - non-negative integers
        - not equal
        - not a completed tie-break score
        """
        if tb_player1 is None or tb_player2 is None:
            return False
        if not isinstance(tb_player1, int) or not isinstance(tb_player2, int):
            return False
        if tb_player1 < 0 or tb_player2 < 0:
            return False
        if tb_player1 == tb_player2:
            return False
        if TennisMatchValidator.validate_tiebreak_score(tb_player1, tb_player2):
            return False
        return True

    @staticmethod
    def validate_partial_supertiebreak_score(stb_player1: int, stb_player2: int) -> bool:
        """
        Partial super tie-break score for retirement cases.
        - non-negative integers
        - not equal
        - not a completed super tie-break score
        """
        if stb_player1 is None or stb_player2 is None:
            return False
        if not isinstance(stb_player1, int) or not isinstance(stb_player2, int):
            return False
        if stb_player1 < 0 or stb_player2 < 0:
            return False
        if stb_player1 == stb_player2:
            return False
        if TennisMatchValidator.validate_supertiebreak_score(stb_player1, stb_player2):
            return False
        return True

    @staticmethod
    def requires_tiebreak(player1_games: int, player2_games: int) -> bool:
        """Check if a set score requires a tie-break."""
        if player1_games is None or player2_games is None:
            return False
        return (player1_games == 7 and player2_games == 6) or \
            (player1_games == 6 and player2_games == 7)

    @staticmethod
    def validate_tiebreak_score(tb_player1: int, tb_player2: int) -> bool:
        """
        Validate tie-break score.

        Rules:
        - First to 7 points, must win by 2
        - Can go beyond 7 (e.g., 8-6, 9-7, 10-8)
        """
        if tb_player1 is None or tb_player2 is None:
            return False

        # Winner must have at least 7 points
        if max(tb_player1, tb_player2) < 7:
            return False

        # Must win by 2
        if abs(tb_player1 - tb_player2) < 2:
            return False

        return True

    @staticmethod
    def validate_supertiebreak_score(stb_player1: int, stb_player2: int) -> bool:
        """
        Validate super tie-break score.

        Rules:
        - First to 10 points, must win by 2
        - Can go beyond 10 (e.g., 12-10, 15-13)
        """
        if stb_player1 is None or stb_player2 is None:
            return False

        # Winner must have at least 10 points
        if max(stb_player1, stb_player2) < 10:
            return False

        # Must win by 2
        if abs(stb_player1 - stb_player2) < 2:
            return False

        return True

    @staticmethod
    def sets_are_split(set1_p1: int, set1_p2: int,
                       set2_p1: int, set2_p2: int) -> bool:
        """Check if each player won one of the first two sets."""
        if any(x is None for x in [set1_p1, set1_p2, set2_p1, set2_p2]):
            return False

        player1_won_set1 = set1_p1 > set1_p2
        player1_won_set2 = set2_p1 > set2_p2

        return player1_won_set1 != player1_won_set2

    def validate_match_scores_for_status(
            self,
            match_data: Dict,
            match_status_id: int
    ) -> Tuple[bool, List[str]]:
        """
        Validate match scores against match status.

        Status rules:
        - Scheduled (1): Must have NULL scores
        - Completed (2): Must have complete valid scores
        - Walkover (3): May have NULL or partial scores
        - Retired (4): Must have partial scores (at least set 1)
        - Cancelled (5): Must have NULL scores
        """
        errors = []

        has_set1 = match_data.get('set1_player1') is not None
        has_set2 = match_data.get('set2_player1') is not None
        has_set3 = match_data.get('set3_player1') is not None or \
                   match_data.get('set3_supertiebreak_player1') is not None

        if match_status_id == self.STATUS_SCHEDULED:
            # Must have NULL scores
            if has_set1 or has_set2 or has_set3:
                errors.append("Scheduled match cannot have scores")

        elif match_status_id == self.STATUS_COMPLETED:
            # Must have complete scores (at least 2 sets)
            if not has_set1 or not has_set2:
                errors.append("Completed match must have at least 2 sets")

        elif match_status_id == self.STATUS_WALKOVER:
            # May have NULL or partial - no validation needed
            pass

        # --- AMENDMENT (Rules.md): retirement can occur in Set 1, Set 2, or Set 3 ---
        elif match_status_id == self.STATUS_RETIRED:
            # Must have started (at least some Set 1 score must exist); Set 3 is permitted.
            if not has_set1:
                errors.append("Retired match must have at least set 1 scores")

        elif match_status_id == self.STATUS_DISQUALIFIED:
            # Must have started (same partial-score rules as retired)
            if not has_set1:
                errors.append("Disqualified match must have at least set 1 scores")

        elif match_status_id == self.STATUS_CANCELLED:
            # Must have NULL scores
            if has_set1 or has_set2 or has_set3:
                errors.append("Cancelled match cannot have scores")

        return (len(errors) == 0, errors)

    def validate_match(self, match_data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate complete match data.

        Args:
            match_data: Dictionary containing match scores and status

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Get match status
        match_status_id = match_data.get('match_status_id', self.STATUS_SCHEDULED)

        # First validate scores match status
        status_valid, status_errors = self.validate_match_scores_for_status(
            match_data, match_status_id
        )
        errors.extend(status_errors)

        # If status doesn't allow scores, skip score validation
        if match_status_id in [self.STATUS_SCHEDULED, self.STATUS_CANCELLED]:
            return (len(errors) == 0, errors)

        # Extract match data
        set1_p1 = match_data.get('set1_player1')
        set1_p2 = match_data.get('set1_player2')
        set1_tb_p1 = match_data.get('set1_tiebreak_player1')
        set1_tb_p2 = match_data.get('set1_tiebreak_player2')

        set2_p1 = match_data.get('set2_player1')
        set2_p2 = match_data.get('set2_player2')
        set2_tb_p1 = match_data.get('set2_tiebreak_player1')
        set2_tb_p2 = match_data.get('set2_tiebreak_player2')

        set3_p1 = match_data.get('set3_player1')
        set3_p2 = match_data.get('set3_player2')
        set3_tb_p1 = match_data.get('set3_tiebreak_player1')
        set3_tb_p2 = match_data.get('set3_tiebreak_player2')

        set3_stb_p1 = match_data.get('set3_supertiebreak_player1')
        set3_stb_p2 = match_data.get('set3_supertiebreak_player2')


        # --- AMENDMENT (Rules.md): STATUS_RETIRED can occur in Set 1, Set 2, or Set 3 (incl. TB / STB) ---
        if match_status_id in (self.STATUS_RETIRED, self.STATUS_DISQUALIFIED):
            # Basic presence checks
            if set1_p1 is None or set1_p2 is None:
                errors.append("Retired match must have Set 1 score values")
                return (len(errors) == 0, errors)

            # Set 3 format cannot be both normal-set and super tie-break
            has_any_set3_normal = (set3_p1 is not None) or (set3_p2 is not None) or (set3_tb_p1 is not None) or (set3_tb_p2 is not None)
            has_any_set3_stb = (set3_stb_p1 is not None) or (set3_stb_p2 is not None)
            if has_any_set3_normal and has_any_set3_stb:
                errors.append("Set 3 cannot have both normal set and super tie-break")
                return (len(errors) == 0, errors)

            # Helper: validate a set that may be completed OR partial OR retired-during-tiebreak (6-6 + partial/complete TB)
            def _validate_set_for_retirement(label: str, g1, g2, tb1, tb2) -> Tuple[bool, bool]:
                """
                Returns: (set_is_present, set_is_partial_or_incomplete)
                """
                # Absent set
                if g1 is None and g2 is None:
                    if tb1 is not None or tb2 is not None:
                        errors.append(f"{label} tie-break values require {label} games")
                    return False, False

                # Half-present set
                if (g1 is None) != (g2 is None):
                    errors.append(f"{label} must have both game values or be NULL")
                    return True, True

                # Completed set score
                if self.validate_set_score(g1, g2):
                    if self.requires_tiebreak(g1, g2):
                        if tb1 is None or tb2 is None:
                            errors.append(f"{label} score {g1}-{g2} requires tie-break")
                            return True, True
                        if not self.validate_tiebreak_score(tb1, tb2):
                            errors.append(f"Invalid {label} tie-break: {tb1}-{tb2}")
                            return True, True
                    else:
                        if tb1 is not None or tb2 is not None:
                            errors.append(f"{label} score {g1}-{g2} should not have tie-break")
                            return True, True
                    return True, False

                # Partial set score (retired mid-set)
                if self.validate_partial_set_score(g1, g2):
                    if tb1 is not None or tb2 is not None:
                        errors.append(f"{label} partial score {g1}-{g2} must not have tie-break")
                    return True, True

                # Retired during tie-break: allow 6-6 with partial/complete tie-break points
                if g1 == 6 and g2 == 6:
                    if tb1 is None or tb2 is None:
                        errors.append(f"{label} score 6-6 requires tie-break points for retired match")
                        return True, True
                    if not (self.validate_tiebreak_score(tb1, tb2) or self.validate_partial_tiebreak_score(tb1, tb2)):
                        errors.append(f"Invalid {label} tie-break: {tb1}-{tb2}")
                    return True, True

                errors.append(f"Invalid {label} score for retired match: {g1}-{g2}")
                return True, True

            # Validate Set 1 and Set 2
            set1_present, set1_incomplete = _validate_set_for_retirement("Set 1", set1_p1, set1_p2, set1_tb_p1, set1_tb_p2)
            set2_present, set2_incomplete = _validate_set_for_retirement("Set 2", set2_p1, set2_p2, set2_tb_p1, set2_tb_p2)

            # Validate Set 3 (either normal-set or super tie-break)
            set3_present = False
            set3_incomplete = False

            if has_any_set3_stb:
                if (set3_stb_p1 is None) != (set3_stb_p2 is None):
                    errors.append("Set 3 super tie-break must have both point values or be NULL")
                    set3_present = True
                    set3_incomplete = True
                else:
                    set3_present = True
                    # completed OR partial STB
                    if self.validate_supertiebreak_score(set3_stb_p1, set3_stb_p2):
                        set3_incomplete = False
                    elif self.validate_partial_supertiebreak_score(set3_stb_p1, set3_stb_p2):
                        set3_incomplete = True
                    else:
                        errors.append(f"Invalid Set 3 super tie-break: {set3_stb_p1}-{set3_stb_p2}")
                        set3_incomplete = True
            else:
                set3_present, set3_incomplete = _validate_set_for_retirement("Set 3", set3_p1, set3_p2, set3_tb_p1, set3_tb_p2)

            # Enforce “no play after retirement”: once an incomplete set exists, later sets must be absent
            if set1_incomplete and (set2_present or set3_present):
                errors.append("Retired in Set 1: Set 2 and Set 3 must be NULL")
            if (not set1_incomplete) and set2_incomplete and set3_present:
                errors.append("Retired in Set 2: Set 3 must be NULL")

            # Ensure it is genuinely a retirement pattern (at least one incomplete set or truncated match)
            if not (set1_incomplete or set2_incomplete or set3_incomplete):
                # Allow “truncated” retirement: e.g., only Set 1 present, Set 2 NULL
                if set2_present:
                    # Set 1 and Set 2 both completed and no Set 3: this looks like a completed match
                    errors.append("Retired match must contain an incomplete set/tie-break or truncated later sets")

            return (len(errors) == 0, errors)


        # Validate Set 1 if present
        if set1_p1 is not None and set1_p2 is not None:
            if not self.validate_set_score(set1_p1, set1_p2):
                errors.append(f"Invalid Set 1 score: {set1_p1}-{set1_p2}")

            # Set 1 tie-break validation
            if self.requires_tiebreak(set1_p1, set1_p2):
                if set1_tb_p1 is None or set1_tb_p2 is None:
                    errors.append(f"Set 1 score {set1_p1}-{set1_p2} requires tie-break")
                elif not self.validate_tiebreak_score(set1_tb_p1, set1_tb_p2):
                    errors.append(f"Invalid Set 1 tie-break: {set1_tb_p1}-{set1_tb_p2}")
            else:
                if set1_tb_p1 is not None or set1_tb_p2 is not None:
                    errors.append(f"Set 1 score {set1_p1}-{set1_p2} should not have tie-break")

        # Validate Set 2 if present
        if set2_p1 is not None and set2_p2 is not None:
            if not self.validate_set_score(set2_p1, set2_p2):
                errors.append(f"Invalid Set 2 score: {set2_p1}-{set2_p2}")

            # Set 2 tie-break validation
            if self.requires_tiebreak(set2_p1, set2_p2):
                if set2_tb_p1 is None or set2_tb_p2 is None:
                    errors.append(f"Set 2 score {set2_p1}-{set2_p2} requires tie-break")
                elif not self.validate_tiebreak_score(set2_tb_p1, set2_tb_p2):
                    errors.append(f"Invalid Set 2 tie-break: {set2_tb_p1}-{set2_tb_p2}")
            else:
                if set2_tb_p1 is not None or set2_tb_p2 is not None:
                    errors.append(f"Set 2 score {set2_p1}-{set2_p2} should not have tie-break")

        # Third set required when sets are split (for completed matches only)
        if match_status_id == self.STATUS_COMPLETED:
            if self.sets_are_split(set1_p1, set1_p2, set2_p1, set2_p2):
                has_normal_set3 = set3_p1 is not None and set3_p2 is not None
                has_supertiebreak = set3_stb_p1 is not None and set3_stb_p2 is not None

                if not has_normal_set3 and not has_supertiebreak:
                    errors.append("Third set required when first two sets are split")

                # Set 3 format must be EITHER normal OR super tie-break
                if has_normal_set3 and has_supertiebreak:
                    errors.append("Set 3 cannot have both normal set and super tie-break")

        # Validate Set 3 if present
        if set3_p1 is not None and set3_p2 is not None:
            if not self.validate_set_score(set3_p1, set3_p2):
                errors.append(f"Invalid Set 3 score: {set3_p1}-{set3_p2}")

            # Set 3 tie-break validation
            if self.requires_tiebreak(set3_p1, set3_p2):
                if set3_tb_p1 is None or set3_tb_p2 is None:
                    errors.append(f"Set 3 score {set3_p1}-{set3_p2} requires tie-break")
                elif not self.validate_tiebreak_score(set3_tb_p1, set3_tb_p2):
                    errors.append(f"Invalid Set 3 tie-break: {set3_tb_p1}-{set3_tb_p2}")

        # Validate super tie-break if present
        if set3_stb_p1 is not None and set3_stb_p2 is not None:
            if not self.validate_supertiebreak_score(set3_stb_p1, set3_stb_p2):
                errors.append(f"Invalid super tie-break: {set3_stb_p1}-{set3_stb_p2}")

        return (len(errors) == 0, errors)

    @staticmethod
    def validate_player_schedule(matches: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Validate that no player has 2 matches on the same day.

        Args:
            matches: List of all match records

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        player_dates = {}  # {(player_id, match_date): count}

        for match in matches:
            match_date = match.get('match_date')
            player1_id = match.get('player1_id')
            player2_id = match.get('player2_id')

            if not match_date or not player1_id or not player2_id:
                continue

            # Track player1
            key1 = (player1_id, match_date)
            player_dates[key1] = player_dates.get(key1, 0) + 1

            # Track player2
            key2 = (player2_id, match_date)
            player_dates[key2] = player_dates.get(key2, 0) + 1

        # Check for violations
        for (player_id, match_date), count in player_dates.items():
            if count > 1:
                errors.append(
                    f"Player {player_id} has {count} matches on {match_date} "
                    f"(max 1 per day)"
                )

        return (len(errors) == 0, errors)

    @staticmethod
    def validate_round_progression(matches: List[Dict], draw_size: int) -> Tuple[bool, List[str]]:
        """
        Validate that match round progression follows bracket structure.

        Args:
            matches: List of match records
            draw_size: Number of players in draw

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Expected number of matches per round for each draw size
        expected_matches = {
            8: {4: 4, 5: 2, 6: 1},  # QF=4, SF=2, F=1
            16: {3: 8, 4: 4, 5: 2, 6: 1},  # R16=8, QF=4, SF=2, F=1
            32: {2: 16, 3: 8, 4: 4, 5: 2, 6: 1},  # R32=16, etc.
            64: {1: 32, 2: 16, 3: 8, 4: 4, 5: 2, 6: 1}  # R64=32, etc.
        }

        if draw_size not in expected_matches:
            errors.append(f"Unsupported draw size for validation: {draw_size}")
            return False, errors

        expected = expected_matches[draw_size]

        # Count matches by round
        round_counts = {}
        for match in matches:
            round_id = match.get('round_id')
            if round_id:
                round_counts[round_id] = round_counts.get(round_id, 0) + 1

        # Validate counts
        for round_id, expected_count in expected.items():
            actual_count = round_counts.get(round_id, 0)
            if actual_count != expected_count:
                errors.append(
                    f"Round {round_id}: expected {expected_count} matches, got {actual_count}"
                )

        return (len(errors) == 0, errors)


def main():
    """Run validation tests with sample match data."""
    validator = TennisMatchValidator()

    print("=" * 70)
    print("TENNIS MATCH VALIDATION TESTS")
    print("=" * 70)

    # Test 1: Valid completed match (2 sets)
    print("\nTest 1: Valid completed match (2 sets)")
    match1 = {
        'match_status_id': 2,
        'set1_player1': 6, 'set1_player2': 3,
        'set2_player1': 6, 'set2_player2': 4,
        'set1_tiebreak_player1': None, 'set1_tiebreak_player2': None,
        'set2_tiebreak_player1': None, 'set2_tiebreak_player2': None,
        'set3_player1': None, 'set3_player2': None,
        'set3_tiebreak_player1': None, 'set3_tiebreak_player2': None,
        'set3_supertiebreak_player1': None, 'set3_supertiebreak_player2': None
    }
    valid, errors = validator.validate_match(match1)
    print(f"Valid: {valid}")
    if errors:
        print(f"Errors: {errors}")

    # Test 2: Valid completed match (tie-break)
    print("\nTest 2: Valid completed match (tie-break)")
    match2 = {
        'match_status_id': 2,
        'set1_player1': 7, 'set1_player2': 6,
        'set1_tiebreak_player1': 7, 'set1_tiebreak_player2': 5,
        'set2_player1': 6, 'set2_player2': 2,
        'set2_tiebreak_player1': None, 'set2_tiebreak_player2': None,
        'set3_player1': None, 'set3_player2': None,
        'set3_tiebreak_player1': None, 'set3_tiebreak_player2': None,
        'set3_supertiebreak_player1': None, 'set3_supertiebreak_player2': None
    }
    valid, errors = validator.validate_match(match2)
    print(f"Valid: {valid}")
    if errors:
        print(f"Errors: {errors}")

    # Test 3: Invalid score (6-5)
    print("\nTest 3: Invalid score (6-5)")
    match3 = {
        'match_status_id': 2,
        'set1_player1': 6, 'set1_player2': 5,
        'set2_player1': 6, 'set2_player2': 4,
        'set1_tiebreak_player1': None, 'set1_tiebreak_player2': None,
        'set2_tiebreak_player1': None, 'set2_tiebreak_player2': None,
        'set3_player1': None, 'set3_player2': None,
        'set3_tiebreak_player1': None, 'set3_tiebreak_player2': None,
        'set3_supertiebreak_player1': None, 'set3_supertiebreak_player2': None
    }
    valid, errors = validator.validate_match(match3)
    print(f"Valid: {valid}")
    if errors:
        print(f"Errors: {errors}")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    main()
