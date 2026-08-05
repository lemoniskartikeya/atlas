"""Analytics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import analytics_service
from app.schemas.analytics import HeatmapResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/heatmap", response_model=HeatmapResponse)
def heatmap(
    days: int = Query(365, ge=1, le=730),
    svc: AnalyticsService = Depends(analytics_service),
):
    return svc.heatmap(days)
