"""Notification-state repository (per-notification read/dismiss flags)."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select

from app.models.notification import NotificationState
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[NotificationState]):
    model = NotificationState

    def status_map(self) -> dict[str, str]:
        """All stored states as ``{notification_id: status}``."""
        return {s.notification_id: s.status for s in self.list()}

    def by_notification(self, notification_id: str) -> Optional[NotificationState]:
        """Look up one stored state. Identity is (account, notification)."""
        return self.session.scalars(
            self.scoped(
                select(NotificationState).where(
                    NotificationState.notification_id == notification_id
                )
            )
        ).first()

    def set_status(
        self,
        notification_id: str,
        status: str,
        kind: Optional[str] = None,
        target: Optional[str] = None,
    ) -> NotificationState:
        row = self.by_notification(notification_id)
        if row is None:
            row = NotificationState(
                notification_id=notification_id, status=status, kind=kind, target=target
            )
            self.add(row)
        else:
            row.status = status
            # Backfill on rows written before kind/target existed.
            if kind and not row.kind:
                row.kind = kind
            if target and not row.target:
                row.target = target
        return row

    def history(self, kind: str, target: Optional[str]) -> Sequence[NotificationState]:
        """Interactions for one nudge stream, newest first."""
        stmt = select(NotificationState).where(NotificationState.kind == kind)
        stmt = stmt.where(
            NotificationState.target == target
            if target is not None
            else NotificationState.target.is_(None)
        )
        return list(
            self.session.scalars(
                self.scoped(stmt.order_by(NotificationState.created_at.desc()))
            )
        )

    def all_states(self) -> Sequence[NotificationState]:
        return list(
            self.session.scalars(
                self.scoped(
                    select(NotificationState).order_by(
                        NotificationState.created_at.desc()
                    )
                )
            )
        )

    def clear_for(self, kind: str, target: Optional[str]) -> int:
        """Forget a stream's history — used to resume a snoozed nudge."""
        rows = self.history(kind, target)
        for row in rows:
            self.session.delete(row)
        return len(rows)
