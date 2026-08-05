"""Unit tests for the pure streak/consistency engine."""
from __future__ import annotations

from datetime import date, timedelta

from app.domain.enums import Frequency
from app.services import streaks

TODAY = date(2026, 8, 7)  # a Friday


def _daily(success_offsets, window_days, today=TODAY):
    success = {today - timedelta(days=o) for o in success_offsets}
    start = today - timedelta(days=window_days)
    return streaks.build_periods(Frequency.DAILY, None, 1, success, start, today)


def test_daily_perfect_streak():
    periods = _daily([0, 1, 2, 3, 4], window_days=4)
    current, longest = streaks.compute_streaks(periods)
    assert current == 5
    assert longest == 5


def test_today_pending_does_not_break_streak():
    # Completed the previous 4 days; today (offset 0) not logged yet.
    periods = _daily([1, 2, 3, 4], window_days=4)
    current, longest = streaks.compute_streaks(periods)
    assert current == 4  # today is pending, streak survives
    assert longest == 4


def test_gap_resets_current_and_bounds_longest():
    # success at 0,1,2 and 5,6,7 with a two-day gap at 3,4
    periods = _daily([0, 1, 2, 5, 6, 7], window_days=7)
    current, longest = streaks.compute_streaks(periods)
    assert current == 3
    assert longest == 3


def test_missed_yesterday_breaks_when_today_also_missing():
    # Nothing recent; last success was 3 days ago.
    periods = _daily([3, 4, 5], window_days=6)
    current, longest = streaks.compute_streaks(periods)
    assert current == 0
    assert longest == 3


def test_custom_mwf_counts_only_occurrence_days():
    custom_days = [0, 2, 4]  # Mon, Wed, Fri
    # Friday (today), Wednesday (-2), Monday (-4) all done.
    success = {TODAY, TODAY - timedelta(days=2), TODAY - timedelta(days=4)}
    periods = streaks.build_periods(
        Frequency.CUSTOM, custom_days, 1, success, TODAY - timedelta(days=13), TODAY
    )
    current, longest = streaks.compute_streaks(periods)
    assert current == 3  # three consecutive M/W/F occurrences


def test_weekly_target_periods():
    # Need 3 completions per ISO week to count the week as successful.
    success = set()
    for offset in (0, 1, 2):       # this week
        success.add(TODAY - timedelta(days=offset))
    for offset in (7, 8, 9):       # last week
        success.add(TODAY - timedelta(days=offset))
    success.add(TODAY - timedelta(days=14))  # two weeks ago: only 1 -> fails target

    periods = streaks.build_periods(
        Frequency.WEEKLY, None, 3, success, TODAY - timedelta(days=20), TODAY
    )
    current, longest = streaks.compute_streaks(periods)
    assert current == 2  # this week + last week met the target of 3
    assert longest == 2


def test_success_rate():
    periods = _daily([0, 2, 4], window_days=4)  # 3 of 5 days
    assert streaks.success_rate(periods) == 3 / 5
