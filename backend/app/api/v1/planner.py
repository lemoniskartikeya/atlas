"""Smart-scheduler endpoint — today's ordered, explainable plan."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import planner_service
from app.schemas.planner import PlanResponse
from app.services.planner_service import PlannerService

router = APIRouter(prefix="/planner", tags=["planner"])


@router.get("/today", response_model=PlanResponse)
def get_today_plan(svc: PlannerService = Depends(planner_service)):
    return svc.build()
