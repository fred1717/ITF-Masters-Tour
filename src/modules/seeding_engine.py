"""
Seeding engine
==============

Single source of truth for all draw seeding logic.

Implements:
- Planned seeding at entry deadline (is_actual_seeding = FALSE)
- Conditional actual seeding after pre-draw withdrawals (is_actual_seeding = TRUE)
- Audit trail between planned and actual seeding

Authoritative source: Rules.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass(frozen=True)
class SeedAssignment:
    player_id: int
    seed_number: int
    is_actual_seeding: bool


# ============================================================
# SEEDING RULES (Rules.md)
# ============================================================

def seeds_for_draw_size(draw_size: int) -> int:
    """
    Number of seeds per draw size (Rules.md).

    Examples:
    - 6–8 players  -> 2 seeds
    - 9–16 players  -> 4 seeds
    - 17–32 players -> 8 seeds
    - 33–64 players -> 16 seeds
    """
    if draw_size < 6:
        raise ValueError(f"Invalid draw_size={draw_size}: draws below 6 players are cancelled per Rules.md")
    if draw_size <= 8:
        return 2
    if draw_size <= 16:
        return 4
    if draw_size <= 32:
        return 8
    return 16


# ============================================================
# CORE ENGINE
# ============================================================

def compute_planned_seeding(
    player_ranking_positions: Dict[int, int],
    draw_size: int,
) -> List[SeedAssignment]:
    """
    Compute planned seeding at entry deadline.

    All returned rows have is_actual_seeding = FALSE.
    """
    seed_count = seeds_for_draw_size(draw_size)
    if seed_count == 0:
        return []

    ranked_players = sorted(
        player_ranking_positions.items(),
        key=lambda x: x[1],  # lower ranking position = better rank
    )

    seeds: List[SeedAssignment] = []
    for i, (player_id, _) in enumerate(ranked_players[:seed_count], start=1):
        seeds.append(
            SeedAssignment(
                player_id=player_id,
                seed_number=i,
                is_actual_seeding=False,
            )
        )

    return seeds


def compute_actual_seeding_after_withdrawal(
    planned_seeds: Sequence[SeedAssignment],
    withdrawn_player_id: int,
    player_ranking_positions: Dict[int, int],
    draw_size: int,
) -> Optional[List[SeedAssignment]]:
    """
    Compute adjusted seeding after a pre-draw withdrawal (0.1% event).

    Rules.md:
    - Recompute seeding ONLY IF the withdrawn player would have been seeded.
    - If withdrawn player was unseeded → no actual seeding snapshot is produced.
    """
    seed_count = seeds_for_draw_size(draw_size)
    if seed_count == 0:
        return None

    planned_seeded_players = {s.player_id for s in planned_seeds}

    # Withdrawal does NOT affect seeding
    if withdrawn_player_id not in planned_seeded_players:
        return None

    # Remove withdrawn player and recompute seeds
    remaining_players = {
        pid: rank
        for pid, rank in player_ranking_positions.items()
        if pid != withdrawn_player_id
    }

    ranked_remaining = sorted(
        remaining_players.items(),
        key=lambda x: x[1],
    )

    actual_seeds: List[SeedAssignment] = []
    for i, (player_id, _) in enumerate(ranked_remaining[:seed_count], start=1):
        actual_seeds.append(
            SeedAssignment(
                player_id=player_id,
                seed_number=i,
                is_actual_seeding=True,
            )
        )

    return actual_seeds
