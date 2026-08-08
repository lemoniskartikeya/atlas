"""Habit and HabitLog ORM models."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import Difficulty, Frequency, HabitLogStatus, Priority, TimeOfDay
from app.models.base import Base, OwnedMixin, TimestampMixin, UUIDMixin, utcnow


class Habit(UUIDMixin, TimestampMixin, OwnedMixin, Base):
    __tablename__ = "habits"

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    category: Mapped[Optional[str]] = mapped_column(String(80), default=None, index=True)

    frequency: Mapped[Frequency] = mapped_column(
        SAEnum(Frequency, native_enum=False, length=20), default=Frequency.DAILY
    )
    # For CUSTOM frequency: weekday indexes (0=Mon .. 6=Sun) the habit is due on.
    custom_days: Mapped[Optional[list]] = mapped_column(JSON, default=None)
    # For WEEKLY/MONTHLY: how many completions constitute a "successful" period.
    target_per_period: Mapped[int] = mapped_column(Integer, default=1)

    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority, native_enum=False, length=20), default=Priority.MEDIUM
    )
    estimated_duration_min: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    difficulty: Mapped[Difficulty] = mapped_column(
        SAEnum(Difficulty, native_enum=False, length=20), default=Difficulty.MEDIUM
    )
    motivation_level: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    required_energy: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    location: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    time_preference: Mapped[TimeOfDay] = mapped_column(
        SAEnum(TimeOfDay, native_enum=False, length=20), default=TimeOfDay.ANY
    )
    color: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    logs: Mapped[list["HabitLog"]] = relationship(
        back_populates="habit",
        cascade="all, delete-orphan",
        order_by="HabitLog.date",
        lazy="selectin",
    )


class HabitLog(UUIDMixin, TimestampMixin, OwnedMixin, Base):
    __tablename__ = "habit_logs"
    __table_args__ = (Index("ix_habit_logs_habit_date", "habit_id", "date"),)

    habit_id: Mapped[str] = mapped_column(
        ForeignKey("habits.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[HabitLogStatus] = mapped_column(
        SAEnum(HabitLogStatus, native_enum=False, length=20),
        default=HabitLogStatus.COMPLETED,
    )
    partial_amount: Mapped[Optional[float]] = mapped_column(Float, default=None)
    reason: Mapped[Optional[str]] = mapped_column(Text, default=None)  # skip reason
    mood_after: Mapped[Optional[int]] = mapped_column(Integer, default=None)  # 1-5
    energy_before: Mapped[Optional[int]] = mapped_column(Integer, default=None)  # 1-5
    energy_after: Mapped[Optional[int]] = mapped_column(Integer, default=None)  # 1-5
    duration_min: Mapped[Optional[int]] = mapped_column(Integer, default=None)  # actual
    note: Mapped[Optional[str]] = mapped_column(Text, default=None)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    habit: Mapped["Habit"] = relationship(back_populates="logs")
