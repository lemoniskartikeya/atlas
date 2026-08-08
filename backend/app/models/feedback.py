"""Did the advice actually work?

Every recommendation the dashboard shows is recorded here, and the following
day it is resolved against what the user really did. That closes the loop the
rest of the app was missing: without it Atlas could rank nudges by *predicted*
risk but never learn which of its own nudges are worth showing.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OwnedMixin, TimestampMixin, UUIDMixin


class RecommendationOutcome(UUIDMixin, TimestampMixin, OwnedMixin, Base):
    __tablename__ = "recommendation_outcomes"
    # One row per recommendation per day *per account*: the dashboard is
    # rebuilt on every load, so recording has to be idempotent — but two
    # accounts shown the same nudge on the same day are two separate facts.
    __table_args__ = (
        UniqueConstraint(
            "user_id", "rec_id", "shown_on", name="uq_recommendation_shown_once_per_day"
        ),
    )

    rec_id: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    #: Coarser than rec_id — "ml-risk", "streak", "sleep-low"… — so outcomes
    #: aggregate across habits rather than fragmenting per habit.
    family: Mapped[str] = mapped_column(String(40), index=True)
    habit_id: Mapped[Optional[str]] = mapped_column(String(32), default=None, index=True)
    shown_on: Mapped[date] = mapped_column(Date, index=True)

    #: None until resolved; then True when the nudged habit was completed.
    followed: Mapped[Optional[bool]] = mapped_column(Boolean, default=None)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
