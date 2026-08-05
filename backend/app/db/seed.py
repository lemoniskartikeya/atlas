"""Seed the database with ~45 days of realistic demo data.

Run:  python -m app.db.seed          (skips if already seeded)
      python -m app.db.seed --force  (wipes and reseeds)

The point of a rich, backdated history is that streaks, consistency, analytics —
and, later, the ML feature pipeline — have something real to work with immediately.
"""
from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete

from app.core.database import SessionLocal, engine
from app.domain.enums import (
    Difficulty,
    Frequency,
    HabitLogStatus,
    Priority,
    TaskStatus,
    TimeOfDay,
)
from app.models.base import Base
from app.models.habit import Habit, HabitLog
from app.models.journal import JournalEntry
from app.models.task import Project, Task

RNG = random.Random(42)
DAYS = 45

_TOD_HOURS = {
    TimeOfDay.MORNING: (6, 9),
    TimeOfDay.AFTERNOON: (13, 16),
    TimeOfDay.EVENING: (19, 21),
    TimeOfDay.NIGHT: (22, 23),
    TimeOfDay.ANY: (8, 20),
}

_SKIP_REASONS = ["Too tired", "Ran out of time", "Traveling", "Felt unwell", "Packed schedule"]

# Each spec drives both the Habit row and how its historical logs are generated.
_HABIT_SPECS = [
    dict(title="Meditate", category="Mindfulness", frequency=Frequency.DAILY,
         time_preference=TimeOfDay.MORNING, estimated_duration_min=10,
         difficulty=Difficulty.EASY, required_energy=2, color="#8FA6B2",
         p=0.88, recent_boost=True),
    dict(title="Deep Work", category="Work", frequency=Frequency.DAILY,
         time_preference=TimeOfDay.MORNING, estimated_duration_min=90,
         difficulty=Difficulty.HARD, required_energy=5, priority=Priority.HIGH,
         color="#9AA7B8", p=0.72, dur=(60, 120), recent_boost=True),
    dict(title="Exercise", category="Health", frequency=Frequency.CUSTOM,
         custom_days=[0, 2, 4], time_preference=TimeOfDay.AFTERNOON,
         estimated_duration_min=45, difficulty=Difficulty.HARD, required_energy=4,
         color="#A7B0A0", p=0.70, dur=(35, 55)),
    dict(title="Read", category="Growth", frequency=Frequency.DAILY,
         time_preference=TimeOfDay.EVENING, estimated_duration_min=30,
         difficulty=Difficulty.MEDIUM, required_energy=2, color="#B2A79B", p=0.78),
    dict(title="Drink Water", category="Health", frequency=Frequency.DAILY,
         time_preference=TimeOfDay.ANY, estimated_duration_min=2,
         difficulty=Difficulty.TRIVIAL, required_energy=1, color="#9BB4C0", p=0.92),
    dict(title="Journal", category="Mindfulness", frequency=Frequency.DAILY,
         time_preference=TimeOfDay.NIGHT, estimated_duration_min=5,
         difficulty=Difficulty.EASY, required_energy=1, color="#B8AEC4", p=0.62),
]


def _logged_at(d: date, tod: TimeOfDay) -> datetime:
    lo, hi = _TOD_HOURS.get(tod, (8, 20))
    return datetime(d.year, d.month, d.day, RNG.randint(lo, hi), RNG.randint(0, 59), tzinfo=timezone.utc)


def _make_habit(spec: dict) -> Habit:
    habit = Habit(
        title=spec["title"],
        category=spec["category"],
        frequency=spec["frequency"],
        custom_days=spec.get("custom_days"),
        time_preference=spec["time_preference"],
        estimated_duration_min=spec["estimated_duration_min"],
        difficulty=spec["difficulty"],
        required_energy=spec["required_energy"],
        priority=spec.get("priority", Priority.MEDIUM),
        color=spec.get("color"),
    )
    habit.created_at = datetime.now(timezone.utc) - timedelta(days=DAYS)
    return habit


def _seed_logs(habit: Habit, spec: dict, today: date) -> None:
    for offset in range(DAYS, -1, -1):
        d = today - timedelta(days=offset)
        if spec["frequency"] == Frequency.CUSTOM and d.weekday() not in spec["custom_days"]:
            continue

        p = spec["p"]
        if spec.get("recent_boost") and offset <= 5:
            p = min(0.97, p + 0.12)  # keep recent days strong for nice live streaks

        roll = RNG.random()
        if roll < p:
            status = HabitLogStatus.COMPLETED
        elif roll < p + 0.08:
            status = HabitLogStatus.PARTIAL
        elif RNG.random() < 0.5:
            status = HabitLogStatus.SKIPPED
        else:
            continue  # no log at all for this day (a genuine miss)

        log = HabitLog(date=d, status=status, logged_at=_logged_at(d, spec["time_preference"]))
        if status in (HabitLogStatus.COMPLETED, HabitLogStatus.PARTIAL):
            log.mood_after = RNG.randint(3, 5)
            log.energy_before = RNG.randint(2, 4)
            log.energy_after = RNG.randint(3, 5)
            if "dur" in spec:
                log.duration_min = RNG.randint(*spec["dur"])
        else:
            log.reason = RNG.choice(_SKIP_REASONS)
        habit.logs.append(log)


def _seed_tasks(session, today: date) -> int:
    app_proj = Project(name="Atlas App", color="#9AA7B8", description="Building the second brain")
    personal = Project(name="Personal", color="#B2A79B")

    tasks = [
        Task(title="Write ML feature-store spec", project=app_proj, priority=Priority.CRITICAL,
             due_date=today, estimated_effort_min=120, status=TaskStatus.IN_PROGRESS,
             tags=["ml", "writing"], focus_required=5),
        Task(title="Design onboarding flow", project=app_proj, priority=Priority.HIGH,
             due_date=today, estimated_effort_min=90, status=TaskStatus.TODO,
             tags=["design"], focus_required=4),
        Task(title="Review PR #42", project=app_proj, priority=Priority.HIGH,
             due_date=today - timedelta(days=1), estimated_effort_min=30, status=TaskStatus.TODO),
        Task(title="Refactor habit repository", project=app_proj, priority=Priority.MEDIUM,
             due_date=today + timedelta(days=1), estimated_effort_min=60, status=TaskStatus.TODO),
        Task(title="Plan weekly review", project=personal, priority=Priority.MEDIUM,
             scheduled_for=today, estimated_effort_min=20, status=TaskStatus.TODO),
        Task(title="Grocery run", project=personal, priority=Priority.LOW, due_date=today,
             estimated_effort_min=40, status=TaskStatus.TODO, location="Errand"),
        Task(title="Book dentist", project=personal, priority=Priority.MEDIUM,
             due_date=today + timedelta(days=3), status=TaskStatus.TODO),
        Task(title="Ship dashboard v1", project=app_proj, priority=Priority.HIGH,
             status=TaskStatus.DONE, completed_at=datetime.now(timezone.utc) - timedelta(days=1)),
    ]
    session.add_all([app_proj, personal, *tasks])
    return len(tasks)


def _seed_journal(session, today: date) -> int:
    gratitude = ["Morning coffee", "A good night's sleep", "Supportive friends",
                 "Quiet focus time", "A short walk outside"]
    wins = ["Shipped a feature", "Cleared the inbox", "Hit my step goal",
            "Solved a tricky bug", "Read 20 pages"]
    count = 0
    for offset in range(11, -1, -1):
        d = today - timedelta(days=offset)
        # Make the most recent entry a short-sleep day so the wellbeing recommendation shows.
        sleep = 6.2 if offset == 0 else round(RNG.uniform(6.4, 8.2), 1)
        session.add(
            JournalEntry(
                date=d,
                mood=RNG.randint(3, 5),
                energy=RNG.randint(2, 5),
                sleep_hours=sleep,
                gratitude=RNG.choice(gratitude),
                wins=RNG.choice(wins),
            )
        )
        count += 1
    return count


def _wipe(session) -> None:
    for model in (HabitLog, Habit, Task, Project, JournalEntry):
        session.execute(delete(model))
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Atlas with demo data")
    parser.add_argument("--force", action="store_true", help="wipe existing data first")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        existing = session.query(Habit).count()
        if existing and not args.force:
            print(f"Already seeded ({existing} habits present). Use --force to reset.")
            return
        if args.force:
            _wipe(session)

        today = date.today()
        for spec in _HABIT_SPECS:
            habit = _make_habit(spec)
            _seed_logs(habit, spec, today)
            session.add(habit)

        n_tasks = _seed_tasks(session, today)
        n_journal = _seed_journal(session, today)
        session.commit()

        n_logs = session.query(HabitLog).count()
        print(
            f"Seeded {len(_HABIT_SPECS)} habits, {n_logs} habit logs, "
            f"{n_tasks} tasks, {n_journal} journal entries."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
