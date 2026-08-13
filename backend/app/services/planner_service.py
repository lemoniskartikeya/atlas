"""Smart scheduler — builds an ordered, explainable "Today's Plan".

The planner assembles today's due habits plus a couple of high-leverage open
tasks into time-of-day blocks (morning / afternoon / evening). Within each block
it orders items so the things most likely to slip surface first — *tackle the
shaky ones while you're fresh*.

If a trained completion model is available it enriches that ordering with
per-habit completion probability (Phase 4's ML layer); if not, it falls back to
transparent heuristics (streak protection, time-of-day fit, priority). Either
way, every placed item carries a ``reason`` and a ``confidence`` — the same
contract the recommendation engine honours.

The ML dependency is imported lazily inside :meth:`_ml_predictions`, so this
service (and its router) stays in the always-on core even when scikit-learn
isn't installed.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.enums import Priority, SUCCESS_STATUSES, TimeOfDay
from app.schemas.planner import PlanBlock, PlanItem, PlanResponse
from app.services import ml_gateway
from app.services.habit_service import HabitService
from app.services.interaction_service import InteractionService
from app.services.task_service import TaskService

_PRIORITY_RANK = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}

# Chronological, so display order == list order.
_BLOCK_DEFS: list[tuple[str, str, str]] = [
    ("morning", "Morning", "Before noon"),
    ("afternoon", "Afternoon", "Noon – 5pm"),
    ("evening", "Evening", "After 5pm"),
]

_TOD_BLOCK = {
    TimeOfDay.MORNING: "morning",
    TimeOfDay.AFTERNOON: "afternoon",
    TimeOfDay.EVENING: "evening",
    TimeOfDay.NIGHT: "evening",
}

_BLOCK_WHEN = {
    "morning": "this morning",
    "afternoon": "this afternoon",
    "evening": "tonight",
}

# A model-backed completion probability below this reads as "at risk".
_AT_RISK = 0.6
# How many open tasks to fold into the plan.
_MAX_TASKS = 2


def _now_block(now_hour: int) -> str:
    if now_hour < 12:
        return "morning"
    if now_hour < 17:
        return "afternoon"
    return "evening"


class PlannerService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habits = HabitService(session)
        self.tasks = TaskService(session)

    def build(
        self, today: Optional[date] = None, now_hour: Optional[int] = None
    ) -> PlanResponse:
        today = today or date.today()
        now_hour = now_hour if now_hour is not None else datetime.now().hour
        now_block = _now_block(now_hour)

        preds, reliability = self._ml_predictions(today)
        model_backed = preds is not None
        # Where the user actually does things, when that disagrees with where
        # the planner has been putting them. Empty until someone has corrected
        # the same item several times.
        preferences = InteractionService(self.session).preferred_blocks(today)

        # (sort_key, PlanItem) per block; sorted once at the end.
        buckets: dict[str, list[tuple[tuple, PlanItem]]] = {k: [] for k, _, _ in _BLOCK_DEFS}

        self._place_habits(buckets, preds, reliability, today, now_block, preferences)
        self._place_tasks(buckets, today, now_block)

        blocks: list[PlanBlock] = []
        open_count = 0
        total_minutes = 0
        for key, label, window in _BLOCK_DEFS:
            entries = buckets[key]
            if not entries:
                continue
            entries.sort(key=lambda e: e[0])
            items = [item for _, item in entries]
            minutes = sum((i.duration_min or 0) for i in items if not i.done)
            open_here = sum(1 for i in items if not i.done)
            open_count += open_here
            total_minutes += minutes
            blocks.append(
                PlanBlock(
                    key=key,
                    label=label,
                    window=window,
                    is_now=(key == now_block),
                    minutes=minutes,
                    items=items,
                )
            )

        summary = self._summary(blocks, open_count, model_backed, now_block)

        return PlanResponse(
            date=today,
            generated_at=datetime.now(),
            now_hour=now_hour,
            now_block=now_block,
            model_backed=model_backed,
            reliability=round(reliability, 3) if reliability is not None else None,
            summary=summary,
            open_count=open_count,
            total_minutes=total_minutes,
            blocks=blocks,
        )

    # ------------------------------------------------------------------ habits
    def _place_habits(
        self, buckets, preds, reliability, today, now_block, preferences=None
    ) -> None:
        for habit in self.habits.list_habits(include_archived=False):
            success_dates = {l.date for l in habit.logs if l.status in SUCCESS_STATUSES}
            if not self.habits.is_due_today(habit, today, success_dates):
                continue

            today_log = self.habits.today_log(habit, today)
            done = bool(today_log and today_log.status in SUCCESS_STATUSES)
            streak = self.habits.compute_stats(habit, today).current_streak

            # ANY-time habits land in the block you're in now, so they read as "now".
            block = _TOD_BLOCK.get(habit.time_preference, now_block)

            # Observed behaviour outranks the stated preference. Someone who
            # set "morning" once and has run every evening since is telling us
            # something more reliable than the dropdown did.
            learned = (preferences or {}).get(habit.id)
            moved_from = None
            if learned and learned[0] != block:
                moved_from, block = block, learned[0]

            pred = preds.get(habit.id) if preds else None
            prob = pred["probability"] if pred else None
            risk: Optional[str] = None
            if prob is not None and not done:
                risk = "at-risk" if prob < _AT_RISK else "steady"

            reason, confidence = self._habit_reason(
                done=done,
                prob=prob,
                risk=risk,
                streak=streak,
                block=block,
                time_pref=habit.time_preference,
                explanation=pred["explanation"] if pred else None,
                reliability=reliability,
            )
            if moved_from:
                # Say it out loud: an item that silently moved would look like
                # a bug to the person who chose the original slot.
                reason = (
                    f"You usually finish this in the {block} — moved here from the "
                    f"{moved_from} ({learned[1]} times recently). " + reason
                )

            item = PlanItem(
                id=habit.id,
                kind="habit",
                title=habit.title,
                color=habit.color,
                duration_min=habit.estimated_duration_min,
                priority=habit.priority.value,
                done=done,
                probability=round(prob, 3) if prob is not None else None,
                risk=risk,
                reason=reason,
                confidence=confidence,
            )
            sort_key = (
                done,  # not-done first
                0 if risk == "at-risk" else 1,  # shaky ones first
                _PRIORITY_RANK.get(habit.priority, 2),
                prob if prob is not None else 0.5,  # lower probability earlier
                -streak,  # protect longer streaks earlier
                habit.estimated_duration_min or 9999,  # quick wins earlier
            )
            buckets[block].append((sort_key, item))

    # ------------------------------------------------------------------- tasks
    def _place_tasks(self, buckets, today, now_block) -> None:
        # A task with a day already chosen in the future is not today's problem.
        # Without this, deferring something would leave it sitting in the plan,
        # which reads as the button having done nothing.
        open_tasks = [
            t
            for t in self.tasks.list_tasks("open", today)
            if not (t.scheduled_for and t.scheduled_for > today)
        ][:_MAX_TASKS]
        for task in open_tasks:
            overdue = bool(task.due_date and task.due_date < today)
            due_txt = ""
            if task.due_date:
                due_txt = " · overdue" if overdue else f" · due {task.due_date.isoformat()}"
            reason = f"High-leverage open task to slot in{due_txt}."
            confidence = {
                Priority.CRITICAL: 0.7,
                Priority.HIGH: 0.65,
                Priority.MEDIUM: 0.55,
                Priority.LOW: 0.5,
            }.get(task.priority, 0.55)

            item = PlanItem(
                id=task.id,
                kind="task",
                title=task.title,
                color=None,
                duration_min=task.estimated_effort_min,
                priority=task.priority.value,
                done=False,
                probability=None,
                risk=None,
                reason=reason,
                confidence=confidence,
            )
            sort_key = (
                False,
                1,  # tasks sort after any at-risk habits
                _PRIORITY_RANK.get(task.priority, 2),
                0.5,
                0,
                task.estimated_effort_min or 9999,
            )
            buckets[now_block].append((sort_key, item))

    # --------------------------------------------------------------- reasoning
    @staticmethod
    def _habit_reason(
        *,
        done: bool,
        prob: Optional[float],
        risk: Optional[str],
        streak: int,
        block: str,
        time_pref: TimeOfDay,
        explanation: Optional[str],
        reliability: Optional[float],
    ) -> tuple[str, float]:
        if done:
            return "Already logged today — nice.", 0.9

        # Model-backed: speak in probabilities.
        if prob is not None:
            p = round(prob * 100)
            conf = round(reliability, 2) if reliability else 0.6
            if risk == "at-risk":
                tail = f" {explanation}" if explanation else ""
                return (
                    f"Only ~{p}% likely on days like today — front-load it while you're fresh.{tail}",
                    conf,
                )
            return f"~{p}% likely — a reliable win to lock in.", conf

        # Heuristic fallback.
        if streak >= 3:
            return (
                f"Protects your {streak}-day streak.",
                round(min(0.9, 0.55 + streak * 0.03), 2),
            )
        if time_pref != TimeOfDay.ANY:
            return f"Set for the {block}.", 0.55
        return "On today's list.", 0.5

    @staticmethod
    def _summary(
        blocks: list[PlanBlock], open_count: int, model_backed: bool, now_block: str
    ) -> str:
        if not blocks:
            return "Nothing due today — add a habit or task to plan your day."
        if open_count == 0:
            return "Everything's logged — you're all clear for today. Nice work."

        noun = "thing" if open_count == 1 else "things"
        base = f"{open_count} {noun} left today"

        # The single genuinely at-risk item (model-backed) leads the headline —
        # but phrased with awareness of *when* it's scheduled, so "start with"
        # never contradicts an evening habit's block.
        riskiest: Optional[PlanItem] = None
        riskiest_block: Optional[str] = None
        for block in blocks:
            for item in block.items:
                if item.done or item.probability is None or item.risk != "at-risk":
                    continue
                if riskiest is None or item.probability < (riskiest.probability or 1.0):
                    riskiest = item
                    riskiest_block = block.key

        if model_backed and riskiest is not None:
            p = round((riskiest.probability or 0) * 100)
            when = _BLOCK_WHEN.get(riskiest_block or "", "")
            if riskiest_block == now_block:
                return f"{base}. Start with “{riskiest.title}” — only ~{p}% likely today."
            return f"{base}. Watch “{riskiest.title}” {when} — only ~{p}% likely."
        if model_backed:
            return f"{base}. You're tracking well — keep your {now_block} block moving."
        return f"{base}. Your {now_block} block is the focus."

    # ------------------------------------------------------------------- ML glue
    def _ml_predictions(
        self, today: date
    ) -> tuple[Optional[dict[str, dict]], Optional[float]]:
        """Today's completion probabilities via the shared, guarded ML gateway."""
        return ml_gateway.habit_predictions(self.session, today)
