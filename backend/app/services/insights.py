"""Plain-language readings of the analytics charts.

The Analytics page shows what happened; nothing on it says what it means. These
are the sentences a person would write after looking at those charts — the best
and worst weekday, whether the last month is up or down, which of the tracked
signals actually moves the completion rate, which habit is slipping.

Three rules, and every function here obeys them:

* **Nothing is invented.** Every sentence is arithmetic over the user's own
  logs, and carries the numbers it was derived from so it can be checked.
* **Silence beats a guess.** Each rule has a minimum sample size and a minimum
  effect. Below either, it returns None and simply isn't shown — an empty list
  is a valid, honest answer for a new account.
* **Rates, not counts.** Comparing raw completion counts across weekdays or
  categories rewards whichever one has more habits scheduled on it. Everything
  comparative here divides by what was actually due.

Pure functions over plain values: no session, no ORM, no clock. The service
layer gathers the frames; the judgement lives here where it can be tested
directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

#: Occurrences a weekday needs before its rate means anything.
MIN_WEEKDAY_SAMPLE = 8
#: Percentage points between best and worst weekday before it is worth saying.
MIN_WEEKDAY_GAP = 0.15

#: Due habit-days needed in each half of a trend comparison.
MIN_TREND_SAMPLE = 10
MIN_TREND_SHIFT = 0.08

#: Overlapping days, and |r|, before a correlation is worth repeating.
MIN_CORRELATION_SAMPLE = 14
MIN_CORRELATION_STRENGTH = 0.3

#: How far a habit's last 30 days must fall below its own history to count as
#: slipping, and the history it needs before that comparison is fair.
MIN_SLIP = 0.2
MIN_SLIP_HISTORY = 20

MIN_ANCHOR_RATE = 0.85
MIN_ANCHOR_HISTORY = 15

MIN_CATEGORY_SHARE = 0.5
MIN_CATEGORY_TOTAL = 20


@dataclass(frozen=True)
class Insight:
    """One sentence, and the numbers behind it.

    `evidence` is kept separate rather than folded into the text so the UI can
    show it quietly alongside — the claim stays readable, and the arithmetic
    stays visible.
    """

    key: str
    text: str
    evidence: str
    tone: str  # "good" | "watch" | "neutral"


def _pct(x: float) -> int:
    return round(x * 100)


# ------------------------------------------------------------------- weekdays
def weekday_edge(by_weekday: Sequence[tuple[int, int]]) -> Optional[Insight]:
    """Which day of the week you actually keep, and which you don't.

    Takes (done, due) per weekday, Monday first. Rates, because a Monday-only
    habit would otherwise make Monday look like your strongest day when it is
    only your busiest.
    """
    if len(by_weekday) != 7:
        return None
    rated = [
        (i, done / due, due)
        for i, (done, due) in enumerate(by_weekday)
        if due >= MIN_WEEKDAY_SAMPLE
    ]
    # Two days to compare, or there is no comparison to make.
    if len(rated) < 2:
        return None

    best = max(rated, key=lambda r: r[1])
    worst = min(rated, key=lambda r: r[1])
    gap = best[1] - worst[1]
    if gap < MIN_WEEKDAY_GAP:
        return None

    return Insight(
        key="weekday_edge",
        text=(
            f"{WEEKDAYS[best[0]]}s are your strongest day at {_pct(best[1])}%, "
            f"and {WEEKDAYS[worst[0]]}s your weakest at {_pct(worst[1])}%."
        ),
        evidence=(
            f"{_pct(gap)} point gap · {best[2]} {WEEKDAYS[best[0]]}s and "
            f"{worst[2]} {WEEKDAYS[worst[0]]}s with something due"
        ),
        tone="neutral",
    )


# ---------------------------------------------------------------------- trend
def trend(
    recent: tuple[int, int], previous: tuple[int, int], window_days: int = 28
) -> Optional[Insight]:
    """Where the last four weeks sit against the four before them.

    Each argument is (done, due). The weekly bar chart already draws this; the
    eye is bad at judging whether a jagged line is going anywhere.
    """
    r_done, r_due = recent
    p_done, p_due = previous
    if r_due < MIN_TREND_SAMPLE or p_due < MIN_TREND_SAMPLE:
        return None

    now, before = r_done / r_due, p_done / p_due
    shift = now - before
    weeks = window_days // 7

    if abs(shift) < MIN_TREND_SHIFT:
        return Insight(
            key="trend",
            text=(
                f"You're holding steady — {_pct(now)}% over the last {weeks} weeks, "
                f"against {_pct(before)}% in the {weeks} before."
            ),
            evidence=f"{r_done}/{r_due} vs {p_done}/{p_due} due",
            tone="neutral",
        )

    rising = shift > 0
    return Insight(
        key="trend",
        text=(
            f"Your completion rate is {'up' if rising else 'down'} "
            f"{abs(_pct(shift))} points over the last {weeks} weeks — "
            f"{_pct(before)}% then, {_pct(now)}% now."
        ),
        evidence=f"{r_done}/{r_due} vs {p_done}/{p_due} due",
        tone="good" if rising else "watch",
    )


# --------------------------------------------------------------------- driver
def strongest_driver(pairs: Iterable[tuple[str, Optional[float], int]]) -> Optional[Insight]:
    """The one tracked signal most closely tied to whether you follow through.

    Takes (label, coefficient, n). The correlation cards each carry their own
    reading; none of them says which one to care about.
    """
    usable = [
        (label, r, n)
        for label, r, n in pairs
        if r is not None and n >= MIN_CORRELATION_SAMPLE and abs(r) >= MIN_CORRELATION_STRENGTH
    ]
    if not usable:
        return None

    label, r, n = max(usable, key=lambda p: abs(p[1]))
    direction = "more" if r > 0 else "less"
    return Insight(
        key="driver",
        text=(
            f"{label} tracks your follow-through most closely: {direction} of it "
            f"goes with a higher completion rate. Worth an experiment, not a conclusion."
        ),
        evidence=f"r={r:+.2f} across {n} days with both recorded",
        tone="neutral",
    )


# --------------------------------------------------------------------- habits
@dataclass(frozen=True)
class HabitRow:
    """What the summary already knows about one habit."""

    title: str
    success_rate: float      # all time
    consistency_30d: float   # last 30 days
    total_completions: int
    current_streak: int


def slipping_habit(habits: Sequence[HabitRow]) -> Optional[Insight]:
    """The habit falling furthest behind its own track record.

    Against its own history, not against the others — a habit due weekly and
    one due daily are not comparable, but either can be compared to itself.
    """
    candidates = [
        (h, h.success_rate - h.consistency_30d)
        for h in habits
        if h.total_completions >= MIN_SLIP_HISTORY
        and h.success_rate - h.consistency_30d >= MIN_SLIP
    ]
    if not candidates:
        return None

    habit, drop = max(candidates, key=lambda c: c[1])
    return Insight(
        key="slipping_habit",
        text=(
            f"“{habit.title}” has slipped: {_pct(habit.consistency_30d)}% over the "
            f"last 30 days against {_pct(habit.success_rate)}% all time."
        ),
        evidence=f"{_pct(drop)} points below its own average · {habit.total_completions} completions on record",
        tone="watch",
    )


def anchor_habit(habits: Sequence[HabitRow]) -> Optional[Insight]:
    """The one that is holding, so the picture isn't only what's wrong."""
    candidates = [
        h
        for h in habits
        if h.total_completions >= MIN_ANCHOR_HISTORY and h.consistency_30d >= MIN_ANCHOR_RATE
    ]
    if not candidates:
        return None

    habit = max(candidates, key=lambda h: (h.consistency_30d, h.current_streak))
    streak = (
        f" and a {habit.current_streak}-day streak" if habit.current_streak >= 3 else ""
    )
    return Insight(
        key="anchor_habit",
        text=(
            f"“{habit.title}” is your anchor — {_pct(habit.consistency_30d)}% over the "
            f"last 30 days{streak}."
        ),
        evidence=f"{habit.total_completions} completions on record",
        tone="good",
    )


# ------------------------------------------------------------------ category
def category_focus(categories: Sequence[tuple[str, int]]) -> Optional[Insight]:
    """When most of the effort lands in one place, say so.

    Not a criticism — a concentrated life is a choice. It is only worth
    surfacing because it is invisible in a bar chart sorted by size.
    """
    named = [(c, n) for c, n in categories if n > 0 and c.lower() != "uncategorized"]
    total = sum(n for _c, n in named)
    if len(named) < 2 or total < MIN_CATEGORY_TOTAL:
        return None

    label, count = max(named, key=lambda c: c[1])
    share = count / total
    if share < MIN_CATEGORY_SHARE:
        return None

    others = len(named) - 1
    rest = (
        "the other category takes what's left"
        if others == 1
        else f"the other {others} categories share what's left"
    )
    return Insight(
        key="category_focus",
        text=f"{_pct(share)}% of everything you complete is {label} — {rest}.",
        evidence=f"{count} of {total} completions",
        tone="neutral",
    )


# ----------------------------------------------------------------- assembly
#: Ordered by what a person would want to read first: where you're heading,
#: then what needs attention, then the patterns underneath.
_ORDER = ["trend", "slipping_habit", "weekday_edge", "driver", "anchor_habit", "category_focus"]


def rank(found: Iterable[Optional[Insight]], limit: int = 4) -> list[Insight]:
    """Drop the rules that had nothing to say, and keep the useful few.

    A wall of observations is as unreadable as none, and the tail is always the
    weakest — these are ordered by usefulness, not by score.
    """
    present = [i for i in found if i is not None]
    present.sort(key=lambda i: _ORDER.index(i.key) if i.key in _ORDER else len(_ORDER))
    return present[:limit]
