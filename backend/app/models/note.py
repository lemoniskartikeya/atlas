"""Note ORM model (markdown knowledge base + daily notes). Expanded in Phase 2."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Note(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notes"

    title: Mapped[str] = mapped_column(String(300), default="Untitled")
    content: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=None)
    is_daily: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[Optional[date]] = mapped_column(Date, default=None, index=True)
