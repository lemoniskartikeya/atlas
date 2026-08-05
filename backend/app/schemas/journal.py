"""Journal API DTOs."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class JournalBase(BaseModel):
    mood: Optional[int] = Field(default=None, ge=1, le=5)
    energy: Optional[int] = Field(default=None, ge=1, le=5)
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    gratitude: Optional[str] = None
    wins: Optional[str] = None
    challenges: Optional[str] = None
    free_writing: Optional[str] = None
    reflection: Optional[str] = None
    lessons: Optional[str] = None


class JournalUpsert(JournalBase):
    """Body for creating/updating the entry for a given day (all fields optional)."""


class JournalRead(JournalBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    date: date
    created_at: datetime
    updated_at: datetime
