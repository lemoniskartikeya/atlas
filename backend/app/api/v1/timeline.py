"""Activity-timeline endpoint."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import timeline_service
from app.schemas.timeline import TimelineResponse
from app.services.timeline_service import TimelineService

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("", response_model=TimelineResponse)
def get_timeline(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    kinds: Optional[str] = Query(None, description="Comma-separated kinds to include"),
    svc: TimelineService = Depends(timeline_service),
):
    parsed = [k.strip() for k in kinds.split(",") if k.strip()] if kinds else None
    return svc.build(limit=limit, offset=offset, kinds=parsed)
