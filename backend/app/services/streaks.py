"""Pure streak / consistency math.

Kept free of ORM and framework imports so it is trivially unit-testable and can be
reused by the future ML feature pipeline. Everything operates on plain dates.

Model: calendar days in a window are grouped into *periods*.
  - DAILY / CUSTOM  -> each due day is its own period (target = 1).
  - WEEKLY          -> an ISO week is a period; successful if >= target completions.
  - MONTHLY         -> a calendar month is a period; successful if >= target completions.

A period that contains "today" and isn't yet successful is treated as *pending* — it
does not break the current streak (you still have time to do it).
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from app.domain.enums import Frequency

_ONE_DAY = timedelta(days=1)


@dataclass(frozen=True)
class Period:
    key: tuple
    success: bool
    is_today: bool


def period_key(frequency: Frequency, d: date) -> tuple:
    if frequency == Frequency.WEEKLY:
        iso = d.isocalendar()
        return ("W", iso.year, iso.week)
    if frequency == Frequency.MONTHLY:
        return ("M", d.year, d.month)
    return ("D", d.toordinal())


def is_occurrence_day(frequency: Frequency, custom_days: Iterable[int] | None, d: date) -> bool:
    """Whether the habit can occur on day ``d``.

    For CUSTOM, only the configured weekdays count. For all other frequencies every
    day is a candidate; the period grouping decides what "on track" means.
    """
    if frequency == Frequency.CUSTOM:
        return d.weekday() in set(custom_days or [])
    return True


def build_periods(
    frequency: Frequency,
    custom_days: Iterable[int] | None,
    target_per_period: int,
    success_dates: set[date],
    start: date,
    today: date,
) -> list[Period]:
    """Aggregate the inclusive range [start, today] into ordered periods."""
    target = target_per_period if frequency in (Frequency.WEEKLY, Frequency.MONTHLY) else 1
    buckets: "OrderedDict[tuple, list]" = OrderedDict()  # key -> [success_count, is_today]
    d = start
    while d <= today:
        if is_occurrence_day(frequency, custom_days, d):
            key = period_key(frequency, d)
            bucket = buckets.setdefault(key, [0, False])
            if d in success_dates:
                bucket[0] += 1
            if d == today:
                bucket[1] = True
        d += _ONE_DAY
    return [Period(key, count >= target, is_today) for key, (count, is_today) in buckets.items()]


def compute_streaks(periods: list[Period]) -> tuple[int, int]:
    """Return ``(current_streak, longest_streak)`` from an ordered period list."""
    longest = run = 0
    for p in periods:
        if p.success:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    current = 0
    for p in reversed(periods):
        if p.success:
            current += 1
        elif p.is_today:
            continue  # today's period is still pending — don't break the streak
        else:
            break
    return current, longest


def success_rate(periods: list[Period]) -> float:
    """Fraction of periods that were successful (0..1)."""
    if not periods:
        return 0.0
    return sum(1 for p in periods if p.success) / len(periods)
