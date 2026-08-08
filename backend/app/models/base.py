"""Declarative base and shared column mixins."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


def new_uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class all ORM models inherit from."""


class UUIDMixin:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class OwnedMixin:
    """Marks a table as belonging to one Atlas account.

    Every row of vault data (habits, logs, tasks, journals, notes, focus
    sessions, notification state, feedback, job history) carries the id of the
    account it belongs to. ``app.core.scoping`` uses *this class* as the handle
    for a session-wide filter, so a model becomes tenant-scoped simply by
    inheriting it — there is no per-model registration to forget.

    Nullable on purpose: a vault created before accounts existed has no owner
    yet. Such rows are invisible to every signed-in account until the first
    account claims them (see ``AuthService.register``), which is safer than
    inventing a user during a migration.
    """

    @declared_attr
    def user_id(cls) -> Mapped[Optional[str]]:
        # declared_attr because a ForeignKey object cannot be shared between
        # tables — each mapped class needs its own.
        return mapped_column(
            ForeignKey("users.id", ondelete="CASCADE"),
            default=None,
            nullable=True,
            index=True,
        )
