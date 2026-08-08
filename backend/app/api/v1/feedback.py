"""What Atlas has learned about its own advice."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import scoped_session
from app.schemas.feedback import EffectivenessResponse, FamilyEffectiveness
from app.services.feedback_service import MIN_SAMPLES_FOR_SIGNAL, FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])

_LABELS = {
    "ml-risk": "Model at-risk nudges",
    "streak": "Streak protection",
    "task": "Next-task suggestions",
    "sleep-low": "Short-sleep warnings",
    "morning-window": "Morning window",
    "consistency-low": "Lighter-day advice",
}


@router.get("/effectiveness", response_model=EffectivenessResponse)
def effectiveness(session: Session = Depends(scoped_session)):
    """Hit-rate per style of recommendation, and whether it's steering ranking."""
    svc = FeedbackService(session)
    today = date.today()
    stats = svc.effectiveness(today)
    weights = svc.weights(today)

    families = [
        FamilyEffectiveness(
            family=family,
            label=_LABELS.get(family, family.replace("-", " ").title()),
            shown=s["shown"],
            followed=s["followed"],
            rate=round(s["rate"], 4),
            weight=weights.get(family),
            influencing=family in weights,
        )
        for family, s in sorted(stats.items(), key=lambda kv: -kv[1]["shown"])
    ]

    resolved = sum(f.shown for f in families)
    return EffectivenessResponse(
        families=families,
        total_resolved=resolved,
        min_samples=MIN_SAMPLES_FOR_SIGNAL,
    )
