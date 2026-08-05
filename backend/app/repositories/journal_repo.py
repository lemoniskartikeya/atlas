"""Journal repository."""
from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from sqlalchemy import select

from app.models.journal import JournalEntry
from app.repositories.base import BaseRepository


class JournalRepository(BaseRepository[JournalEntry]):
    model = JournalEntry

    def by_date(self, d: date) -> Optional[JournalEntry]:
        return self.session.scalars(
            select(JournalEntry).where(JournalEntry.date == d)
        ).first()

    def recent(self, limit: int = 14) -> Sequence[JournalEntry]:
        return list(
            self.session.scalars(
                select(JournalEntry).order_by(JournalEntry.date.desc()).limit(limit)
            )
        )

    def latest(self) -> Optional[JournalEntry]:
        return self.session.scalars(
            select(JournalEntry).order_by(JournalEntry.date.desc())
        ).first()
