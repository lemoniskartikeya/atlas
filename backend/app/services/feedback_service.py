"""Closing the loop on recommendations.

Atlas could always rank nudges by *predicted* risk. This is what lets it learn
which of its own nudges actually work: every recommendation shown is recorded,
resolved the next day against what the user really did, and the resulting
hit-rate per family feeds back into how future recommendations are ordered.

Resolution is deliberately conservative. A recommendation counts as "followed"
only when the habit it named was completed on the day it was shown. Anything
still in progress (today's recommendations) stays unresolved rather than being
scored as a failure.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import SUCCESS_STATUSES
from app.models.feedback import RecommendationOutcome
from app.models.habit import HabitLog
from app.schemas.dashboard import Recommendation

# Below this many resolved samples a family's hit-rate is noise, so it is left
# at neutral rather than being allowed to reorder the list.
MIN_SAMPLES_FOR_SIGNAL = 5

# How far back to look when scoring. Old evidence stops reflecting how the user
# works now.
LOOKBACK_DAYS = 120


def family_of(rec_id: str) -> str:
    """Group ids like ``ml-risk-<habit>`` / ``streak-<habit>`` into a family.

    Per-habit ids would fragment the evidence into samples of one; the useful
    question is whether *this style* of nudge works.
    """
    for prefix in ("ml-risk", "streak", "task"):
        if rec_id.startswith(prefix):
            return prefix
    # Non-parameterised ids ("sleep-low", "morning-window") are their own family.
    return rec_id


class FeedbackService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---------------------------------------------------------------- recording
    def record_shown(self, recs: Iterable[Recommendation], today: date) -> None:
        """Idempotent: the dashboard is rebuilt on every load."""
        existing = {
            row.rec_id
            for row in self.session.scalars(
                select(RecommendationOutcome).where(
                    RecommendationOutcome.shown_on == today
                )
            )
        }
        added = False
        for rec in recs:
            if rec.id in existing:
                continue
            self.session.add(
                RecommendationOutcome(
                    rec_id=rec.id,
                    kind=rec.kind,
                    family=family_of(rec.id),
                    habit_id=getattr(rec, "habit_id", None),
                    shown_on=today,
                )
            )
            added = True
        if added:
            self.session.commit()

    # --------------------------------------------------------------- resolution
    def resolve_due(self, today: date) -> int:
        """Score every unresolved recommendation from a day that has finished."""
        pending = list(
            self.session.scalars(
                select(RecommendationOutcome).where(
                    RecommendationOutcome.followed.is_(None),
                    RecommendationOutcome.shown_on < today,
                )
            )
        )
        if not pending:
            return 0

        days = {row.shown_on for row in pending}
        logs = self.session.scalars(
            select(HabitLog).where(HabitLog.date.in_(list(days)))
        )
        success: set[tuple[str, date]] = {
            (log.habit_id, log.date) for log in logs if log.status in SUCCESS_STATUSES
        }

        now = datetime.now(timezone.utc)
        for row in pending:
            if row.habit_id:
                row.followed = (row.habit_id, row.shown_on) in success
            else:
                # Nudges that don't name a habit (sleep, morning window) have no
                # objective completion event, so they're closed as unscored
                # rather than counted against the model.
                row.followed = None
                row.resolved_at = now
                continue
            row.resolved_at = now

        self.session.commit()
        return len(pending)

    # ------------------------------------------------------------------ scoring
    def effectiveness(self, today: Optional[date] = None) -> dict[str, dict]:
        """``{family: {shown, followed, rate}}`` over the recent window."""
        today = today or date.today()
        cutoff = date.fromordinal(max(1, today.toordinal() - LOOKBACK_DAYS))

        rows = self.session.scalars(
            select(RecommendationOutcome).where(
                RecommendationOutcome.shown_on >= cutoff,
                RecommendationOutcome.followed.is_not(None),
            )
        )
        stats: dict[str, dict] = {}
        for row in rows:
            s = stats.setdefault(row.family, {"shown": 0, "followed": 0, "rate": 0.0})
            s["shown"] += 1
            if row.followed:
                s["followed"] += 1
        for s in stats.values():
            s["rate"] = s["followed"] / s["shown"] if s["shown"] else 0.0
        return stats

    def weights(self, today: Optional[date] = None) -> dict[str, float]:
        """Per-family multipliers the recommender uses to reorder its list.

        Centred on 1.0 so an unproven family ranks exactly as it does today;
        only families with enough resolved evidence move, and the range is
        clamped so a bad week can't bury a genuinely urgent nudge.
        """
        out: dict[str, float] = {}
        for family, s in self.effectiveness(today).items():
            if s["shown"] < MIN_SAMPLES_FOR_SIGNAL:
                continue
            # rate 0 -> 0.7, rate 0.5 -> 1.0, rate 1 -> 1.3
            out[family] = round(0.7 + 0.6 * s["rate"], 3)
        return out
