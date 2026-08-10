"""Focus-session repository."""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from app.models.focus import FocusSession
from app.repositories.base import BaseRepository


class FocusRepository(BaseRepository[FocusSession]):
    model = FocusSession

    def recent(self, limit: int = 20) -> Sequence[FocusSession]:
        # created_at/id break ties: without them two sessions sharing a
        # started_at come back in whatever order the database picks, which
        # showed the newer one *below* the older in the recent-sessions list.
        return list(
            self.session.scalars(
                self.scoped(
                    select(FocusSession)
                    .order_by(
                        FocusSession.started_at.desc(),
                        FocusSession.created_at.desc(),
                        FocusSession.id.desc(),
                    )
                    .limit(limit)
                )
            )
        )
