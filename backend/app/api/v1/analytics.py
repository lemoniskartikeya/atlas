"""Analytics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import analytics_service
from app.schemas.analytics import (
    AnalyticsSummary,
    CorrelationsResponse,
    HeatmapResponse,
    InsightsResponse,
    WeeklyResponse,
)
from app.services.analytics_service import AnalyticsService

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
