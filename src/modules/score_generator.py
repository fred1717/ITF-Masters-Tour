"""
score_generator.py

Score generation strictly driven by Rules.md via rules_engine.

This module generates:
- Completed matches (status_id=2): only valid completed set scores
- Retired matches (status_id=4): allows partial scoring in the retirement set
  (e.g., set1 partial like 1-0 OR set1 complete then set2 partial like 4-3),
  and NO later sets after retirement.

No database access.
No ranking logic (winner bias handled upstream).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import random

from src.modules import rules_engine as R

ScoreFields = Dict[str, Optional[int]]

def _blank_score_fields() -> ScoreFields:
    return {
        "set1_player1": None, "set1_player2": None,
        "set1_tiebreak_player1": None, "set1_tiebreak_player2": None,

        "set2_player1": None, "set2_player2": None,
        "set2_tiebreak_player1": None, "set2_tiebreak_player2": None,

        "set3_player1": None, "set3_player2": None,
        "set3_tiebreak_player1": None, "set3_tiebreak_player2": None,

        "set3_supertiebreak_player1": None, "set3_supertiebreak_player2": None,
    }

def _parse_pair(s: str) -> Tuple[int, int]:
    a, b = s.split("-")
    return int(a), int(b)

def _winner_slot_from_games(g1: int, g2: int) -> int:
    return 1 if g1 > g2 else 2

def _normal_set_weights_excluding_ret() -> Dict[str, float]:
    w = dict(R.NORMAL_SET_SCORES)
    w.pop("RET", None)
    total = float(sum(w.values()))
    return {k: float(v) / total for k, v in w.items()}

def _sample_completed_normal_set(rng: random.Random) -> Tuple[int, int]:
    score = R.weighted_choice(_normal_set_weights_excluding_ret(), rng=rng)
    return _parse_pair(score)

def _sample_completed_tiebreak_set(rng: random.Random) -> Tuple[int, int, int, int]:
    """Completed 7-6 set with normal tie-break points (Rules.md weights).

    The tie-break points are sampled from Rules.md distribution (via rules_engine),
    and the winner side is randomised to avoid always making player1 the set winner.
    """
    tb = R.sample_tiebreak_score(rng=rng)  # e.g. "7-4", "10-8"
    w_pts, l_pts = _parse_pair(tb)

    # Randomise which player wins this set while keeping the same TB points distribution
    if rng.random() < 0.5:
        # player1 wins set 7-6
        return 7, 6, w_pts, l_pts
    # player2 wins set 6-7 (swap TB points)
    return 6, 7, l_pts, w_pts

def _is_finished_set_score(g1: int, g2: int) -> bool:
    finished = {
        (6, 0), (6, 1), (6, 2), (6, 3), (6, 4),
        (0, 6), (1, 6), (2, 6), (3, 6), (4, 6),
        (7, 5), (5, 7),
        (7, 6), (6, 7),
    }
    return (g1, g2) in finished

def _sample_partial_set_score(rng: random.Random) -> Tuple[int, int]:
    """
    Partial (incomplete) set score for retired matches.

    Allowed:
    - integers 0..6
    - not equal
    - not (6,6)
    - not a finished set score (so 6-3 is excluded; 4-3 is allowed)
    """
    while True:
        g1 = rng.randint(0, 6)
        g2 = rng.randint(0, 6)
        if g1 == g2:
            continue
        if g1 == 6 and g2 == 6:
            continue
        if _is_finished_set_score(g1, g2):
            continue
        return g1, g2

def _sample_partial_tiebreak_points(rng: random.Random) -> Tuple[int, int]:
    """
    Partial (incomplete) tie-break points for retired matches.

    Allowed:
    - non-negative integers
    - not equal
    - not a completed tie-break score (>=7 and win by 2)
    """
    while True:
        p1 = rng.randint(0, 12)
        p2 = rng.randint(0, 12)
        if p1 == p2:
            continue
        # Exclude completed tie-break outcomes (>=7, win by 2)
        if max(p1, p2) >= 7 and abs(p1 - p2) >= 2:
            continue
        return p1, p2

def _sample_partial_supertiebreak_points(rng: random.Random) -> Tuple[int, int]:
    """
    Partial (incomplete) super tie-break points for retired matches.

    Allowed:
    - non-negative integers
    - not equal
    - not a completed super tie-break score (>=10 and win by 2)
    """
    while True:
        p1 = rng.randint(0, 18)
        p2 = rng.randint(0, 18)
        if p1 == p2:
            continue
        # Exclude completed super tie-break outcomes (>=10, win by 2)
        if max(p1, p2) >= 10 and abs(p1 - p2) >= 2:
            continue
        return p1, p2

@dataclass
class GeneratedMatch:
    score: ScoreFields
    winner_slot: int  # 1 or 2

class ScoreGenerator:
    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    # ----------------------------
    # Completed match (status=2)
    # ----------------------------
    def generate_completed_match(self, *, has_supertiebreak: bool) -> GeneratedMatch:
        score = _blank_score_fields()

        wins1 = 0
        wins2 = 0

        # Set 1
        self._fill_completed_set(score, set_no=1)
        w = _winner_slot_from_games(score["set1_player1"], score["set1_player2"])  # type: ignore[arg-type]
        wins1 += 1 if w == 1 else 0
        wins2 += 1 if w == 2 else 0

        # Set 2
        self._fill_completed_set(score, set_no=2)
        w = _winner_slot_from_games(score["set2_player1"], score["set2_player2"])  # type: ignore[arg-type]
        wins1 += 1 if w == 1 else 0
        wins2 += 1 if w == 2 else 0

        if wins1 == 2:
            return GeneratedMatch(score=score, winner_slot=1)
        if wins2 == 2:
            return GeneratedMatch(score=score, winner_slot=2)

        # Split sets -> third set required
        # Rules.md: when a third set is required, use a super tie-break in 75% of cases.
        # Rules.md: has_supertiebreak is deterministic per draw (not random).
        # True = always super tie-break, False = always normal 3rd set.
        if has_supertiebreak:
            stb = R.sample_super_tiebreak_score(rng=self.rng)  # e.g. "10-7" or "12-10"
            s1, s2 = _parse_pair(stb)
            score["set3_supertiebreak_player1"] = s1
            score["set3_supertiebreak_player2"] = s2
            return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(s1, s2))

        # Otherwise, play a normal third set (completed)
        self._fill_completed_set(score, set_no=3)
        w = _winner_slot_from_games(score["set3_player1"], score["set3_player2"])  # type: ignore[arg-type]
        return GeneratedMatch(score=score, winner_slot=w)

    def _fill_completed_set(self, score: ScoreFields, *, set_no: int) -> None:
        """
        Completed set: either normal or 7-6 with tie-break points, per Rules.md.
        """
        if R.is_set_tiebreak(rng=self.rng):
            g1, g2, tb1, tb2 = _sample_completed_tiebreak_set(self.rng)
            score[f"set{set_no}_player1"] = g1
            score[f"set{set_no}_player2"] = g2
            score[f"set{set_no}_tiebreak_player1"] = tb1
            score[f"set{set_no}_tiebreak_player2"] = tb2
            return

        g1, g2 = _sample_completed_normal_set(self.rng)
        score[f"set{set_no}_player1"] = g1
        score[f"set{set_no}_player2"] = g2

    # ----------------------------
    # Retired match (status=4)
    # ----------------------------
    # ----------------------------
    # Retired match (status=4)
    # ----------------------------
    def generate_retired_match(self, *, has_supertiebreak: bool) -> GeneratedMatch:
        """
        Retired match scoring (Rules.md):
        - Retirement can occur in Set 1, Set 2, OR Set 3.
        - The retirement set may be partial (e.g., 1-0, 4-3).
        - Retirement may occur during a tie-break (6-6 + partial TB points) in any set that uses a normal tie-break.
        - If has_supertiebreak is True, retirement may occur during the Set 3 super tie-break (partial STB points).
        - No play after retirement: later sets must remain NULL.
        - Completed set(s) before retirement are fully valid (including 7-6 with TB points).
        """
        score = _blank_score_fields()

        # Neutral defaults (Rules.md does not mandate retirement timing distribution)
        r = self.rng.random()
        if r < 1/3:
            retire_set = 1
        elif r < 2/3:
            retire_set = 2
        else:
            retire_set = 3

        # Retire in Set 1: partial Set 1 only
        if retire_set == 1:
            # Neutral: 25% chance retirement during tie-break at 6-6, else mid-set
            if self.rng.random() < 0.25:
                score["set1_player1"] = 6
                score["set1_player2"] = 6
                tb1, tb2 = _sample_partial_tiebreak_points(self.rng)
                score["set1_tiebreak_player1"] = tb1
                score["set1_tiebreak_player2"] = tb2
                return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(tb1, tb2))

            g1, g2 = _sample_partial_set_score(self.rng)
            score["set1_player1"] = g1
            score["set1_player2"] = g2
            return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(g1, g2))

        # Retire in Set 2: Set 1 completed, Set 2 partial only
        if retire_set == 2:
            self._fill_completed_set(score, set_no=1)

            if self.rng.random() < 0.25:
                score["set2_player1"] = 6
                score["set2_player2"] = 6
                tb1, tb2 = _sample_partial_tiebreak_points(self.rng)
                score["set2_tiebreak_player1"] = tb1
                score["set2_tiebreak_player2"] = tb2
                return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(tb1, tb2))

            g1, g2 = _sample_partial_set_score(self.rng)
            score["set2_player1"] = g1
            score["set2_player2"] = g2
            return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(g1, g2))

        # Retire in Set 3: Sets 1–2 completed AND split 1–1, then retirement in Set 3
        # Ensure 1–1 after two completed sets (otherwise Set 3 is not reached).
        while True:
            self._fill_completed_set(score, set_no=1)
            self._fill_completed_set(score, set_no=2)

            w1 = _winner_slot_from_games(score["set1_player1"], score["set1_player2"])  # type: ignore[arg-type]
            w2 = _winner_slot_from_games(score["set2_player1"], score["set2_player2"])  # type: ignore[arg-type]
            if w1 != w2:
                break

            score = _blank_score_fields()

        # If third set is a super tie-break, retirement can occur during the STB
        if has_supertiebreak:
            p1, p2 = _sample_partial_supertiebreak_points(self.rng)
            score["set3_supertiebreak_player1"] = p1
            score["set3_supertiebreak_player2"] = p2
            return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(p1, p2))

        # Otherwise, third set is a normal set; retirement can occur mid-set OR during a tie-break.
        if self.rng.random() < 0.25:
            score["set3_player1"] = 6
            score["set3_player2"] = 6
            tb1, tb2 = _sample_partial_tiebreak_points(self.rng)
            score["set3_tiebreak_player1"] = tb1
            score["set3_tiebreak_player2"] = tb2
            return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(tb1, tb2))

        g1, g2 = _sample_partial_set_score(self.rng)
        score["set3_player1"] = g1
        score["set3_player2"] = g2
        return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(g1, g2))

    # ----------------------------
    # Disqualified match (status=6)
    # ----------------------------
    def generate_disqualified_match(self, *, has_supertiebreak: bool) -> GeneratedMatch:
        """
        Disqualification scoring (Rules.md):
        - The match MUST have started in normal conditions (player1 and player2 present).
        - A partial in-progress score MUST be produced (blank scores violate the 'started match' rule).
        - DQ can occur in Set 1, Set 2, OR Set 3.
        - DQ may occur during a tie-break (6-6 + partial TB points) in any set using a normal tie-break.
        - If has_supertiebreak is True, DQ may occur during the Set 3 super tie-break (partial STB points).
        - No play after DQ: later sets must remain NULL.
        """
        score = _blank_score_fields()

        # Neutral defaults: choose the set in which DQ occurs
        r = self.rng.random()
        if r < 1/3:
            dq_set = 1
        elif r < 2/3:
            dq_set = 2
        else:
            dq_set = 3

        def _non_zero_partial_games() -> Tuple[int, int]:
            # Ensure the match has started: exclude 0-0.
            while True:
                g1, g2 = _sample_partial_set_score(self.rng)
                if g1 == 0 and g2 == 0:
                    continue
                return g1, g2

        # DQ in Set 1
        if dq_set == 1:
            if self.rng.random() < 0.20:
                score["set1_player1"] = 6
                score["set1_player2"] = 6
                tb1, tb2 = _sample_partial_tiebreak_points(self.rng)
                score["set1_tiebreak_player1"] = tb1
                score["set1_tiebreak_player2"] = tb2
                return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(tb1, tb2))

            g1, g2 = _non_zero_partial_games()
            score["set1_player1"] = g1
            score["set1_player2"] = g2
            return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(g1, g2))

        # DQ in Set 2 (Set 1 completed, Set 2 partial)
        if dq_set == 2:
            self._fill_completed_set(score, set_no=1)

            if self.rng.random() < 0.20:
                score["set2_player1"] = 6
                score["set2_player2"] = 6
                tb1, tb2 = _sample_partial_tiebreak_points(self.rng)
                score["set2_tiebreak_player1"] = tb1
                score["set2_tiebreak_player2"] = tb2
                return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(tb1, tb2))

            g1, g2 = _non_zero_partial_games()
            score["set2_player1"] = g1
            score["set2_player2"] = g2
            return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(g1, g2))

        # DQ in Set 3 requires 1–1 after two completed sets
        while True:
            self._fill_completed_set(score, set_no=1)
            self._fill_completed_set(score, set_no=2)

            w1 = _winner_slot_from_games(score["set1_player1"], score["set1_player2"])  # type: ignore[arg-type]
            w2 = _winner_slot_from_games(score["set2_player1"], score["set2_player2"])  # type: ignore[arg-type]
            if w1 != w2:
                break

            score = _blank_score_fields()

        if has_supertiebreak and self.rng.random() < 0.25:
            p1, p2 = _sample_partial_supertiebreak_points(self.rng)
            # Ensure STB started
            if p1 == 0 and p2 == 0:
                p1 = 1
            score["set3_supertiebreak_player1"] = p1
            score["set3_supertiebreak_player2"] = p2
            return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(p1, p2))

        if self.rng.random() < 0.20:
            score["set3_player1"] = 6
            score["set3_player2"] = 6
            tb1, tb2 = _sample_partial_tiebreak_points(self.rng)
            score["set3_tiebreak_player1"] = tb1
            score["set3_tiebreak_player2"] = tb2
            return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(tb1, tb2))

        g1, g2 = _non_zero_partial_games()
        score["set3_player1"] = g1
        score["set3_player2"] = g2
        return GeneratedMatch(score=score, winner_slot=_winner_slot_from_games(g1, g2))
