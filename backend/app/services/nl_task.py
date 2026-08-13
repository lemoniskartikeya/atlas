"""Turning "gym tomorrow 7am !high" into a task.

Deterministic, offline, and free. No model is called: an LLM would be slower,
would need a key the app deliberately doesn't require, and would be worse at
this — the grammar of "next tuesday at 3" is small and closed, and a parser
that always does the same thing is one people can learn.

Three rules keep it from being annoying:

* **Whole words only.** Fragments inside a word are never matched, so
  "somersault" keeps its "some" and "August" is not an "aug" plus a "ust".
* **Never eat the title.** If removing what was understood would leave nothing
  behind, the match is given back — "tomorrow" on its own is a perfectly good
  task name.
* **Say what was understood.** Every extraction is reported, so the guesses
  below are visible and correctable instead of surprising.

The one real guess is a bare hour: "at 3" means 3pm, because almost nobody
schedules 3am. Stated here, shown in the UI, and overridable in the form.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Optional

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

#: Words that raise priority. Only unambiguous ones — "important" is far more
#: often part of a title ("draft important email") than a priority marker.
_PRIORITY_WORDS = {
    "urgent": "high",
    "asap": "high",
    "critical": "critical",
}

_PRIORITY_BANGS = {"!low": "low", "!med": "medium", "!medium": "medium",
                   "!high": "high", "!urgent": "high", "!critical": "critical"}

#: Named times of day, mapped to the hour a person means by them.
_NAMED_TIMES = {"noon": 12, "midday": 12, "midnight": 0}


@dataclass
class ParsedTask:
    """What was read out of the phrase, and what was left of it."""

    title: str
    due_date: Optional[date] = None
    deadline: Optional[datetime] = None
    priority: Optional[str] = None
    estimated_effort_min: Optional[int] = None
    tags: list[str] = field(default_factory=list)
    #: One phrase per thing understood, for showing back to the user.
    understood: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Nothing was extracted — this was just a title after all."""
        return not (
            self.due_date or self.deadline or self.priority
            or self.estimated_effort_min or self.tags
        )


class _Text:
    """The phrase, with matched spans blanked out as they are consumed.

    Blanking rather than deleting keeps every remaining match's offsets valid,
    so the passes below can run in any order without tracking shifting indices.
    """

    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.mask = [True] * len(raw)  # True = still part of the title

    def take(self, match: re.Match) -> None:
        for i in range(*match.span()):
            self.mask[i] = False

    def search(self, pattern: str) -> Optional[re.Match]:
        """First match that lies entirely in text not yet consumed."""
        for m in re.finditer(pattern, self.raw, re.IGNORECASE):
            if all(self.mask[i] for i in range(*m.span())):
                return m
        return None

    def remainder(self) -> str:
        kept = "".join(c for c, keep in zip(self.raw, self.mask) if keep)
        return re.sub(r"\s{2,}", " ", kept).strip(" ,-–—")


def _next_weekday(today: date, weekday: int, *, force_next: bool = False) -> date:
    """The coming occurrence of a weekday.

    Saying a day name on that same day means next week — "do it Monday" said on
    a Monday is not about the hour you are living in. Otherwise "next friday"
    and "friday" agree, which matches how people actually use them.
    """
    ahead = (weekday - today.weekday()) % 7
    if ahead == 0:
        ahead = 7
    return today + timedelta(days=ahead)


def _hour_from(raw_hour: int, meridiem: Optional[str], bare: bool) -> Optional[int]:
    if meridiem:
        meridiem = meridiem.lower().replace(".", "")
        if raw_hour > 12:
            return None
        if meridiem.startswith("p"):
            return 12 if raw_hour == 12 else raw_hour + 12
        return 0 if raw_hour == 12 else raw_hour
    if raw_hour > 23:
        return None
    # A bare "at 3" means the afternoon; "at 9" means the morning. Nobody
    # schedules a gym session for 3am, and this is shown back for correction.
    if bare and 1 <= raw_hour <= 7:
        return raw_hour + 12
    return raw_hour


def parse(text: str, now: Optional[datetime] = None) -> ParsedTask:
    """Read a phrase into task fields. Never raises; worst case is a plain title."""
    now = now or datetime.now()
    today = now.date()
    t = _Text(text or "")

    due: Optional[date] = None
    at: Optional[time] = None
    priority: Optional[str] = None
    effort: Optional[int] = None
    tags: list[str] = []
    understood: list[str] = []

    # --- tags ---------------------------------------------------------------
    while True:
        m = t.search(r"#([A-Za-z][\w-]*)")
        if not m:
            break
        t.take(m)
        tags.append(m.group(1).lower())
    if tags:
        understood.append("tagged " + ", ".join(f"#{x}" for x in tags))

    # --- priority -----------------------------------------------------------
    m = t.search(r"(?<!\w)(!low|!medium|!med|!high|!urgent|!critical)(?!\w)")
    if m:
        t.take(m)
        priority = _PRIORITY_BANGS[m.group(1).lower()]
    else:
        m = t.search(r"(?<!\w)(urgent|asap|critical)(?!\w)")
        if m:
            t.take(m)
            priority = _PRIORITY_WORDS[m.group(1).lower()]
    if priority:
        understood.append(f"{priority} priority")

    # --- duration -----------------------------------------------------------
    m = t.search(r"(?<!\w)(?:for\s+)?(\d+(?:\.\d+)?)\s*(hours|hour|hrs|hr|h|minutes|minute|mins|min|m)(?!\w)")
    if m:
        value, unit = float(m.group(1)), m.group(2).lower()
        minutes = int(round(value * 60)) if unit.startswith("h") else int(round(value))
        # A stray "2 m" is more likely a typo than a two-minute task, but the
        # damage is small and visible; anything absurd is refused outright.
        if 1 <= minutes <= 24 * 60:
            t.take(m)
            effort = minutes
            understood.append(f"about {minutes} min")

    # --- explicit date: 2026-08-15 -----------------------------------------
    m = t.search(r"(?<!\w)(\d{4})-(\d{2})-(\d{2})(?!\w)")
    if m:
        try:
            due = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            t.take(m)
        except ValueError:
            pass

    # --- "15 aug" / "aug 15" / "15th" --------------------------------------
    if due is None:
        month_names = "|".join(sorted(_MONTHS, key=len, reverse=True))
        m = t.search(rf"(?<!\w)(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})(?!\w)")
        if m:
            day, month = int(m.group(1)), _MONTHS[m.group(2).lower()]
        else:
            m = t.search(rf"(?<!\w)({month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?!\w)")
            day, month = (int(m.group(2)), _MONTHS[m.group(1).lower()]) if m else (0, 0)
        if m and 1 <= day <= 31:
            year = now.year
            try:
                candidate = date(year, month, day)
                # A date that has already passed means next year: "jan 3" said
                # in December is not ten months ago.
                if candidate < today:
                    candidate = date(year + 1, month, day)
                due = candidate
                t.take(m)
            except ValueError:
                pass

    # --- relative days ------------------------------------------------------
    if due is None:
        m = t.search(r"(?<!\w)(today|tonight|tomorrow|tmr|tmw)(?!\w)")
        if m:
            word = m.group(1).lower()
            t.take(m)
            due = today if word in {"today", "tonight"} else today + timedelta(days=1)
            if word == "tonight" and at is None:
                at = time(19, 0)

    if due is None:
        m = t.search(r"(?<!\w)in\s+(\d{1,3})\s+(days?|weeks?)(?!\w)")
        if m:
            n = int(m.group(1))
            t.take(m)
            due = today + timedelta(days=n * (7 if m.group(2).startswith("week") else 1))

    if due is None:
        m = t.search(r"(?<!\w)next\s+week(?!\w)")
        if m:
            t.take(m)
            due = today + timedelta(days=7)

    if due is None:
        names = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
        m = t.search(rf"(?<!\w)(?:(next|this)\s+)?({names})(?!\w)")
        if m:
            t.take(m)
            due = _next_weekday(
                today, _WEEKDAYS[m.group(2).lower()], force_next=bool(m.group(1))
            )

    # --- time of day --------------------------------------------------------
    if at is None:
        m = t.search(r"(?<!\w)(?:at\s+)?(\d{1,2})[:.](\d{2})\s*([ap]\.?m\.?)?(?!\w)")
        if m:
            hour = _hour_from(int(m.group(1)), m.group(3), bare=False)
            minute = int(m.group(2))
            if hour is not None and minute < 60:
                t.take(m)
                at = time(hour, minute)

    if at is None:
        m = t.search(r"(?<!\w)(\d{1,2})\s*([ap]\.?m\.?)(?!\w)")
        if m:
            hour = _hour_from(int(m.group(1)), m.group(2), bare=False)
            if hour is not None:
                t.take(m)
                at = time(hour, 0)

    if at is None:
        m = t.search(r"(?<!\w)at\s+(\d{1,2})(?!\w)")
        if m:
            hour = _hour_from(int(m.group(1)), None, bare=True)
            if hour is not None:
                t.take(m)
                at = time(hour, 0)

    if at is None:
        m = t.search(r"(?<!\w)(noon|midday|midnight)(?!\w)")
        if m:
            t.take(m)
            at = time(_NAMED_TIMES[m.group(1).lower()], 0)

    # --- assemble -----------------------------------------------------------
    title = t.remainder()
    if not title:
        # Everything was understood and nothing is left to call it. Better to
        # hand back the original phrase than an untitled task.
        return ParsedTask(title=(text or "").strip())

    deadline: Optional[datetime] = None
    if at is not None:
        if due is None:
            # A time with no day means today, unless that has already gone by.
            due = today if now.time() <= at else today + timedelta(days=1)
        deadline = datetime.combine(due, at).astimezone()

    if due is not None:
        understood.insert(0, _describe_day(due, today) + (f" at {_fmt(at)}" if at else ""))

    return ParsedTask(
        title=title,
        due_date=due,
        deadline=deadline,
        priority=priority,
        estimated_effort_min=effort,
        tags=tags,
        understood=understood,
    )


def _fmt(t: time) -> str:
    hour = t.hour % 12 or 12
    suffix = "am" if t.hour < 12 else "pm"
    return f"{hour}:{t.minute:02d}{suffix}"


def _describe_day(d: date, today: date) -> str:
    delta = (d - today).days
    if delta == 0:
        return "due today"
    if delta == 1:
        return "due tomorrow"
    if 2 <= delta <= 6:
        return f"due {d.strftime('%A')}"
    # Built by hand: %-d is a glibc extension and %#d is Windows-only, so
    # neither is portable, and a zero-padded day reads like a serial number.
    return f"due {d.strftime('%b')} {d.day}"
