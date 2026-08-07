"""The recommendation engine behind the dashboard's "Insights for today".

When a completion model is trained, the riskiest habits lead with model-driven,
explainable nudges (probability + the model's own "why"); the transparent
heuristics that shipped in Phase 1 (streak protection, short sleep, morning
window, next task) fill in behind them. With no model it's heuristics only.
Either way the contract holds: every recommendation carries a reason and a
confidence.
"""
from __future__ import annotations

from typing import Optional

from app.domain.enums import TimeOfDay
from app.schemas.dashboard import HabitTodayItem, Recommendation

# A model-backed completion probability at or below this is worth a nudge
# (~35%+ chance of slipping) — aligned with the prediction engine's risk bands.
_RISK_NUDGE = 0.65
# Cap how many model nudges we lead with, so the list stays actionable.
_MAX_NUDGES = 2

_ACTION_BY_TOD = {
    TimeOfDay.MORNING: "Do it this morning while the day's still yours.",
    TimeOfDay.AFTERNOON: "Slot it into your afternoon block.",
    TimeOfDay.EVENING: "Lock it in this evening before the day gets away.",
    TimeOfDay.NIGHT: "Give it a fixed slot tonight so it doesn't slip.",
    TimeOfDay.ANY: "Knock it out now while it's front of mind.",
}


class Recommender:
    """Builds the ranked recommendation list for the dashboard.

    ``predictions`` is ``{habit_id: {probability, explanation, ...}}`` from the
    ML gateway (or ``None`` when no model is available); ``reliability`` is the
    model's held-out ROC-AUC, used as the confidence in model-driven nudges.
    """

    def __init__(
        self,
        *,
        predictions: Optional[dict[str, dict]] = None,
        reliability: Optional[float] = None,
        weights: Optional[dict[str, float]] = None,
    ) -> None:
        self.predictions = predictions
        self.reliability = reliability
        # Per-family multipliers from the outcome-feedback loop; empty until
        # enough recommendations have been shown and resolved.
        self.weights = weights or {}

    @property
    def model_backed(self) -> bool:
        return self.predictions is not None

    def build(
        self,
        *,
        habits_today: list[HabitTodayItem],
        weekly_consistency: float,
        journal,
        suggested,
        now_hour: int,
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []
        flagged: set[str] = set()  # habit ids already covered, to avoid duplicates

        # 1) Model-driven at-risk nudges lead.
        for item in self._riskiest(habits_today):
            pred = self.predictions[item.id]  # type: ignore[index]
            prob = pred["probability"]
            p = round(prob * 100)
            action = _ACTION_BY_TOD.get(item.time_preference, _ACTION_BY_TOD[TimeOfDay.ANY])
            why = pred.get("explanation") or "Based on your recent pattern."
            streak_bit = (
                f" It also protects a {item.current_streak}-day streak."
                if item.current_streak >= 3
                else ""
            )
            recs.append(
                Recommendation(
                    id=f"ml-risk-{item.id}",
                    kind="habit",
                    title=f"“{item.title}” tends to slip on days like today",
                    detail=f"~{p}% likely to complete. {action}{streak_bit}",
                    confidence=round(self.reliability or 0.7, 2),
                    reason=why,
                    habit_id=item.id,
                )
            )
            flagged.add(item.id)

        # 2) Streak protection for anything the model didn't already flag.
        for item in habits_today:
            if item.id in flagged or item.done_today or item.current_streak < 3:
                continue
            conf = min(0.95, 0.5 + item.current_streak * 0.03 + (0.1 if now_hour >= 17 else 0))
            recs.append(
                Recommendation(
                    id=f"streak-{item.id}",
                    kind="habit",
                    title=f"Keep your {item.current_streak}-day streak on “{item.title}”",
                    detail="Still open today — a quick win now protects the streak.",
                    confidence=round(conf, 2),
                    reason=(
                        f"“{item.title}” has a {item.current_streak}-day run and isn't "
                        "logged yet today."
                    ),
                    habit_id=item.id,
                )
            )
            flagged.add(item.id)

        # 3) Short sleep -> protect energy.
        if journal is not None and journal.sleep_hours is not None and journal.sleep_hours < 6.5:
            recs.append(
                Recommendation(
                    id="sleep-low",
                    kind="wellbeing",
                    title="You slept less than usual",
                    detail="Front-load easy work and protect one deep-work block.",
                    confidence=0.55,
                    reason=f"Your latest journal logged {journal.sleep_hours}h of sleep (< 6.5h).",
                )
            )

        # 4) Morning window still open.
        morning_open = [
            i for i in habits_today
            if not i.done_today and i.time_preference == TimeOfDay.MORNING and i.id not in flagged
        ]
        if morning_open and now_hour < 14:
            names = ", ".join(f"“{i.title}”" for i in morning_open[:2])
            recs.append(
                Recommendation(
                    id="morning-window",
                    kind="focus",
                    title="Your morning window is still open",
                    detail=f"Knock out {names} while it's early.",
                    confidence=0.6,
                    reason="These habits are set for the morning and aren't logged yet.",
                )
            )

        # 5) Low weekly consistency -> suggest a lighter, focused day.
        if habits_today and weekly_consistency < 0.5:
            recs.append(
                Recommendation(
                    id="consistency-low",
                    kind="wellbeing",
                    title="Aim for a lighter, focused day",
                    detail="Pick 1–2 keystone habits to win rather than spreading thin.",
                    confidence=0.6,
                    reason=(
                        f"You completed {round(weekly_consistency * 100)}% of due "
                        "habit-days over the last 7 days."
                    ),
                )
            )

        # 6) Next best task.
        if suggested is not None:
            due_txt = f" (due {suggested.due_date.isoformat()})" if suggested.due_date else ""
            recs.append(
                Recommendation(
                    id=f"task-{suggested.id}",
                    kind="task",
                    title=f"Next up: {suggested.title}",
                    detail=f"Your highest-priority open task{due_txt}.",
                    confidence=0.65,
                    reason="Chosen by priority and due date among your open tasks.",
                )
            )

        return self._rank(recs)[:5]

    # ------------------------------------------------------------------ ranking
    def _rank(self, recs: list[Recommendation]) -> list[Recommendation]:
        """Reorder by how well each *style* of nudge has actually worked.

        The generator's own order encodes urgency, so that stays the primary
        signal — a family's track record is applied as a bounded multiplier on
        confidence, enough to promote a consistently effective nudge or demote
        one the user reliably ignores, but never enough to invert the list.
        Families without enough resolved evidence keep their position exactly.
        """
        if not self.weights:
            return recs

        from app.services.feedback_service import family_of

        scored = []
        for position, rec in enumerate(recs):
            weight = self.weights.get(family_of(rec.id))
            if weight is not None:
                rec.outcome_ranked = True
            # Original position is the tiebreaker, so an unweighted list is
            # returned byte-identical to the generator's order.
            scored.append((-(rec.confidence * (weight or 1.0)), position, rec))
        scored.sort(key=lambda s: (s[0], s[1]))
        return [rec for _score, _pos, rec in scored]

    def _riskiest(self, habits_today: list[HabitTodayItem]) -> list[HabitTodayItem]:
        """Not-yet-done due habits the model thinks are most likely to slip."""
        if not self.predictions:
            return []
        candidates = [
            item
            for item in habits_today
            if not item.done_today
            and item.id in self.predictions
            and self.predictions[item.id]["probability"] <= _RISK_NUDGE
        ]
        candidates.sort(key=lambda i: self.predictions[i.id]["probability"])  # type: ignore[index]
        return candidates[:_MAX_NUDGES]
