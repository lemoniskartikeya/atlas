"""Smart notifications.

Notifications are derived fresh from live signals (the prediction engine + open
tasks) and *time-gated* so they arrive when they're useful — a morning brief
early, streak-slip nudges from midday, an end-of-day wrap after 8pm. The engine
is stateless about content; only the user's read/dismiss interaction is
persisted, keyed by each notification's deterministic id.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import NotificationOut, NotificationsResponse
from app.services.prediction_service import PredictionService
from app.services.task_service import TaskService

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
_KIND_RANK = {"task": 0, "risk": 1, "streak": 1, "wellbeing": 2, "eod": 3, "brief": 4}


class NotificationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = NotificationRepository(session)
        self.tasks = TaskService(session)

    def build(
        self, today: Optional[date] = None, now_hour: Optional[int] = None
    ) -> NotificationsResponse:
        today = today or date.today()
        now_hour = now_hour if now_hour is not None else datetime.now().hour

        candidates = self._candidates(today, now_hour)

        states = self.repo.status_map()
        visible: list[NotificationOut] = []
        for n in candidates:
            status = states.get(n.id)
            if status == "dismissed":
                continue
            n.read = status == "read"
            visible.append(n)

        visible.sort(
            key=lambda n: (_PRIORITY_RANK.get(n.priority, 3), _KIND_RANK.get(n.kind, 9))
        )
        unread = sum(1 for n in visible if not n.read)
        return NotificationsResponse(
            generated_at=datetime.now(), unread=unread, notifications=visible
        )

    # -------------------------------------------------------------- mutations
    def mark_read(self, notification_id: str) -> None:
        self.repo.set_status(notification_id, "read")
        self.repo.commit()

    def dismiss(self, notification_id: str) -> None:
        self.repo.set_status(notification_id, "dismissed")
        self.repo.commit()

    def mark_all_read(
        self, today: Optional[date] = None, now_hour: Optional[int] = None
    ) -> None:
        for n in self.build(today, now_hour).notifications:
            if not n.read:
                self.repo.set_status(n.id, "read")
        self.repo.commit()

    # ---------------------------------------------------------- candidate rules
    def _candidates(self, today: date, now_hour: int) -> list[NotificationOut]:
        report = PredictionService(self.session).build(today)
        ec = report.expected_completion
        out: list[NotificationOut] = []
        d = today.isoformat()

        # 1) Morning brief (5–11), when habits remain.
        if 5 <= now_hour < 11 and ec.remaining > 0:
            pace = f" · on pace for ~{ec.expected_total:.0f}" if ec.model_backed else ""
            out.append(
                NotificationOut(
                    id=f"brief:{d}",
                    kind="brief",
                    priority="low",
                    title="Your day at a glance",
                    body=f"{ec.remaining} of {ec.due} habits still to do{pace}.",
                    reason=ec.reason,
                    action_label="Open plan",
                    action_route="/plan",
                )
            )

        # 2) Streak-slip / at-risk nudges (from midday), top 2.
        if now_hour >= 12:
            for r in report.streak_risks[:2]:
                kind = "streak" if r.current_streak >= 3 else "risk"
                out.append(
                    NotificationOut(
                        id=f"{kind}:{r.habit_id}:{d}",
                        kind=kind,
                        priority="high" if r.level == "high" else "medium",
                        title=f"“{r.title}” is still open",
                        body=(
                            f"{r.current_streak}-day streak · "
                            f"~{round(r.risk * 100)}% chance it slips today"
                        ),
                        reason=r.reason,
                        action_label="Log it",
                        action_route="/plan",
                    )
                )

        # 3) Overdue tasks (anytime), top 3.
        overdue = [
            t
            for t in self.tasks.list_tasks("open", today)
            if t.due_date and t.due_date < today
        ]
        for t in overdue[:3]:
            days = (today - t.due_date).days
            out.append(
                NotificationOut(
                    id=f"task:{t.id}",
                    kind="task",
                    priority="high",
                    title=f"Overdue: {t.title}",
                    body=f"Due {t.due_date.isoformat()} · {days}d ago",
                    reason="An open task is past its due date.",
                    action_label="View tasks",
                    action_route="/tasks",
                )
            )

        # 4) Burnout — only when it's genuinely elevated, so it stays rare.
        if report.burnout.level == "elevated":
            out.append(
                NotificationOut(
                    id=f"burnout:{d}",
                    kind="wellbeing",
                    priority="medium",
                    title="Ease off — burnout signals are rising",
                    body="Protect sleep and win 1–2 keystone habits rather than spreading thin.",
                    reason=report.burnout.reason,
                    action_label="See outlook",
                    action_route="/plan",
                )
            )

        # 5) End-of-day wrap (20:00+), when habits remain.
        if now_hour >= 20 and ec.remaining > 0:
            n = ec.remaining
            out.append(
                NotificationOut(
                    id=f"eod:{d}",
                    kind="eod",
                    priority="medium",
                    title="A few still open before bed",
                    body=f"{n} habit{'s' if n != 1 else ''} left today — a quick win keeps momentum.",
                    reason="Late in the day with habits still unlogged.",
                    action_label="Open plan",
                    action_route="/plan",
                )
            )

        return out
