"""Notification read/dismiss state.

Notifications themselves are *derived* fresh from live signals each request, so
there's nothing to persist except the user's interaction with them. The row key
is the notification's deterministic id (e.g. ``streak:<habit>:<date>``); a new
day mints new ids, so a dismissed nudge naturally reappears when it recurs.
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NotificationState(TimestampMixin, Base):
    __tablename__ = "notification_states"

    notification_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))  # "read" | "dismissed"
