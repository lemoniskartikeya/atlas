"""Journal domain service (one entry per day, upsert semantics)."""
from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.journal import JournalEntry
from app.repositories.journal_repo import JournalRepository
from app.schemas.journal import JournalUpsert


class JournalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = JournalRepository(session)

    def get(self, d: date) -> Optional[JournalEntry]:
        return self.repo.by_date(d)

    def recent(self, limit: int = 14) -> Sequence[JournalEntry]:
        return self.repo.recent(limit)

    def latest(self) -> Optional[JournalEntry]:
        return self.repo.latest()

    def upsert(self, d: date, data: JournalUpsert) -> JournalEntry:
        entry = self.repo.by_date(d)
        payload = data.model_dump(exclude_unset=True)
        if entry:
            for key, value in payload.items():
                setattr(entry, key, value)
        else:
            entry = JournalEntry(date=d, **payload)
            self.repo.add(entry)
        self.repo.commit()
        return entry
