"""Weekly-review endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import review_service
from app.schemas.review import WeeklyReview
from app.services.review_service import WeeklyReviewService

router = APIRouter(prefix="/review", tags=["review"])


@router.get("", response_model=WeeklyReview)
def weekly_review(
    offset: int = Query(0, ge=0, le=520, description="Weeks back from the current week"),
    svc: WeeklyReviewService = Depends(review_service),
):
    return svc.build(offset=offset)
