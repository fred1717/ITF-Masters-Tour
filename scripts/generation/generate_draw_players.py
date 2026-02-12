#!/usr/bin/env python3
"""
Generate DrawPlayers rows
=========================

RESPONSIBILITY
--------------
This file generates DrawPlayers rows (placement + byes).

It MUST NOT contain validation helpers or CLI/demo code.
All validation logic is moved to:
    scripts/validation/validate_draw_players.py

Rules enforced here:
- Pre-draw withdrawal: withdrawn player must not be placed.
- Seed snapshot selection: prefer is_actual_seeding=TRUE if present, else planned.
- Seeding placement uses seed_number order (not entry list index).
- Byes are assigned to seeded players first (seed order), then randomly among unseeded.

Author: Malik Hamdane
Date: January 2026
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Tuple, Optional, Sequence

import random


# ============================================================
# CORE HELPERS (existing behaviour preserved)
# ============================================================

def get_standard_seeding_positions(draw_size: int, num_seeds: int, randomize: bool = False) -> List[int]:
    """
    Return standard seed placement positions for a single-elimination draw.

    This function returns draw positions (1-based).

    Example:
    - 8 draw: seed 1 -> 1, seed 2 -> 8
    - 16 draw: seed 1 -> 1, seed 2 -> 16, seed 3 -> 5, seed 4 -> 12
    """
    if num_seeds <= 0:
        return []

    # Canonical ITF-style placements for top seeds, then fill remaining as needed
    standard = {
        2: [1, draw_size],
        4: [1, draw_size, 1 + draw_size // 4, draw_size - draw_size // 4],
        8: [1, draw_size, 1 + draw_size // 4, draw_size - draw_size // 4,
            1 + draw_size // 8, draw_size - draw_size // 8, 1 + (3 * draw_size) // 8, draw_size - (3 * draw_size) // 8],
        16: [1, draw_size],
    }

    if num_seeds in standard and num_seeds != 16:
        positions = standard[num_seeds][:]
        if randomize:
            # optional randomisation of the sub-seed blocks only
            random.shuffle(positions[2:])
        return positions[:num_seeds]

    # Fallback for other cases: place 1 at top, 2 at bottom, remaining spread
    positions = [1, draw_size]
    step = max(1, draw_size // max(1, num_seeds))
    pos = 1 + step
    while len(positions) < num_seeds and pos < draw_size:
        positions.append(pos)
        pos += step

    if randomize and len(positions) > 2:
        random.shuffle(positions[2:])

    return positions[:num_seeds]


def _select_seed_assignments(seed_assignments: Optional[Sequence[Dict]]) -> Optional[List[Dict]]:
    """Select the correct seed snapshot.

    Rules.md / DrawSeed audit trail:
    - If any seed rows exist with is_actual_seeding = TRUE, those rows must drive draw placement.
    - Otherwise, planned seeding (is_actual_seeding = FALSE) drives placement.
    - If seed_assignments is None or empty, seeding is derived from entries ordering (legacy path).
    """
    if not seed_assignments:
        return None

    actual = [s for s in seed_assignments if bool(s.get("is_actual_seeding"))]
    planned = [s for s in seed_assignments if not bool(s.get("is_actual_seeding"))]

    chosen = actual if actual else planned
    if not chosen:
        return None

    return sorted(chosen, key=lambda x: int(x["seed_number"]))


def _seeded_player_ids_in_order(
    *,
    sorted_entries: List[Dict],
    num_seeds: int,
    chosen_seed_assignments: Optional[List[Dict]]
) -> List[int]:
    """Return seeded player_ids in seed-number order.

    If chosen_seed_assignments is provided, it is authoritative.
    Otherwise, top num_seeds from sorted_entries (by entry_points desc) are used.
    """
    if num_seeds <= 0:
        return []

    if chosen_seed_assignments:
        return [int(s["player_id"]) for s in chosen_seed_assignments[:num_seeds]]

    return [int(e["player_id"]) for e in sorted_entries[:num_seeds]]


def _entry_sort_key(e: Dict) -> Tuple:
    """
    Sort key for entries: higher entry_points first; tie-breakers stable on player_id.
    """
    return (-int(e.get("entry_points", 0)), int(e["player_id"]))


# ============================================================
# MAIN GENERATOR
# ============================================================

def generate_draw_players(
    draw_id: int,
    entries: List[Dict],  # List of entry records for this draw
    draw_generated_timestamp: datetime,
    seeding_rules: List[Dict],
    disable_seeding: bool = False,
    *,
    withdrawn_player_id: Optional[int] = None,
    seed_assignments: Optional[Sequence[Dict]] = None,
) -> List[Dict]:
    """
    Generate DrawPlayers rows for one draw.

    Inputs expected in each entry dict:
    - player_id
    - entry_points (int)

    seed_assignments (optional) is a list of DrawSeed-like dicts with:
    - player_id
    - seed_number
    - is_actual_seeding

    Output rows match the DrawPlayers schema fields used by this project:
    - draw_id
    - player_id
    - draw_position
    - has_bye
    - created_at
    """
    # ============================================================
    # PRE-DRAW WITHDRAWAL (Rules.md 0.1% event)
    # ============================================================
    #
    # The withdrawn player MUST NOT be placed in DrawPlayers.
    # Seeding adjustment (is_actual_seeding=TRUE) is handled upstream in the seeding engine.
    #
    if withdrawn_player_id is not None:
        entries = [e for e in entries if int(e.get("player_id")) != int(withdrawn_player_id)]

    num_entries = len(entries)
    if num_entries == 0:
        return []

    # Determine draw size and byes from seeding_rules (existing project convention)
    # seeding_rules is expected to include a single dict for this draw size
    # with keys: draw_size, num_seeds, num_byes
    rule = seeding_rules[0] if seeding_rules else {}
    draw_size = int(rule.get("max_players", num_entries))
    num_seeds = int(rule.get("num_seeds", 0)) if not disable_seeding else 0
    num_byes = draw_size - num_entries

    if draw_size < num_entries:
        raise ValueError(f"draw_size={draw_size} is smaller than num_entries={num_entries} for draw_id={draw_id}")

    sorted_entries = sorted(entries, key=_entry_sort_key)

    # Select the correct seed snapshot (prefer is_actual_seeding=TRUE if present).
    chosen_seed_assignments = _select_seed_assignments(seed_assignments)

    # If chosen seeds exist, ensure all seeded players are present in entries.
    if chosen_seed_assignments:
        seeded_ids = {int(s["player_id"]) for s in chosen_seed_assignments}
        entry_ids = {int(e["player_id"]) for e in sorted_entries}
        missing = seeded_ids - entry_ids
        if missing:
            raise ValueError(
                f"Seed assignments reference player_id(s) not present in entries for draw_id={draw_id}: {sorted(missing)}"
            )

    # Seeding positions (only for seeded players)
    seeding_positions: List[int] = []
    if num_seeds > 0:
        seeding_positions = get_standard_seeding_positions(draw_size, num_seeds, randomize=False)

    # Seeded player_ids in seed-number order:
    # - If seed_assignments provided (and actual seeds exist), those seeds drive placement.
    # - Otherwise, seeds are derived from sorted_entries (entry_points desc).
    seeded_player_ids = _seeded_player_ids_in_order(
        sorted_entries=sorted_entries,
        num_seeds=num_seeds,
        chosen_seed_assignments=chosen_seed_assignments,
    )
    seeded_player_id_set = set(seeded_player_ids)

    # ---- Position pairs: (1,2), (3,4), ..., (draw_size-1, draw_size) ----
    all_pairs = [(i, i + 1) for i in range(1, draw_size + 1, 2)]

    # ---- Place seeded players at canonical positions ----
    seed_player_positions = {}
    seed_pair_indices = set()
    for idx, pid in enumerate(seeded_player_ids):
        pos = seeding_positions[idx]
        seed_player_positions[pid] = pos
        seed_pair_indices.add((pos - 1) // 2)

    # ---- Bye allocation (Rules.md) ----
    # Seeded players receive byes first (seed order), then random unseeded.
    bye_seeded_count = min(num_byes, len(seeded_player_ids))
    remaining_byes = num_byes - bye_seeded_count
    bye_player_ids = set(seeded_player_ids[:bye_seeded_count])

    # Seed pairs where seed has bye: fully reserved (opponent slot empty)
    # Seed pairs where seed has NO bye: opponent slot available for unseeded
    seed_bye_pair_indices = set()
    seed_opponent_positions = []
    for idx, pid in enumerate(seeded_player_ids):
        pair_idx = (seeding_positions[idx] - 1) // 2
        if pid in bye_player_ids:
            seed_bye_pair_indices.add(pair_idx)
        else:
            pos = seeding_positions[idx]
            pair = all_pairs[pair_idx]
            opponent_pos = pair[1] if pos == pair[0] else pair[0]
            seed_opponent_positions.append(opponent_pos)

    # Available full pairs for unseeded players (not occupied by any seed)
    available_pairs = [i for i in range(len(all_pairs)) if i not in seed_pair_indices]
    random.shuffle(available_pairs)

    # Split unseeded entries into bye / no-bye groups
    unseeded_entries = [e for e in sorted_entries if int(e["player_id"]) not in seeded_player_id_set]
    random.shuffle(unseeded_entries)

    unseeded_bye_entries = unseeded_entries[:remaining_byes]
    unseeded_no_bye_entries = unseeded_entries[remaining_byes:]
    bye_player_ids.update(int(e["player_id"]) for e in unseeded_bye_entries)

    seed_opponent_positions = []
    for idx, pid in enumerate(seeded_player_ids):
        if pid not in bye_player_ids:
            pos = seeding_positions[idx]
            pair = all_pairs[(pos - 1) // 2]
            seed_opponent_positions.append(pair[1] if pos == pair[0] else pair[0])

    # ---- Build draw_players ----
    draw_players: List[Dict] = []

    def _append_player(pid, pos, has_bye, entry):
        draw_players.append({
            "draw_id": draw_id,
            "player_id": pid,
            "draw_position": int(pos),
            "has_bye": bool(has_bye),
            "entry_points": int(entry.get("entry_points", 0)),
            "entry_timestamp": draw_generated_timestamp,
        })

    # 1. Seeded players (canonical positions)
    for pid in seeded_player_ids:
        entry = next(e for e in sorted_entries if int(e["player_id"]) == pid)
        _append_player(pid, seed_player_positions[pid], pid in bye_player_ids, entry)

    # 2. Unseeded players WITH byes (one slot of a pair, opponent slot stays empty)
    for entry in unseeded_bye_entries:
        pair_idx = available_pairs.pop(0)
        pos = all_pairs[pair_idx][0]
        _append_player(int(entry["player_id"]), pos, True, entry)

    # 3. Unseeded players WITHOUT byes
    no_bye_positions = list(seed_opponent_positions)
    for pair_idx in available_pairs:
        no_bye_positions.extend(all_pairs[pair_idx])
    random.shuffle(no_bye_positions)

    for entry in unseeded_no_bye_entries:
        pos = no_bye_positions.pop(0)
        _append_player(int(entry["player_id"]), pos, False, entry)

    return draw_players
