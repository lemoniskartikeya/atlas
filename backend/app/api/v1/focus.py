"""Focus-mode endpoints — log deep-work sessions and report stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import focus_service
from app.schemas.focus import FocusSessionCreate, FocusSessionRead, FocusStats
from app.services.focus_service import FocusService

router = APIRouter(prefix="/focus", tags=["focus"])


@router.post("/sessions", response_model=FocusSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: FocusSessionCreate, svc: FocusService = Depends(focus_service)):
    return svc.create(payload)


@router.get("/sessions", response_model=list[FocusSessionRead])
def list_sessions(
    limit: int = Query(20, ge=1, le=200), svc: FocusService = Depends(focus_service)
):
    return list(svc.recent(limit))


@router.get("/stats", response_model=FocusStats)
def focus_stats(svc: FocusService = Depends(focus_service)):
    return svc.stats()
