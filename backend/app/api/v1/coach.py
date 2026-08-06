"""AI-coach endpoints (local by default; Claude when configured)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import coach_service
from app.schemas.coach import CoachRequest, CoachResponse, CoachStatus
from app.services.coach_service import CoachService

router = APIRouter(prefix="/coach", tags=["coach"])


@router.get("/status", response_model=CoachStatus)
def coach_status(svc: CoachService = Depends(coach_service)):
    return svc.status()


@router.post("/ask", response_model=CoachResponse)
def coach_ask(payload: CoachRequest, svc: CoachService = Depends(coach_service)):
    return svc.ask(payload.messages, use_ai=payload.use_ai)
