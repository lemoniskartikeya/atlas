"""Daily journal entry ORM model. One entry per calendar day (unique date)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OwnedMixin, TimestampMixin, UUIDMixin


class JournalEntry(UUIDMixin, TimestampMixin, OwnedMixin, Base):
    __tablename__ = "journal_entries"
    # One entry per day *per account* — the old bare-unique on ``date`` would
    # have let one account's entry block everyone else's.
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_journal_entry_user_date"),
    )

    date: Mapped[date] = mapped_column(Date, index=True)
    mood: Mapped[Optional[int]] = mapped_column(Integer, default=None)  # 1-5
    energy: Mapped[Optional[int]] = mapped_column(Integer, default=None)  # 1-5
    sleep_hours: Mapped[Optional[float]] = mapped_column(Float, default=None)
    gratitude: Mapped[Optional[str]] = mapped_column(Text, default=None)
    wins: Mapped[Optional[str]] = mapped_column(Text, default=None)
    challenges: Mapped[Optional[str]] = mapped_column(Text, default=None)
    free_writing: Mapped[Optional[str]] = mapped_column(Text, default=None)
    reflection: Mapped[Optional[str]] = mapped_column(Text, default=None)
    lessons: Mapped[Optional[str]] = mapped_column(Text, default=None)
