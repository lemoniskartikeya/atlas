"""Timestamp → calendar-day conversion.

Atlas stores timestamps in UTC but every user-facing notion of a "day" is
local: `date.today()`, the day a habit is logged against, the ISO week a
review covers. Converting a stored UTC timestamp with a bare ``.date()``
therefore attributes anything logged after local midnight-minus-offset to the
previous day — in IST (UTC+5:30) that is every evening from 18:30 onward.

One helper, used everywhere a timestamp becomes a day.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional, overload


@overload
def local_day(ts: datetime) -> date: ...
@overload
def local_day(ts: Optional[datetime], fallback: date) -> date: ...


def local_day(ts: Optional[datetime], fallback: Optional[date] = None) -> Optional[date]:
    """The calendar day a timestamp falls on, in the machine's timezone.

    Naive values (what SQLite hands back) are treated as UTC, which is how they
    were written.
    """
    if ts is None:
        return fallback
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone().date()
