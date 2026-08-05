"""Dashboard aggregate endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import dashboard_service
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(svc: DashboardService = Depends(dashboard_service)):
    return svc.build()
