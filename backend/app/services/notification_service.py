"""Smart notifications.

Notifications are derived fresh from live signals (the prediction engine + open
tasks) and *time-gated* so they arrive when they're useful — a morning brief
early, streak-slip nudges from midday, an end-of-day wrap after 8pm. The engine
is stateless about content; only the user's read/dismiss interaction is
persisted, keyed by each notification's deterministic id.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import NotificationOut, NotificationsResponse, SnoozedStream
from app.services.prediction_service import PredictionService
from app.services.task_service import TaskService

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
_KIND_RANK = {"task": 0, "risk": 1, "streak": 1, "wellbeing": 2, "eod": 3, "brief": 4}

# --- back-off ---------------------------------------------------------------
# A nudge that keeps getting dismissed is a nudge that isn't working. After
# this many *consecutive* dismissals (a single read resets the run, because
# engagement means it landed), the stream goes quiet for a while.
_BACKOFF_AFTER = 3
# Cooldown grows with persistence, so Atlas stops arguing with the user.
# (dismissal streak -> days of silence)
_COOLDOWN_LADDER = [(8, 21), (5, 7), (_BACKOFF_AFTER, 3)]

_KIND_LABEL = {
    "brief": "Morning brief",
    "streak": "Streak nudges",
    "risk": "At-risk nudges",
    "task": "Overdue tasks",
    "wellbeing": "Burnout warnings",
    "eod": "End-of-day wrap",
}


_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _cooldown_days(streak: int) -> int:
    for threshold, days in _COOLDOWN_LADDER:
        if streak >= threshold:
            return days
    return 0


def _aware(dt: datetime) -> datetime:
    """Naive rows out of SQLite were written as UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _short_date(dt: datetime) -> str:
    """`8 Aug`. Built by hand — strftime's `%-d` is glibc-only and dies on Windows."""
    local = dt.astimezone()
    return f"{local.day} {_MONTHS[local.month - 1]}"


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
        now = datetime.now(timezone.utc)
        visible: list[NotificationOut] = []
        snoozed: dict[tuple[str, Optional[str]], SnoozedStream] = {}

        for n in candidates:
            status = states.get(n.id)
            if status == "dismissed":
                continue

            # Has this particular stream been ignored enough to go quiet?
            quiet, until, streak = self._backoff(n.kind, n.target, now)
            if quiet and until is not None:
                key = (n.kind, n.target)
                snoozed.setdefault(
                    key,
                    SnoozedStream(
                        kind=n.kind,
                        target=n.target,
                        label=self._stream_label(n),
                        dismissals=streak,
                        until=until,
                        reason=(
                            f"Dismissed {streak} times in a row — paused until "
                            f"{_short_date(until)}."
                        ),
                    ),
                )
                continue

            n.read = status == "read"
            visible.append(n)

        visible.sort(
            key=lambda n: (_PRIORITY_RANK.get(n.priority, 3), _KIND_RANK.get(n.kind, 9))
        )
        unread = sum(1 for n in visible if not n.read)
        return NotificationsResponse(
            generated_at=datetime.now(),
            unread=unread,
            notifications=visible,
            snoozed=list(snoozed.values()),
        )

    # ------------------------------------------------------------------ back-off
    def _backoff(
        self, kind: str, target: Optional[str], now: datetime
    ) -> tuple[bool, Optional[datetime], int]:
        """``(is_quiet, quiet_until, consecutive_dismissals)`` for one stream.

        Counts dismissals back from the most recent interaction and stops at the
        first read: opening a nudge is evidence it worked, so engagement clears
        the back-off rather than merely pausing it.
        """
        rows = self.repo.history(kind, target)
        streak = 0
        last_dismissed: Optional[datetime] = None
        for row in rows:
            if row.status != "dismissed":
                break
            streak += 1
            if last_dismissed is None:
                last_dismissed = _aware(row.created_at)

        days = _cooldown_days(streak)
        if not days or last_dismissed is None:
            return False, None, streak

        until = last_dismissed + timedelta(days=days)
        # Once the cooldown lapses, one nudge is allowed through as a probe. If
        # it's dismissed too, the streak grows and the next silence is longer.
        return now < until, until, streak

    @staticmethod
    def _stream_label(n: NotificationOut) -> str:
        base = _KIND_LABEL.get(n.kind, n.kind.title())
        if n.kind in ("streak", "risk") and n.title:
            return n.title.strip("“”\"")
        return base

    def resume(self, kind: str, target: Optional[str] = None) -> int:
        """Un-snooze a stream by forgetting its dismissal history."""
        removed = self.repo.clear_for(kind, target)
        self.repo.commit()
        return removed

    def snoozed_streams(
        self, today: Optional[date] = None, now_hour: Optional[int] = None
    ) -> list[SnoozedStream]:
        return self.build(today, now_hour).snoozed

    # -------------------------------------------------------------- mutations
    def _classify(self, notification_id: str) -> tuple[Optional[str], Optional[str]]:
        """Recover (kind, target) for an id by matching it against live candidates.

        Not parsed from the id: the prefix and the kind genuinely differ in
        places (``burnout:…`` is kind ``wellbeing``), and back-off groups by
        kind, so guessing would split one stream into two.
        """
        for n in self._candidates(date.today(), datetime.now().hour):
            if n.id == notification_id:
                return n.kind, n.target
        return None, None

    def mark_read(self, notification_id: str) -> None:
        kind, target = self._classify(notification_id)
        self.repo.set_status(notification_id, "read", kind, target)
        self.repo.commit()

    def dismiss(self, notification_id: str) -> None:
        kind, target = self._classify(notification_id)
        self.repo.set_status(notification_id, "dismissed", kind, target)
        self.repo.commit()

    def mark_all_read(
        self, today: Optional[date] = None, now_hour: Optional[int] = None
    ) -> None:
        for n in self.build(today, now_hour).notifications:
            if not n.read:
                self.repo.set_status(n.id, "read", n.kind, n.target)
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
                    target=None,
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
                        target=r.habit_id,
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
                    target=t.id,
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
                    target=None,
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
                    target=None,
                    priority="medium",
                    title="A few still open before bed",
                    body=f"{n} habit{'s' if n != 1 else ''} left today — a quick win keeps momentum.",
                    reason="Late in the day with habits still unlogged.",
                    action_label="Open plan",
                    action_route="/plan",
                )
            )

        return out
