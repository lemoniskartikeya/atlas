"""What the user did with what the planner suggested.

The planner proposes an order and a time of day for everything due. Until now
nothing recorded whether the user agreed. That gap is the reason a plan could
suggest a morning run for six months to someone who has run in the evening
every single day — the suggestion was never wrong in a way the app could see.

One row per plan item per day, holding the suggestion *and* what actually
happened, so a disagreement between them is a fact rather than an inference.
It is deliberately the ultimate outcome for the day and not an event log: a
row is updated in place if the user changes their mind, because the useful
question is what they settled on, not how many times they clicked.

Named for plans rather than tasks because the plan contains both habits and
tasks, and a table called `task_interactions` holding habits would be a lie
that outlives whoever wrote it.
"""
from __future__ import annotations

from datetime import date as date_t
from typing import Optional

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OwnedMixin, TimestampMixin, UUIDMixin

#: What the user did with a suggestion.
ACTIONS = ("completed", "deferred", "dismissed")
BLOCKS = ("morning", "afternoon", "evening")


class PlanInteraction(UUIDMixin, TimestampMixin, OwnedMixin, Base):
    __tablename__ = "plan_interactions"
    # One settled outcome per item per day per account.
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "plan_date",
            "item_kind",
            "item_id",
            name="uq_plan_interaction_per_item_per_day",
        ),
    )

    plan_date: Mapped[date_t] = mapped_column(Date, index=True)
    item_kind: Mapped[str] = mapped_column(String(16))  # "habit" | "task"
    #: Not a foreign key: it points at either a habit or a task depending on
    #: item_kind, and the record of what was suggested stays interesting after
    #: the thing itself is deleted.
    item_id: Mapped[str] = mapped_column(String(32), index=True)

    #: What the planner proposed, as the user actually saw it.
    suggested_block: Mapped[str] = mapped_column(String(16))
    #: Its position in that block, 0-based. Lets us see whether the ordering is
    #: being followed or worked around.
    suggested_rank: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    action: Mapped[str] = mapped_column(String(16), index=True)
    #: The block the user was actually in when they acted. Equal to
    #: suggested_block when the suggestion was followed; the interesting rows
    #: are the ones where it isn't.
    actual_block: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    #: Local hour, 0–23. Kept alongside the block because "just after 5" and
    #: "close to midnight" are both "evening" and are not the same habit.
    at_hour: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    @property
    def corrected(self) -> bool:
        """Whether the user did it somewhere other than where it was put."""
        return (
            self.action == "completed"
            and self.actual_block is not None
            and self.actual_block != self.suggested_block
        )
