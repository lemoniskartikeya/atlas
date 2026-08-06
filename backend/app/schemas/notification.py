"""Notification DTOs."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    kind: str  # "brief" | "risk" | "streak" | "task" | "wellbeing" | "eod"
    priority: str  # "high" | "medium" | "low"
    title: str
    body: str
    reason: str
    action_label: Optional[str] = None
    action_route: Optional[str] = None  # in-app deep link, e.g. "/plan"
    read: bool = False


class NotificationsResponse(BaseModel):
    generated_at: datetime
    unread: int
    notifications: list[NotificationOut]


class NotificationAction(BaseModel):
    id: str
