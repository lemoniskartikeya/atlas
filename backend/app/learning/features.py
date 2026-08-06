"""Feature engineering for the completion-probability model.

One training example per (habit, occurrence-day) with a *settled* outcome. Every
behavioural feature uses only information available strictly BEFORE that day, so the
model never peeks at the label (no leakage). Journal signals come from the prior day.

Missing values are left as NaN on purpose — HistGradientBoosting handles them
natively, which matters because journals are sparse.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import cos, pi, sin

import numpy as np
from sqlalchemy.orm import Session

from app.domain.enums import Difficulty, Frequency, Priority, SUCCESS_STATUSES, TimeOfDay
from app.models.habit import Habit
from app.repositories.habit_repo import HabitRepository
from app.repositories.journal_repo import JournalRepository
from app.services import streaks

FEATURE_NAMES = [
    "dow_sin",
    "dow_cos",
    "is_weekend",
    "month",
    "difficulty",
    "required_energy",
    "motivation",
    "est_duration",
    "priority",
    "tp_morning",
    "tp_afternoon",
    "tp_evening",
    "tp_night",
    "tp_any",
    "rate_7",
    "rate_30",
    "streak_in",
    "days_since_last",
    "done_prev",
    "mood_prev",
    "energy_prev",
    "sleep_prev",
]

NAN = float("nan")
_DIFFICULTY = {Difficulty.TRIVIAL: 0, Difficulty.EASY: 1, Difficulty.MEDIUM: 2, Difficulty.HARD: 3}
_PRIORITY = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2, Priority.CRITICAL: 3}


def _static(habit: Habit) -> dict:
    tp = habit.time_preference
    return {
        "difficulty": float(_DIFFICULTY.get(habit.difficulty, 2)),
        "required_energy": float(habit.required_energy),
        "motivation": float(habit.motivation_level),
        "est_duration": float(habit.estimated_duration_min or 0),
        "priority": float(_PRIORITY.get(habit.priority, 1)),
        "tp_morning": 1.0 if tp == TimeOfDay.MORNING else 0.0,
        "tp_afternoon": 1.0 if tp == TimeOfDay.AFTERNOON else 0.0,
        "tp_evening": 1.0 if tp == TimeOfDay.EVENING else 0.0,
        "tp_night": 1.0 if tp == TimeOfDay.NIGHT else 0.0,
        "tp_any": 1.0 if tp == TimeOfDay.ANY else 0.0,
    }


def _calendar(d: date) -> dict:
    dow = d.weekday()
    return {
        "dow_sin": sin(2 * pi * dow / 7),
        "dow_cos": cos(2 * pi * dow / 7),
        "is_weekend": 1.0 if dow >= 5 else 0.0,
        "month": float(d.month),
    }


def _behaviour(history: list[bool]) -> dict:
    """Rolling features from prior occurrence-day outcomes (ordered oldest→newest)."""
    if not history:
        return {
            "rate_7": NAN,
            "rate_30": NAN,
            "streak_in": 0.0,
            "days_since_last": NAN,
            "done_prev": NAN,
        }
    last7 = history[-7:]
    last30 = history[-30:]
    streak = 0
    for v in reversed(history):
        if v:
            streak += 1
        else:
            break
    days_since_last = NAN
    for i, v in enumerate(reversed(history)):
        if v:
            days_since_last = float(i)
            break
    return {
        "rate_7": sum(last7) / len(last7),
        "rate_30": sum(last30) / len(last30),
        "streak_in": float(streak),
        "days_since_last": days_since_last,
        "done_prev": 1.0 if history[-1] else 0.0,
    }


def _journal_prev(journals: dict, d: date) -> dict:
    j = journals.get(d - timedelta(days=1))
    return {
        "mood_prev": float(j.mood) if j and j.mood is not None else NAN,
        "energy_prev": float(j.energy) if j and j.energy is not None else NAN,
        "sleep_prev": float(j.sleep_hours) if j and j.sleep_hours is not None else NAN,
    }


def _row(static: dict, cal: dict, beh: dict, jrn: dict) -> list[float]:
    merged = {**cal, **static, **beh, **jrn}
    return [merged[name] for name in FEATURE_NAMES]


def _occurrence_days(habit: Habit, start: date, end: date) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        if streaks.is_occurrence_day(habit.frequency, habit.custom_days, d):
            days.append(d)
        d += timedelta(days=1)
    return days


def _due_today(habit: Habit, today: date) -> bool:
    if habit.frequency == Frequency.CUSTOM:
        return today.weekday() in set(habit.custom_days or [])
    return True  # daily / weekly / monthly all "occur" today


def build_training(session: Session, today: date | None = None):
    """Return (X, y, dates) over every habit's settled occurrence days."""
    today = today or date.today()
    habits = HabitRepository(session).list_all(include_archived=True)
    journals = {j.date: j for j in JournalRepository(session).recent(2000)}

    rows: list[list[float]] = []
    labels: list[int] = []
    dates: list[date] = []
    for habit in habits:
        logs = list(habit.logs)
        if not logs:
            continue
        success = {l.date for l in logs if l.status in SUCCESS_STATUSES}
        earliest = min(l.date for l in logs)
        occ = _occurrence_days(habit, earliest, today - timedelta(days=1))
        static = _static(habit)
        history: list[bool] = []
        for d in occ:
            rows.append(_row(static, _calendar(d), _behaviour(history), _journal_prev(journals, d)))
            labels.append(1 if d in success else 0)
            dates.append(d)
            history.append(d in success)

    X = np.array(rows, dtype=float) if rows else np.empty((0, len(FEATURE_NAMES)))
    y = np.array(labels, dtype=int)
    return X, y, dates


def build_inference(session: Session, today: date | None = None):
    """Return [(habit, feature_vector, done_today)] for habits due today."""
    today = today or date.today()
    habits = HabitRepository(session).list_all(include_archived=False)
    journals = {j.date: j for j in JournalRepository(session).recent(2000)}

    out = []
    for habit in habits:
        if not _due_today(habit, today):
            continue
        logs = list(habit.logs)
        success = {l.date for l in logs if l.status in SUCCESS_STATUSES}
        earliest = min((l.date for l in logs), default=today)
        occ = _occurrence_days(habit, earliest, today - timedelta(days=1))
        history = [d in success for d in occ]
        vec = _row(_static(habit), _calendar(today), _behaviour(history), _journal_prev(journals, today))
        done = any(l.date == today and l.status in SUCCESS_STATUSES for l in logs)
        out.append((habit, np.array(vec, dtype=float), done))
    return out
