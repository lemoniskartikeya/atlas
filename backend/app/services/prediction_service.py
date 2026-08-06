"""Prediction engine: how today is likely to end, streak-break risk, burnout.

Leans on the Phase-4 completion model when it's trained (per-habit probabilities
via the shared ML gateway) and degrades to transparent trend heuristics
otherwise. Burnout is deliberately a documented weighted formula over sleep,
energy, completion, and load — not a learned black box — so its drivers are
always inspectable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.enums import SUCCESS_STATUSES
from app.models.habit import Habit
from app.schemas.habit import HabitStats
from app.schemas.prediction import (
    BurnoutSignal,
    ExpectedCompletion,
    PredictionReport,
    StreakRisk,
)
from app.services import ml_gateway, streaks
from app.services.habit_service import HabitService
from app.services.journal_service import JournalService
from app.services.task_service import TaskService


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _avg(values: list[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return (sum(vals) / len(vals)) if vals else None


@dataclass
class _Due:
    habit: Habit
    done: bool
    stats: HabitStats
    prob: Optional[float]  # today's completion probability, when model-backed


class PredictionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habits = HabitService(session)
        self.tasks = TaskService(session)
        self.journals = JournalService(session)

    def build(self, today: Optional[date] = None) -> PredictionReport:
        today = today or date.today()
        preds, reliability = ml_gateway.habit_predictions(self.session, today)
        model_backed = preds is not None

        all_habits = list(self.habits.list_habits(include_archived=False))
        due: list[_Due] = []
        for habit in all_habits:
            success_dates = {l.date for l in habit.logs if l.status in SUCCESS_STATUSES}
            if not self.habits.is_due_today(habit, today, success_dates):
                continue
            today_log = self.habits.today_log(habit, today)
            done = bool(today_log and today_log.status in SUCCESS_STATUSES)
            stats = self.habits.compute_stats(habit, today)
            prob = preds[habit.id]["probability"] if (preds and habit.id in preds) else None
            due.append(_Due(habit, done, stats, prob))

        return PredictionReport(
            date=today,
            model_backed=model_backed,
            reliability=round(reliability, 3) if reliability is not None else None,
            expected_completion=self._expected(due, reliability, model_backed),
            streak_risks=self._streak_risks(due, model_backed),
            burnout=self._burnout(today, all_habits, due),
        )

    # ---------------------------------------------------------- expected today
    @staticmethod
    def _expected(
        due: list[_Due], reliability: Optional[float], model_backed: bool
    ) -> ExpectedCompletion:
        n_due = len(due)
        done = sum(1 for d in due if d.done)
        remaining = [d for d in due if not d.done]

        if model_backed:
            expected_additional = sum((d.prob or 0.0) for d in remaining)
            confidence = reliability
            basis = "summing the model's completion probabilities for what's left"
        else:
            expected_additional = sum(d.stats.consistency_30d for d in remaining)
            confidence = None
            basis = "your recent completion rates"

        expected_total = done + expected_additional
        rate = (expected_total / n_due) if n_due else 0.0

        if n_due == 0:
            reason = "Nothing due today — a clean slate."
        else:
            reason = (
                f"On pace for ~{expected_total:.1f} of {n_due} today "
                f"({done} already done), {basis}."
            )

        return ExpectedCompletion(
            due=n_due,
            done=done,
            remaining=len(remaining),
            expected_total=round(expected_total, 2),
            expected_rate=round(_clamp01(rate), 3),
            confidence=round(confidence, 3) if confidence is not None else None,
            model_backed=model_backed,
            reason=reason,
        )

    # ------------------------------------------------------------ streak risks
    @staticmethod
    def _streak_risks(due: list[_Due], model_backed: bool) -> list[StreakRisk]:
        risks: list[StreakRisk] = []
        for d in due:
            if d.done or d.stats.current_streak < 2:
                continue
            if d.prob is not None:
                risk = 1.0 - d.prob
                basis = f"~{round(d.prob * 100)}% likely to complete today"
            else:
                risk = _clamp01(1.0 - d.stats.consistency_30d)
                basis = f"completed {round(d.stats.consistency_30d * 100)}% of the time lately"
            level = "high" if risk >= 0.5 else "medium" if risk >= 0.3 else "low"
            if level == "low":
                continue
            risks.append(
                StreakRisk(
                    habit_id=d.habit.id,
                    title=d.habit.title,
                    current_streak=d.stats.current_streak,
                    probability=round(d.prob, 3) if d.prob is not None else None,
                    risk=round(risk, 3),
                    level=level,
                    reason=(
                        f"{d.stats.current_streak}-day streak on the line — {basis}, "
                        "and it isn't logged yet."
                    ),
                )
            )
        # Longer streaks at higher risk float to the top.
        risks.sort(key=lambda r: r.risk * (1 + r.current_streak / 10), reverse=True)
        return risks[:4]

    # ---------------------------------------------------------------- burnout
    def _burnout(
        self, today: date, all_habits: list[Habit], due: list[_Due]
    ) -> BurnoutSignal:
        """Transparent 0..1 composite: sleep + energy + completion + load.

        score = 0.30·sleep_debt + 0.25·low_energy + 0.25·missed_completion
                + 0.20·high_load
        """
        window_start = today - timedelta(days=6)
        recent = [j for j in self.journals.recent(14) if j.date >= window_start]
        avg_sleep = _avg([j.sleep_hours for j in recent])
        avg_energy = _avg([float(j.energy) for j in recent if j.energy is not None])

        weekly = self._weekly_consistency(all_habits, today)
        load = len(due) + len(self.tasks.tasks.open_tasks())

        sleep_risk = _clamp01((6.8 - avg_sleep) / 2.0) if avg_sleep is not None else 0.0
        energy_risk = _clamp01((3.2 - avg_energy) / 2.0) if avg_energy is not None else 0.0
        completion_risk = _clamp01((0.6 - weekly) / 0.6)
        load_risk = _clamp01((load - 8) / 10.0)

        score = (
            0.30 * sleep_risk
            + 0.25 * energy_risk
            + 0.25 * completion_risk
            + 0.20 * load_risk
        )
        level = "elevated" if score >= 0.6 else "moderate" if score >= 0.33 else "low"

        drivers: list[str] = []
        if sleep_risk >= 0.4 and avg_sleep is not None:
            drivers.append(f"sleep averaging {avg_sleep:.1f}h")
        if energy_risk >= 0.4 and avg_energy is not None:
            drivers.append(f"energy averaging {avg_energy:.1f}/5")
        if completion_risk >= 0.4:
            drivers.append(f"completion down to {round(weekly * 100)}% this week")
        if load_risk >= 0.4:
            drivers.append(f"a heavy load ({load} things on your plate)")

        if level == "low":
            reason = "Sustainable pace — sleep, energy, completion, and load all look healthy."
        elif drivers:
            reason = "Signals building: " + ", ".join(drivers) + "."
        else:
            reason = "Some strain across sleep, energy, completion, and load."

        return BurnoutSignal(
            score=round(score, 3), level=level, drivers=drivers, reason=reason
        )

    def _weekly_consistency(self, habits: list[Habit], today: date) -> float:
        num = den = 0.0
        for habit in habits:
            success_dates = {l.date for l in habit.logs if l.status in SUCCESS_STATUSES}
            for i in range(7):
                d = today - timedelta(days=i)
                if streaks.is_occurrence_day(habit.frequency, habit.custom_days, d):
                    den += 1
                    if d in success_dates:
                        num += 1
        return (num / den) if den else 0.0
