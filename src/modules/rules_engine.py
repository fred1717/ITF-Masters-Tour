"""
rules_engine.py

Single source of truth for all tournament generation rules.
All probabilities, timings, and constraints MUST be defined here.
No generator, recalculation, or validation script may hardcode rules.

Authoritative source: Rules.md (most recent upload).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Tuple, Optional, List, Iterable, Any
import random


# ============================================================
# TIME (UTC)
# ============================================================

UTC = timezone.utc

ENTRY_DEADLINE_WEEKDAY = 1            # Tuesday
ENTRY_DEADLINE_TIME = time(10, 0)     # 10:00 UTC

DRAW_PUBLICATION_WEEKDAY = 4          # Friday
DRAW_PUBLICATION_TIME = time(19, 0)   # 19:00 UTC

RANKING_PUBLICATION_WEEKDAY = 0       # Monday
RANKING_PUBLICATION_TIME = time(20, 0)  # 20:00 UTC


# ============================================================
# MATCH OUTCOMES / CONSTRAINTS
# ============================================================

BETTER_RANKED_WIN_PROBABILITY = 2 / 3

THIRD_SET_PROBABILITY = 0.25
SET_TIEBREAK_PROBABILITY = 0.10

# When a third set is required, a super tie-break is used in 75% of cases (Rules.md)
THIRD_SET_SUPER_TB_RATE = 0.75

DEFAULT_PRE_DRAW_PROBABILITY = 0.001   # 0.1%
DEFAULT_POST_DRAW_PROBABILITY = 0.005  # 0.5%

NO_PLAYER_TWO_MATCHES_SAME_DAY = True


# ============================================================
# SCORE DISTRIBUTIONS (Rules.md)
# ============================================================

# Normal (non tie-break) set score distribution
NORMAL_SET_SCORES: Dict[str, float] = {
    "6-3": 0.30,
    "6-4": 0.25,
    "7-5": 0.20,
    "6-2": 0.10,
    "6-1": 0.10,
    "6-0": 0.09,
    "RET": 0.01,
}

# Tie-break: 80% end at 7-x, 20% go beyond (tied 6-6)
TIEBREAK_NORMAL_PROBABILITY = 0.80
TIEBREAK_DEUCE_PROBABILITY = 0.20

TIEBREAK_NORMAL_SCORES: Dict[str, float] = {
    "7-4": 0.30,
    "7-3": 0.25,
    "7-5": 0.20,
    "7-2": 0.15,
    "7-1": 0.10,
    "7-0": 0.10,
}

TIEBREAK_DEUCE_SCORES: Dict[str, float] = {
    "8-6": 0.25,
    "9-7": 0.20,
    "10-8": 0.15,
    "11-9": 0.10,
    "12-10": 0.10,
    "13-11": 0.10,
    "14-12": 0.05,
    "15-13": 0.05,
}

# Super tie-break: 80% end at 10-x, 20% go beyond (tied 9-9)
SUPER_TIEBREAK_NORMAL_PROBABILITY = 0.80
SUPER_TIEBREAK_DEUCE_PROBABILITY = 0.20

SUPER_TIEBREAK_NORMAL_SCORES: Dict[str, float] = {
    "10-7": 0.25,
    "10-6": 0.20,
    "10-8": 0.15,
    "10-5": 0.10,
    "10-4": 0.10,
    "10-3": 0.10,
    "10-2": 0.06,
    "10-1": 0.03,
    "10-0": 0.01,
}

SUPER_TIEBREAK_DEUCE_SCORES: Dict[str, float] = {
    "11-9": 0.25,
    "12-10": 0.20,
    "13-11": 0.15,
    "14-12": 0.10,
    "15-13": 0.10,
    "16-14": 0.10,
    "17-15": 0.05,
    "18-16": 0.05,
}


# ============================================================
# DRAW / SEEDING (Rules.md)
# ============================================================

MIN_DRAW_SIZE = 6
MAX_DRAW_SIZE = 64

# Draw size is predetermined in Draws.num_players (no power-of-two forcing)
POWER_OF_TWO_NOT_REQUIRED = True

# Seeding rule update: tournament_id 1 and 2 are not seeded; first seeding is tournament_id 3
UNSEEDED_TOURNAMENT_IDS = {1, 2}
FIRST_SEEDED_TOURNAMENT_ID = 3


# Super tie-break usage is deterministic per category, not random.
# The mapping keys are (age_category_id, gender_id).
# Values must match Rules.md precisely; adjust IDs to match AgeCategory.csv and Gender.csv.
#
# Placeholder mapping below reflects the earlier rule described in Rules.md discussions:
# - Men's +60: normal third set
# - all other listed categories: super tie-break
#
# IMPORTANT: if AgeCategory.csv uses different IDs/order, update the keys accordingly.
HAS_SUPER_TIEBREAK_BY_CATEGORY: Dict[Tuple[int, int], bool] = {
    (1, 1): False,  # Men +60
    (2, 1): True,   # Men +65
    (1, 2): True,   # Ladies +60
    (2, 2): True,   # Ladies +65
}


# ============================================================
# RANKING (Rules.md)
# ============================================================

ROLLING_WEEKS = 52
BEST_RESULTS_COUNTED = 4

RANKING_START_YEAR = 2025
RANKING_START_WEEK = 3

RANKING_END_YEAR = 2026
RANKING_END_WEEK = 6


# ============================================================
# DISCIPLINE / SUSPENSIONS (Rules.md)
# ============================================================

NO_SHOW_SUSPENSION_MONTHS = 2
DISQUALIFICATION_SUSPENSION_MONTHS = 6

ZERO_POINTS_IF_FIRST_MATCH_LOST = True


# ============================================================
# PURE HELPERS
# ============================================================

class RuleError(ValueError):
    pass


# ============================================================
# ELIGIBILITY (Rules.md)
# ============================================================

@dataclass(frozen=True)
class AgeCategoryRule:
    age_category_id: int
    min_age: int
    max_age: int


def age_category_rules_from_rows(rows) -> Tuple[AgeCategoryRule, ...]:
    """
    Convert DB/CSV rows into AgeCategoryRule objects.

    Expected keys per row:
      - age_category_id
      - min_age
      - max_age
    """
    out: list[AgeCategoryRule] = []
    for r in rows:
        out.append(
            AgeCategoryRule(
                age_category_id=int(r["age_category_id"]),
                min_age=int(r["min_age"]),
                max_age=int(r["max_age"]),
            )
        )
    return tuple(out)


def age_in_competition_year(birth_year: int, tournament_year: int) -> int:
    """
    Age is evaluated within the tournament's calendar year.
    Example: tournament_year=2026, birth_year=1966 => age=60.
    """
    if birth_year is None:
        raise RuleError("birth_year is required")
    return int(tournament_year) - int(birth_year)


def eligible_age_categories(
    *,
    birth_year: int,
    tournament_year: int,
    categories: Tuple[AgeCategoryRule, ...],
) -> Tuple[AgeCategoryRule, ...]:
    """
    Return all categories the player may enter for the tournament year.
    - Must satisfy min_age
    - Must satisfy max_age if max_age is defined
    """
    age = age_in_competition_year(birth_year, tournament_year)

    eligible: list[AgeCategoryRule] = []
    for c in categories:
        if age < int(c.min_age):
            continue
        if age > int(c.max_age):
            continue
        eligible.append(c)

    return tuple(eligible)


def required_age_category_id(
    *,
    birth_year: int,
    tournament_year: int,
    categories: Tuple[AgeCategoryRule, ...],
) -> int:
    """
    Rules.md: if eligible for a higher age group, entry in a lower age category is not allowed.
    This returns the highest eligible category by min_age.
    """
    eligible = eligible_age_categories(
        birth_year=int(birth_year),
        tournament_year=int(tournament_year),
        categories=categories,
    )
    if not eligible:
        raise RuleError("No eligible age category for the player in the tournament year")

    highest = max(eligible, key=lambda c: int(c.min_age))
    return int(highest.age_category_id)

# ============================================================
# SUSPENSIONS (Rules.md)
# ============================================================

# ============================================================
# SUSPENSIONS (Rules.md)
# ============================================================

def is_player_suspended(
    *,
    player_id: int,
    at_dt: datetime,
    suspensions: Iterable[Dict[str, Any]],
) -> bool:
    """Return True if player_id is suspended at the given datetime.

    Input records (PlayerSuspensions) are expected to contain:
    - player_id
    - suspension_start_date
    - suspension_end_date

    The comparison is inclusive on both ends.
    """
    pid = int(player_id)
    for s in suspensions:
        if int(s.get("player_id")) != pid:
            continue

        start = s.get("suspension_start")
        end = s.get("suspension_end")

        if start is None or end is None:
            continue

        # Accept date or datetime in inputs
        if isinstance(start, datetime):
            start_dt = start
        else:
            start_dt = datetime.combine(start, time(0, 0), tzinfo=UTC)

        if isinstance(end, datetime):
            end_dt = end
        else:
            end_dt = datetime.combine(end, time(23, 59, 59), tzinfo=UTC)

        # Normalise at_dt to UTC if naive
        at_utc = at_dt if at_dt.tzinfo else at_dt.replace(tzinfo=UTC)

        if start_dt <= at_utc <= end_dt:
            return True

    return False


def enforce_superior_age_group_exclusion(
    *,
    birth_year: int,
    tournament_year: int,
    requested_age_category_id: int,
    categories: Tuple[AgeCategoryRule, ...],
) -> bool:
    """Rules.md: if eligible for a superior age group, lower category entry is forbidden.

    Returns True if the player is allowed to enter requested_age_category_id,
    otherwise False.

    Raises RuleError if no eligible category exists.
    """
    required_id = required_age_category_id(
        birth_year=birth_year,
        tournament_year=tournament_year,
        categories=categories,
    )
    return int(required_id) == int(requested_age_category_id)


def _validate_weight_map(name: str, weight_map: Dict[str, float]) -> None:
    if not weight_map:
        raise RuleError(f"{name}: empty weight map")

    total = 0.0
    for k, w in weight_map.items():
        if w is None or w < 0:
            raise RuleError(f"{name}: invalid weight for {k!r}: {w!r}")
        total += float(w)

    if total <= 0.0:
        raise RuleError(f"{name}: sum of weights must be > 0, got {total}")

    # Tolerance is intentionally loose; Rules.md values are treated as the source of truth.
    # This check exists to catch omissions/typos early.
    if abs(total - 1.0) > 1e-6:
        raise RuleError(f"{name}: weights must sum to 1.0, got {total}")


def validate_all_rules() -> None:
    """
    Call once at script startup to fail fast if Rules.md-to-code transcription is broken.
    """
    _validate_weight_map("NORMAL_SET_SCORES", NORMAL_SET_SCORES)
    _validate_weight_map("TIEBREAK_NORMAL_SCORES", TIEBREAK_NORMAL_SCORES)
    _validate_weight_map("TIEBREAK_DEUCE_SCORES", TIEBREAK_DEUCE_SCORES)
    _validate_weight_map("SUPER_TIEBREAK_NORMAL_SCORES", SUPER_TIEBREAK_NORMAL_SCORES)
    _validate_weight_map("SUPER_TIEBREAK_DEUCE_SCORES", SUPER_TIEBREAK_DEUCE_SCORES)

    if abs((TIEBREAK_NORMAL_PROBABILITY + TIEBREAK_DEUCE_PROBABILITY) - 1.0) > 1e-12:
        raise RuleError("Tie-break normal/deuce probabilities must sum to 1.0")

    if abs((SUPER_TIEBREAK_NORMAL_PROBABILITY + SUPER_TIEBREAK_DEUCE_PROBABILITY) - 1.0) > 1e-12:
        raise RuleError("Super tie-break normal/deuce probabilities must sum to 1.0")

    if THIRD_SET_SUPER_TB_RATE < 0.0 or THIRD_SET_SUPER_TB_RATE > 1.0:
        raise RuleError("Third-set super tie-break rate must be in [0,1]")

    if FIRST_SEEDED_TOURNAMENT_ID in UNSEEDED_TOURNAMENT_IDS:
        raise RuleError("FIRST_SEEDED_TOURNAMENT_ID cannot be in UNSEEDED_TOURNAMENT_IDS")


def weighted_choice(weight_map: Dict[str, float], rng: Optional[random.Random] = None) -> str:
    values = list(weight_map.keys())
    weights = list(weight_map.values())
    r = rng or random
    return r.choices(values, weights=weights, k=1)[0]


def bernoulli(p: float, rng: Optional[random.Random] = None) -> bool:
    if p < 0.0 or p > 1.0:
        raise RuleError(f"Probability must be in [0,1], got {p}")
    r = rng or random
    return r.random() < p


def should_seed_tournament(tournament_id: int) -> bool:
    """
    Implements the Rules.md update:
    - tournament_id 1 and 2: NOT seeded
    - first seeded tournament: tournament_id 3
    """
    if tournament_id in UNSEEDED_TOURNAMENT_IDS:
        return False
    return tournament_id >= FIRST_SEEDED_TOURNAMENT_ID


def has_super_tiebreak(age_category_id: int, gender_id: int) -> bool:
    """
    Deterministic third-set format based on category mapping from Rules.md.
    """
    key = (age_category_id, gender_id)
    if key not in HAS_SUPER_TIEBREAK_BY_CATEGORY:
        raise RuleError(f"No has_super_tiebreak rule for age_category_id={age_category_id}, gender_id={gender_id}")
    return HAS_SUPER_TIEBREAK_BY_CATEGORY[key]


def is_default(pre_draw: bool, rng: Optional[random.Random] = None) -> bool:
    prob = DEFAULT_PRE_DRAW_PROBABILITY if pre_draw else DEFAULT_POST_DRAW_PROBABILITY
    return bernoulli(prob, rng=rng)


def better_ranked_wins(rng: Optional[random.Random] = None) -> bool:
    return bernoulli(BETTER_RANKED_WIN_PROBABILITY, rng=rng)


def is_third_set_played(rng: Optional[random.Random] = None) -> bool:
    return bernoulli(THIRD_SET_PROBABILITY, rng=rng)


def is_third_set_super_tiebreak(rng: Optional[random.Random] = None) -> bool:
    """Rules.md: when a third set is required, use a super tie-break in 75% of cases."""
    return bernoulli(THIRD_SET_SUPER_TB_RATE, rng=rng)


def is_set_tiebreak(rng: Optional[random.Random] = None) -> bool:
    return bernoulli(SET_TIEBREAK_PROBABILITY, rng=rng)


def sample_normal_set_score(rng: Optional[random.Random] = None) -> str:
    return weighted_choice(NORMAL_SET_SCORES, rng=rng)


def sample_tiebreak_score(rng: Optional[random.Random] = None) -> str:
    if bernoulli(TIEBREAK_NORMAL_PROBABILITY, rng=rng):
        return weighted_choice(TIEBREAK_NORMAL_SCORES, rng=rng)
    return weighted_choice(TIEBREAK_DEUCE_SCORES, rng=rng)


def sample_super_tiebreak_score(rng: Optional[random.Random] = None) -> str:
    if bernoulli(SUPER_TIEBREAK_NORMAL_PROBABILITY, rng=rng):
        return weighted_choice(SUPER_TIEBREAK_NORMAL_SCORES, rng=rng)
    return weighted_choice(SUPER_TIEBREAK_DEUCE_SCORES, rng=rng)


def draw_publication_datetime(year: int, iso_week: int) -> datetime:
    """
    Friday 19:00 UTC of ISO week.
    """
    monday = datetime.fromisocalendar(year, iso_week, 1).replace(tzinfo=UTC)
    friday = monday + timedelta(days=DRAW_PUBLICATION_WEEKDAY)
    return datetime.combine(friday.date(), DRAW_PUBLICATION_TIME, tzinfo=UTC)


def ranking_publication_datetime(year: int, iso_week: int) -> datetime:
    """
    Monday 20:00 UTC of ISO week.
    """
    monday = datetime.fromisocalendar(year, iso_week, 1).replace(tzinfo=UTC)
    return datetime.combine(monday.date(), RANKING_PUBLICATION_TIME, tzinfo=UTC)


def entry_deadline_datetime(year: int, iso_week: int) -> datetime:
    """
    Tuesday 10:00 UTC of ISO week (the entry deadline for that tournament week, per Rules.md).
    """
    monday = datetime.fromisocalendar(year, iso_week, 1).replace(tzinfo=UTC)
    tuesday = monday + timedelta(days=ENTRY_DEADLINE_WEEKDAY)
    return datetime.combine(tuesday.date(), ENTRY_DEADLINE_TIME, tzinfo=UTC)
