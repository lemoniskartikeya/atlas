"""Focus-session repository."""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from app.models.focus import FocusSession
from app.repositories.base import BaseRepository


class FocusRepository(BaseRepository[FocusSession]):
    model = FocusSession

    def recent(self, limit: int = 20) -> Sequence[FocusSession]:
        return list(
            self.session.scalars(
                self.scoped(
                    select(FocusSession)
                    .order_by(FocusSession.started_at.desc())
                    .limit(limit)
                )
            )
        )
