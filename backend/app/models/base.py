"""Declarative base and shared column mixins."""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


def new_uuid() -> str:
    return uuid.uuid4().hex


def _make_utcnow():
    """Pick the most precise UTC clock this platform offers.

    On Windows, `datetime.now()` reads `GetSystemTimeAsFileTime`, whose
    resolution is **15.625 ms**. Two rows written inside one tick get byte-identical
    timestamps, so any "most recent first" ordering falls back to whatever order
    the database happens to return — the focus-session list showed a just-logged
    session *below* the one before it. The precise API is sub-microsecond, which
    is enough to keep consecutive writes distinguishable.
    """
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        try:
            get_time = ctypes.windll.kernel32.GetSystemTimePreciseAsFileTime
        except (AttributeError, OSError):  # pragma: no cover - pre-Windows 8
            return lambda: datetime.now(timezone.utc)
        get_time.restype = None
        get_time.argtypes = [ctypes.POINTER(wintypes.FILETIME)]

        # FILETIME counts 100-nanosecond intervals since 1601-01-01 UTC.
        epoch_offset = 116_444_736_000_000_000  # 1601-01-01 -> 1970-01-01

        def _precise_now() -> datetime:
            filetime = wintypes.FILETIME()
            get_time(ctypes.byref(filetime))
            ticks = (filetime.dwHighDateTime << 32) | filetime.dwLowDateTime
            return datetime.fromtimestamp((ticks - epoch_offset) / 1e7, tz=timezone.utc)

        return _precise_now

    return lambda: datetime.now(timezone.utc)


_utcnow = _make_utcnow()


def utcnow() -> datetime:
    """Current UTC time, at the finest resolution the platform can give us."""
    return _utcnow()


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
