"""PlayerSuspensions generator.

This module generates rows for the PlayerSuspensions table as file-based artefacts.

Suspension rules (source of truth: Rules.md):
- match_status_id = 3 (Walkover / No-show / Default after draw) -> 2 months suspension
- match_status_id = 6 (Disqualified) -> 6 months suspension

Table schema (create_itf_schema.sql):
PlayerSuspensions(
    suspension_id INT PK,
    player_id INT NOT NULL,
    tournament_id INT NOT NULL,
    reason_match_status_id INT NOT NULL CHECK IN (3, 6),
    suspension_start DATE NOT NULL,
    suspension_end DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


REASON_NO_SHOW = 3
REASON_DISQUALIFIED = 6


@dataclass(frozen=True)
class PlayerSuspensionRow:
    suspension_id: int
    player_id: int
    tournament_id: int
    reason_match_status_id: int
    suspension_start: date
    suspension_end: date


def _add_months(d: date, months: int) -> date:
    """Add months to a date without external dependencies.

    Behaviour:
    - Month roll-over is handled.
    - If the resulting month has fewer days, the day is clamped to the month end.
    """
    # Convert to year/month index
    y = d.year
    m = d.month - 1 + months
    y += m // 12
    m = m % 12 + 1

    # Clamp day
    # Find last day of target month
    if m == 12:
        next_month = date(y + 1, 1, 1)
    else:
        next_month = date(y, m + 1, 1)
    last_day = next_month - timedelta(days=1)
    day = min(d.day, last_day.day)
    return date(y, m, day)


def _infer_tournament_id(draw_id: int, draw_to_tournament_id: Dict[int, int]) -> Optional[int]:
    try:
        return int(draw_to_tournament_id[int(draw_id)])
    except Exception:
        return None


def _infer_sanctioned_player_id(match: Dict) -> Optional[int]:
    """Infer which player is sanctioned for status 3 or 6.

    Assumption:
    - The sanctioned player is the loser (winner_id is the non-sanctioned player).
    - If winner_id is missing or does not match either player, None is returned.
    """
    try:
        p1 = int(match.get("player1_id"))
        p2 = int(match.get("player2_id"))
        w = match.get("winner_id")
        if w is None:
            return None
        w = int(w)
    except Exception:
        return None

    if w == p1:
        return p2
    if w == p2:
        return p1
    return None


def _match_date_to_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    # Accept ISO formats 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'
    if isinstance(value, str):
        v = value.strip()
        try:
            return datetime.fromisoformat(v).date()
        except Exception:
            try:
                return date.fromisoformat(v[:10])
            except Exception:
                return None
    return None


def generate_player_suspensions(
    matches: Sequence[Dict],
    draw_to_tournament_id: Dict[int, int],
    *,
    starting_suspension_id: int = 1,
    created_at: Optional[datetime] = None,
) -> List[PlayerSuspensionRow]:
    """Generate PlayerSuspensions rows from match outcomes.

    Inputs expected per match dict (minimum):
    - draw_id
    - match_status_id
    - player1_id, player2_id
    - winner_id
    - match_date (date/datetime/ISO string)

    Only match_status_id in (3, 6) produces suspensions.

    Deduplication:
    - One suspension per (player_id, tournament_id, reason_match_status_id).
    """
    rows: List[PlayerSuspensionRow] = []
    next_id = int(starting_suspension_id)

    seen: set[Tuple[int, int, int]] = set()

    for m in matches:
        try:
            status = int(m.get("match_status_id"))
        except Exception:
            continue

        if status not in (REASON_NO_SHOW, REASON_DISQUALIFIED):
            continue

        draw_id = m.get("draw_id")
        if draw_id is None:
            continue

        tournament_id = _infer_tournament_id(int(draw_id), draw_to_tournament_id)
        if tournament_id is None:
            continue

        sanctioned_player_id = _infer_sanctioned_player_id(m)
        if sanctioned_player_id is None:
            continue

        start_dt = _match_date_to_date(m.get("match_date"))
        if start_dt is None:
            # Fallback: if match_date missing, no safe rule-based date can be inferred here.
            # The caller must provide match_date in match generation output.
            continue

        months = 2 if status == REASON_NO_SHOW else 6
        end_dt = _add_months(start_dt, months)

        key = (sanctioned_player_id, int(tournament_id), status)
        if key in seen:
            continue
        seen.add(key)

        rows.append(
            PlayerSuspensionRow(
                suspension_id=next_id,
                player_id=int(sanctioned_player_id),
                tournament_id=int(tournament_id),
                reason_match_status_id=status,
                suspension_start=start_dt,
                suspension_end=end_dt,
            )
        )
        next_id += 1

    return rows
