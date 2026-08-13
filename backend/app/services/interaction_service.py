"""Recording — and then using — the user's disagreements with the plan.

Two halves of one loop:

* :meth:`record` stores what the planner suggested next to what the user did.
* :meth:`preferred_block` reads those rows back and reports where someone
  *actually* does a thing, so the planner can stop insisting otherwise.

The second half only speaks when the evidence is one-sided and there is enough
of it. Moving a habit's slot because of a single late finish would make the
plan flap around, which is worse than being consistently a little wrong.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan_interaction import ACTIONS, BLOCKS, PlanInteraction

#: Times a user has to complete something outside its slot before the planner
#: moves it. Two could be a busy fortnight; three is a habit.
MIN_CORRECTIONS = 3
#: And the share of recent completions that has to agree.
MIN_AGREEMENT = 0.6
#: How far back to look. Someone who used to run at dawn and now runs after
#: work should not be argued with using last spring's evidence.
LOOKBACK_DAYS = 60


def block_for_hour(hour: int) -> str:
    """The plan block a moment falls in. The planner's own boundaries."""
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    return "evening"


class InteractionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------- recording
    def record(
        self,
        *,
        item_kind: str,
        item_id: str,
        action: str,
        suggested_block: str,
        suggested_rank: Optional[int] = None,
        plan_date: Optional[date] = None,
        at_hour: Optional[int] = None,
    ) -> PlanInteraction:
        """Store what happened to one suggestion, replacing any earlier answer.

        Idempotent per item per day: changing your mind updates the row rather
        than adding a second opinion, because the question is what you settled
        on. Raises ValueError on anything outside the known vocabulary — a
        typo'd block would quietly become evidence for a slot that isn't real.
        """
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        if suggested_block not in BLOCKS:
            raise ValueError(f"unknown block {suggested_block!r}")

        plan_date = plan_date or date.today()
        hour = at_hour if at_hour is not None else datetime.now().hour
        if not 0 <= hour <= 23:
            raise ValueError(f"hour {hour} is not an hour")

        existing = self.session.scalars(
            select(PlanInteraction).where(
                PlanInteraction.plan_date == plan_date,
                PlanInteraction.item_kind == item_kind,
                PlanInteraction.item_id == item_id,
            )
        ).first()

        row = existing or PlanInteraction(
            plan_date=plan_date, item_kind=item_kind, item_id=item_id
        )
        row.suggested_block = suggested_block
        row.suggested_rank = suggested_rank
        row.action = action
        # Only a completion says anything about *when* someone does a thing.
        # Deferring at 9am tells you nothing about their preferred slot.
        row.actual_block = block_for_hour(hour) if action == "completed" else None
        row.at_hour = hour

        if existing is None:
            self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    # -------------------------------------------------------------- learning
    def preferred_blocks(self, today: Optional[date] = None) -> dict[str, tuple[str, int]]:
        """``{item_id: (block, times_observed)}`` for items with a clear habit.

        Only items the user has repeatedly completed somewhere other than where
        they were put. Everything else is absent, and the planner carries on as
        before — no entry means no opinion, which is different from an opinion
        of "wherever you suggested".
        """
        today = today or date.today()
        since = today - timedelta(days=LOOKBACK_DAYS)

        rows = self.session.scalars(
            select(PlanInteraction).where(
                PlanInteraction.plan_date >= since,
                PlanInteraction.action == "completed",
                PlanInteraction.actual_block.is_not(None),
            )
        ).all()

        seen: dict[str, dict[str, int]] = {}
        for row in rows:
            seen.setdefault(row.item_id, {})
            seen[row.item_id][row.actual_block] = seen[row.item_id].get(row.actual_block, 0) + 1

        preferences: dict[str, tuple[str, int]] = {}
        for item_id, counts in seen.items():
            total = sum(counts.values())
            block, n = max(counts.items(), key=lambda kv: kv[1])
            if n >= MIN_CORRECTIONS and (n / total) >= MIN_AGREEMENT:
                preferences[item_id] = (block, n)
        return preferences
