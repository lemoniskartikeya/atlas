"""Habit and HabitLog repositories."""
from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from sqlalchemy import select

from app.models.habit import Habit, HabitLog
from app.repositories.base import BaseRepository


class HabitRepository(BaseRepository[Habit]):
    model = Habit

    def list_all(self, include_archived: bool = False) -> Sequence[Habit]:
        stmt = select(Habit).order_by(Habit.created_at)
        if not include_archived:
            stmt = stmt.where(Habit.archived.is_(False))
        return list(self.session.scalars(stmt))


class HabitLogRepository(BaseRepository[HabitLog]):
    model = HabitLog

    def for_habit(self, habit_id: str) -> Sequence[HabitLog]:
        return list(
            self.session.scalars(
                select(HabitLog).where(HabitLog.habit_id == habit_id).order_by(HabitLog.date)
            )
        )

    def for_habit_and_date(self, habit_id: str, d: date) -> Optional[HabitLog]:
        return self.session.scalars(
            select(HabitLog).where(HabitLog.habit_id == habit_id, HabitLog.date == d)
        ).first()

    def for_date(self, d: date) -> Sequence[HabitLog]:
        return list(self.session.scalars(select(HabitLog).where(HabitLog.date == d)))

    def in_range(self, start: date, end: date) -> Sequence[HabitLog]:
        return list(
            self.session.scalars(
                select(HabitLog)
                .where(HabitLog.date >= start, HabitLog.date <= end)
                .order_by(HabitLog.date)
            )
        )
