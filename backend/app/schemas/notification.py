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
    #: What can be done from the nudge itself, without navigating anywhere.
    #: Empty for nudges that are only informational, like the morning brief.
    actions: list[str] = []
    read: bool = False
    #: What the nudge is about (habit/task id). Groups a recurring nudge across
    #: days so repeated dismissals of *the same* thing can be recognised.
    target: Optional[str] = None


class SnoozedStream(BaseModel):
    """A nudge Atlas has stopped sending because it kept being dismissed."""

    kind: str
    target: Optional[str] = None
    label: str
    dismissals: int
    until: datetime
    reason: str


class NotificationsResponse(BaseModel):
    generated_at: datetime
    unread: int
    notifications: list[NotificationOut]
    snoozed: list[SnoozedStream] = []


class NotificationAction(BaseModel):
    id: str


class NotificationActRequest(BaseModel):
    id: str
    #: "complete" — log the habit / finish the task.
    #: "defer" — push the task to tomorrow (tasks only).
    action: str


class NotificationActResponse(BaseModel):
    done: bool
    #: What happened, in the words to show the user.
    detail: str


class ResumeRequest(BaseModel):
    kind: str
    target: Optional[str] = None
