"""How this person actually works.

Everything else in Atlas describes a moment: today's plan, this week's review,
the current streak. None of it describes the *person* — that they finish things
before 9am, fall apart on Saturdays, and rarely take a streak past four days.
Those patterns are stable, they are already implicit in the logs, and they are
what makes advice specific instead of generic.

The profile is read-only and derived. It stores nothing and predicts nothing;
it reports what the record already says, with the sample size attached. Every
trait is omitted when the evidence is too thin — a profile that guesses is a
horoscope, and this one has to survive the user checking it.

Four traits, chosen because nothing else in the app computes them:

* **Peak hours** — when completions actually land, across habits and tasks.
* **Weekday reliability** — which days hold and which don't, by rate.
* **Streak durability** — how long runs usually last before they break.
* **Load tolerance** — how a crowded day changes what gets finished.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.timeutil import local_day
from app.domain.enums import SUCCESS_STATUSES, TaskStatus
from app.repositories.habit_repo import HabitRepository
from app.repositories.task_repo import TaskRepository

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

#: Completions needed before "when you work" is a pattern rather than an anecdote.
MIN_COMPLETIONS_FOR_HOURS = 20
#: And how concentrated that window has to be before it is worth mentioning.
MIN_PEAK_SHARE = 0.35

#: Occurrences per weekday before its rate is comparable to another's.
MIN_WEEKDAY_SAMPLE = 6
MIN_WEEKDAY_SPREAD = 0.15

#: Completed runs needed before a typical length means anything.
MIN_RUNS = 4

#: Days in each half of the load comparison, and the gap worth reporting.
MIN_LOAD_SAMPLE = 8
MIN_LOAD_GAP = 0.15


@dataclass(frozen=True)
class Trait:
    """One observed pattern, and what it was derived from."""

    key: str
    summary: str
    evidence: str


@dataclass
class BehaviourProfile:
    traits: list[Trait]
    #: Structured versions of the same facts, for callers that want the numbers
    #: rather than the sentence.
    peak_hours: Optional[tuple[int, int]] = None
    best_weekday: Optional[int] = None
    worst_weekday: Optional[int] = None
    typical_streak: Optional[int] = None

    def sentences(self) -> list[str]:
        return [t.summary for t in self.traits]


def _fmt_hour(hour: int) -> str:
    if hour == 0:
        return "midnight"
    if hour == 12:
        return "noon"
    return f"{hour % 12 or 12}{'am' if hour < 12 else 'pm'}"


# ------------------------------------------------------------------- traits
def peak_hours(hours: Sequence[int]) -> Optional[tuple[Trait, tuple[int, int]]]:
    """The three-hour window most completions fall into.

    A window rather than a single hour: "you work at 7am" is a claim about a
    clock, "you work first thing" is a claim about a person, and the second one
    is both truer and more useful.
    """
    if len(hours) < MIN_COMPLETIONS_FOR_HOURS:
        return None

    counts = Counter(hours)
    best_start, best_n = 0, -1
    for start in range(24):
        window = sum(counts.get((start + offset) % 24, 0) for offset in range(3))
        if window > best_n:
            best_start, best_n = start, window

    share = best_n / len(hours)
    if share < MIN_PEAK_SHARE:
        return None

    end = (best_start + 3) % 24
    return (
        Trait(
            key="peak_hours",
            summary=(
                f"You get most done between {_fmt_hour(best_start)} and {_fmt_hour(end)} — "
                f"{round(share * 100)}% of everything you finish."
            ),
            evidence=f"{best_n} of {len(hours)} completions with a recorded time",
        ),
        (best_start, end),
    )


def weekday_reliability(
    by_weekday: Sequence[tuple[int, int]]
) -> Optional[tuple[Trait, int, int]]:
    """Which day holds and which doesn't, as (done, due) per weekday.

    By rate, always: counting completions would crown whichever weekday simply
    has the most scheduled on it.
    """
    if len(by_weekday) != 7:
        return None
    rated = [
        (i, done / due, due)
        for i, (done, due) in enumerate(by_weekday)
        if due >= MIN_WEEKDAY_SAMPLE
    ]
    if len(rated) < 3:
        return None

    best = max(rated, key=lambda r: r[1])
    worst = min(rated, key=lambda r: r[1])
    if best[1] - worst[1] < MIN_WEEKDAY_SPREAD:
        return None

    return (
        Trait(
            key="weekday_reliability",
            summary=(
                f"{WEEKDAYS[best[0]]} is your most reliable day ({round(best[1] * 100)}%) "
                f"and {WEEKDAYS[worst[0]]} your least ({round(worst[1] * 100)}%)."
            ),
            evidence=f"{best[2]} and {worst[2]} occurrences respectively",
        ),
        best[0],
        worst[0],
    )


def streak_durability(runs: Sequence[int]) -> Optional[tuple[Trait, int]]:
    """How long a run of completions usually lasts before it breaks.

    Only *finished* runs count — a streak still going has no length yet, and
    including it would drag the typical figure down every time you looked.
    """
    if len(runs) < MIN_RUNS:
        return None

    ordered = sorted(runs)
    middle = len(ordered) // 2
    typical = (
        ordered[middle]
        if len(ordered) % 2
        else round((ordered[middle - 1] + ordered[middle]) / 2)
    )
    longest = max(ordered)

    if typical >= longest:
        summary = f"Your runs are steady at around {typical} days."
    else:
        summary = (
            f"Your streaks usually break around day {typical}, though you've "
            f"reached {longest}."
        )
    return (
        Trait(
            key="streak_durability",
            summary=summary,
            evidence=f"{len(runs)} completed runs on record",
        ),
        typical,
    )


def load_tolerance(rows: Sequence[dict]) -> Optional[Trait]:
    """What a crowded day does to how much gets finished.

    Splits the days at the median number of things due, which adapts to the
    person: "busy" for someone tracking three habits is not "busy" for someone
    tracking twelve.
    """
    days = [r for r in rows if r["due"] > 0 and r["rate"] is not None]
    if len(days) < MIN_LOAD_SAMPLE * 2:
        return None

    loads = sorted(r["due"] for r in days)
    # The *lower* median, so the split actually divides. Taking the upper one
    # puts every day in the light half whenever the load only ever takes two
    # values — which is exactly the case this trait exists to describe.
    median = loads[(len(loads) - 1) // 2]
    light = [r for r in days if r["due"] <= median]
    heavy = [r for r in days if r["due"] > median]
    if len(light) < MIN_LOAD_SAMPLE or len(heavy) < MIN_LOAD_SAMPLE:
        return None  # too little variation in load to compare halves

    light_rate = sum(r["rate"] for r in light) / len(light)
    heavy_rate = sum(r["rate"] for r in heavy) / len(heavy)
    gap = light_rate - heavy_rate
    if abs(gap) < MIN_LOAD_GAP:
        return None

    if gap > 0:
        summary = (
            f"Busy days cost you: you finish {round(heavy_rate * 100)}% when more than "
            f"{median} things are due, against {round(light_rate * 100)}% on lighter days."
        )
    else:
        summary = (
            f"A fuller day suits you — {round(heavy_rate * 100)}% when more than {median} "
            f"things are due, against {round(light_rate * 100)}% on lighter days."
        )
    return Trait(
        key="load_tolerance",
        summary=summary,
        evidence=f"{len(heavy)} busier days against {len(light)} lighter ones",
    )


# ------------------------------------------------------------------ service
class BehaviourProfileService:
    #: A season. Long enough for weekday and load patterns to show, short
    #: enough that it describes who someone is now.
    WINDOW_DAYS = 120

    def __init__(self, session: Session) -> None:
        self.session = session

    def build(self, today: Optional[date] = None) -> BehaviourProfile:
        today = today or date.today()
        start = today - timedelta(days=self.WINDOW_DAYS - 1)

        habits = list(HabitRepository(self.session).list_all(include_archived=True))
        tasks = list(TaskRepository(self.session).list_all())

        profile = BehaviourProfile(traits=[])

        found = peak_hours(self._completion_hours(habits, tasks, start))
        if found:
            trait, window = found
            profile.traits.append(trait)
            profile.peak_hours = window

        from app.services.analytics_service import AnalyticsService

        rows = AnalyticsService(self.session).daily_frame(self.WINDOW_DAYS, today)

        weekday: list[list[int]] = [[0, 0] for _ in range(7)]
        for row in rows:
            i = row["date"].weekday()
            weekday[i][0] += row["done"]
            weekday[i][1] += row["due"]

        found = weekday_reliability([(w[0], w[1]) for w in weekday])
        if found:
            trait, best, worst = found
            profile.traits.append(trait)
            profile.best_weekday, profile.worst_weekday = best, worst

        found = streak_durability(self._completed_runs(habits, start, today))
        if found:
            trait, typical = found
            profile.traits.append(trait)
            profile.typical_streak = typical

        trait = load_tolerance(rows)
        if trait:
            profile.traits.append(trait)

        return profile

    # ------------------------------------------------------------- gathering
    @staticmethod
    def _completion_hours(habits, tasks, start: date) -> list[int]:
        """Local hour of every completion in the window, habits and tasks alike.

        Local, because "when do you work" is a question about the user's day,
        not about UTC.
        """
        hours: list[int] = []
        for habit in habits:
            for log in habit.logs:
                if log.status in SUCCESS_STATUSES and log.date >= start and log.logged_at:
                    hours.append(log.logged_at.astimezone().hour)
        for task in tasks:
            if task.status == TaskStatus.DONE and task.completed_at:
                day = local_day(task.completed_at)
                if day and day >= start:
                    hours.append(task.completed_at.astimezone().hour)
        return hours

    @staticmethod
    def _completed_runs(habits, start: date, today: date) -> list[int]:
        """Lengths of every *finished* run of consecutive successful days.

        Deliberately over consecutive calendar days rather than a habit's own
        schedule: this is about how long someone keeps something up, and a
        weekly habit's "streak" of four is four months, which does not belong
        in the same average.
        """
        runs: list[int] = []
        for habit in habits:
            success = sorted(
                l.date for l in habit.logs if l.status in SUCCESS_STATUSES and l.date >= start
            )
            if not success:
                continue
            run = 1
            for previous, current in zip(success, success[1:]):
                if (current - previous).days == 1:
                    run += 1
                else:
                    if run > 1:
                        runs.append(run)
                    run = 1
            # A run touching today is still going and has no final length yet.
            if run > 1 and success[-1] < today:
                runs.append(run)
        return runs
