"""Notification-state repository (per-notification read/dismiss flags)."""
from __future__ import annotations

from app.models.notification import NotificationState
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[NotificationState]):
    model = NotificationState

    def status_map(self) -> dict[str, str]:
        """All stored states as ``{notification_id: status}``."""
        return {s.notification_id: s.status for s in self.list()}

    def set_status(self, notification_id: str, status: str) -> NotificationState:
        row = self.get(notification_id)
        if row is None:
            row = NotificationState(notification_id=notification_id, status=status)
            self.add(row)
        else:
            row.status = status
        return row
