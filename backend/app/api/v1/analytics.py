"""Analytics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import analytics_service, scoped_session
from app.schemas.analytics import (
    AnalyticsSummary,
    BehaviourProfileOut,
    CorrelationsResponse,
    HeatmapResponse,
    InsightsResponse,
    WeeklyResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.behaviour_profile import BehaviourProfileService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/heatmap", response_model=HeatmapResponse)
def heatmap(
    days: int = Query(365, ge=1, le=730),
    svc: AnalyticsService = Depends(analytics_service),
):
    return svc.heatmap(days)


@router.get("/summary", response_model=AnalyticsSummary)
def summary(svc: AnalyticsService = Depends(analytics_service)):
    return svc.summary()


@router.get("/weekly", response_model=WeeklyResponse)
def weekly(
    weeks: int = Query(12, ge=1, le=53),
    svc: AnalyticsService = Depends(analytics_service),
):
    return svc.weekly(weeks)


@router.get("/insights", response_model=InsightsResponse)
def insights(
    days: int = Query(365, ge=28, le=730),
    svc: AnalyticsService = Depends(analytics_service),
):
    """Plain-language readings of the same data the other endpoints chart.

    Returns an empty list when nothing meets its evidence threshold — that is
    the expected answer for a new account, not an error.
    """
    return svc.insights(days)


@router.get("/correlations", response_model=CorrelationsResponse)
def correlations(
    days: int = Query(90, ge=7, le=365),
    svc: AnalyticsService = Depends(analytics_service),
):
    return svc.correlations(days)


@router.get("/profile", response_model=BehaviourProfileOut)
def behaviour_profile(session: Session = Depends(scoped_session)):
    """How this person works, as opposed to how today is going.

    Read-only and derived — nothing is stored. Traits appear only when the
    record supports them, so a new account gets an empty list rather than a
    personality it hasn't earned.
    """
    svc = BehaviourProfileService(session)
    profile = svc.build()
    return BehaviourProfileOut(
        traits=[
            {"key": t.key, "summary": t.summary, "evidence": t.evidence}
            for t in profile.traits
        ],
        peak_hours=list(profile.peak_hours) if profile.peak_hours else None,
        best_weekday=profile.best_weekday,
        worst_weekday=profile.worst_weekday,
        typical_streak=profile.typical_streak,
        window_days=svc.WINDOW_DAYS,
    )
