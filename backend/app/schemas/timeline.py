"""Activity-timeline DTOs."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class TimelineEvent(BaseModel):
    id: str
    kind: str  # "habit" | "streak" | "task" | "journal" | "habit_created"
    timestamp: datetime
    date: date
    title: str
    detail: Optional[str] = None
    status: Optional[str] = None  # habit-log status, when kind == "habit"
    color: Optional[str] = None
    route: Optional[str] = None  # in-app deep link


class TimelineResponse(BaseModel):
    events: list[TimelineEvent]
    offset: int
    limit: int
    total: int
    has_more: bool
