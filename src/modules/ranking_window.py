# src/modules/ranking_window.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Tuple


UTC = timezone.utc


@dataclass(frozen=True)
class IsoWeek:
    """
    ISO (International Organization for Standardization) week identifier.

    ISO weeks use:
    - Monday as the first day of the week
    - week number 01..52/53
    - an ISO year (may differ from the calendar year near boundaries)
    """
    iso_year: int
    iso_week: int


def iso_week_of(d: date) -> IsoWeek:
    """Return the ISO week (iso_year, iso_week) for a given date."""
    y, w, _ = d.isocalendar()
    return IsoWeek(int(y), int(w))


def iso_week_monday(iso_year: int, iso_week: int) -> date:
    """
    Return the Monday date for an ISO year/week.
    Implemented via ISO calendar constructor (Monday = 1).
    """
    return date.fromisocalendar(iso_year, iso_week, 1)


def iso_week_sunday(iso_year: int, iso_week: int) -> date:
    """Return the Sunday date for an ISO year/week (Sunday = 7)."""
    return date.fromisocalendar(iso_year, iso_week, 7)


def add_iso_weeks(iso_year: int, iso_week: int, weeks_delta: int) -> IsoWeek:
    """
    Add weeks_delta ISO weeks to an ISO week.
    Uses the Monday anchor date then converts back to ISO.
    """
    anchor = iso_week_monday(iso_year, iso_week)
    shifted = anchor + timedelta(weeks=weeks_delta)
    return iso_week_of(shifted)


def ranking_publication_dt(iso_year: int, iso_week: int) -> datetime:
    """
    Rules.md: weekly ranking is published every Monday at 20:00 UTC.

    Returns a timezone-aware datetime in UTC.
    """
    monday = iso_week_monday(iso_year, iso_week)
    return datetime.combine(monday, time(20, 0, 0), tzinfo=UTC)


def ranking_window_dt(iso_year: int, iso_week: int) -> Tuple[datetime, datetime]:
    """
    Rules.md: ranking includes best 4 results over the previous 52 weeks.

    Window definition:
    - window_end: ranking publication timestamp (Monday 20:00 UTC)
    - window_start: window_end minus 52 weeks

    Returns (window_start, window_end), both timezone-aware UTC datetimes.
    """
    window_end = ranking_publication_dt(iso_year, iso_week)
    window_start = window_end - timedelta(weeks=52)
    return window_start, window_end


def ranking_week_for_tournament_week(tournament_iso_year: int, tournament_iso_week: int) -> IsoWeek:
    """
    Rules.md: players are seeded according to the weekly ranking of the week preceding the tournament.

    For a tournament in ISO week W:
    - use ranking published on Monday of ISO week (W - 1)

    Returns the ISO week of the ranking publication to use for seeding.
    """
    return add_iso_weeks(tournament_iso_year, tournament_iso_week, -1)


def entry_deadline_dt_for_tournament_week(tournament_iso_year: int, tournament_iso_week: int) -> datetime:
    """
    Rules.md: entry deadline is every Tuesday at 10:00 UTC for the tournament starting the following week.

    For a tournament in ISO week W:
    - entry deadline is Tuesday 10:00 UTC of ISO week (W - 1)
    """
    prev_week = add_iso_weeks(tournament_iso_year, tournament_iso_week, -1)
    tuesday = date.fromisocalendar(prev_week.iso_year, prev_week.iso_week, 2)
    return datetime.combine(tuesday, time(10, 0, 0), tzinfo=UTC)


def draw_publication_dt_for_tournament_week(tournament_iso_year: int, tournament_iso_week: int) -> datetime:
    """
    Rules.md: draw is published on the Friday following the entry deadline at exactly 19:00 UTC.

    For a tournament in ISO week W:
    - draw publication is Friday 19:00 UTC of ISO week (W - 1)
    """
    prev_week = add_iso_weeks(tournament_iso_year, tournament_iso_week, -1)
    friday = date.fromisocalendar(prev_week.iso_year, prev_week.iso_week, 5)
    return datetime.combine(friday, time(19, 0, 0), tzinfo=UTC)


def tournament_week_range(tournament_iso_year: int, tournament_iso_week: int) -> Tuple[date, date]:
    """
    Return (monday, sunday) date range for the tournament ISO week.
    Useful for UI labelling and schedule validation.
    """
    return iso_week_monday(tournament_iso_year, tournament_iso_week), iso_week_sunday(tournament_iso_year, tournament_iso_week)
