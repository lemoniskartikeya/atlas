"""Notification read/dismiss state.

Notifications themselves are *derived* fresh from live signals each request, so
there's nothing to persist except the user's interaction with them. The row key
is the notification's deterministic id (e.g. ``streak:<habit>:<date>``); a new
day mints new ids, so a dismissed nudge naturally reappears when it recurs.

Because ids embed the date, these rows accumulate into an interaction history.
``kind`` and ``target`` are denormalised out of the id so that history can be
grouped without parsing keys — which is what lets the service notice that a
particular nudge is being ignored and back off.

That history is now two-sided. A nudge can be acted on as well as ignored, and
``action`` records which — so "you completed the run from the nudge four times
this month" is a fact in the same table as "you dismissed it three times".
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OwnedMixin, TimestampMixin, UUIDMixin


class NotificationState(UUIDMixin, TimestampMixin, OwnedMixin, Base):
    __tablename__ = "notification_states"
    # The notification id used to be the primary key. It can't be any more:
    # two accounts legitimately produce the same deterministic id on the same
    # day, so identity is now (account, notification).
    __table_args__ = (
        UniqueConstraint(
            "user_id", "notification_id", name="uq_notification_state_user_notification"
        ),
    )

    notification_id: Mapped[str] = mapped_column(String(160), index=True)
    #: "read" | "dismissed" | "snoozed" | "acted". Only "dismissed" counts
    #: against a stream in the back-off ladder; acting on a nudge is the
    #: strongest evidence it was worth sending.
    status: Mapped[str] = mapped_column(String(16))
    #: What was actually done from the notification — "complete", "defer" —
    #: when the status is "acted". Null for a plain read or dismissal.
    action: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    #: Notification family, e.g. "streak" | "risk" | "task" | "brief" | "eod".
    kind: Mapped[Optional[str]] = mapped_column(String(32), default=None, index=True)
    #: What it was about (usually a habit or task id); None for global nudges.
    target: Mapped[Optional[str]] = mapped_column(String(64), default=None, index=True)
