"""Notification read/dismiss state.

Notifications themselves are *derived* fresh from live signals each request, so
there's nothing to persist except the user's interaction with them. The row key
is the notification's deterministic id (e.g. ``streak:<habit>:<date>``); a new
day mints new ids, so a dismissed nudge naturally reappears when it recurs.

Because ids embed the date, these rows accumulate into an interaction history.
``kind`` and ``target`` are denormalised out of the id so that history can be
grouped without parsing keys — which is what lets the service notice that a
particular nudge is being ignored and back off.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NotificationState(TimestampMixin, Base):
    __tablename__ = "notification_states"

    notification_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))  # "read" | "dismissed"
    #: Notification family, e.g. "streak" | "risk" | "task" | "brief" | "eod".
    kind: Mapped[Optional[str]] = mapped_column(String(32), default=None, index=True)
    #: What it was about (usually a habit or task id); None for global nudges.
    target: Mapped[Optional[str]] = mapped_column(String(64), default=None, index=True)
