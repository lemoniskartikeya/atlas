"""Smart-scheduler endpoints — today's plan, and what you did with it."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import planner_service, scoped_session
from app.schemas.planner import PlanInteractionIn, PlanInteractionOut, PlanResponse
from app.services.interaction_service import InteractionService
from app.services.planner_service import PlannerService

router = APIRouter(prefix="/planner", tags=["planner"])


@router.get("/today", response_model=PlanResponse)
def get_today_plan(svc: PlannerService = Depends(planner_service)):
    return svc.build()


@router.post("/interactions", response_model=PlanInteractionOut)
def record_interaction(
    body: PlanInteractionIn,
    session: Session = Depends(scoped_session),
):
    """Record what the user did with a suggestion.

    Called by the plan view when someone acts on an item through the controls
    it already has — this adds no new thing to click. Repeating it for the same
    item on the same day replaces the previous answer.
    """
    try:
        row = InteractionService(session).record(
            item_kind=body.item_kind,
            item_id=body.item_id,
            action=body.action,
            suggested_block=body.suggested_block,
            suggested_rank=body.suggested_rank,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return PlanInteractionOut(
        recorded=True,
        item_id=row.item_id,
        action=row.action,
        suggested_block=row.suggested_block,
        actual_block=row.actual_block,
        corrected=row.corrected,
    )
