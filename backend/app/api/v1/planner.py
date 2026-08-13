"""Smart-scheduler endpoints — today's plan, and what you did with it."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.domain.enums import TaskStatus

from app.api.deps import planner_service, scoped_session
from app.schemas.planner import (
    DeferRequest,
    DeferResponse,
    PlanInteractionIn,
    PlanInteractionOut,
    PlanResponse,
)
from app.services.interaction_service import InteractionService
from app.services.task_service import TaskService
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


@router.post("/defer", response_model=DeferResponse)
def defer_task(
    body: DeferRequest,
    session: Session = Depends(scoped_session),
):
    """Move a task off today's plan to a later day.

    Changes only when you intend to do it. The due date is left alone, so
    something already late stays late and keeps saying so.
    """
    if not 1 <= body.days <= 30:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Defer by between 1 and 30 days.",
        )

    tasks = TaskService(session)
    task = tasks.get(body.task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such task.")
    if task.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That task is already closed."
        )

    today = date.today()
    target = today + timedelta(days=body.days)
    tasks.defer(task, target)

    # A deferral is a disagreement with the plan, so it belongs in the record —
    # best effort, because failing to take a note must not undo the move.
    if body.suggested_block:
        try:
            InteractionService(session).record(
                item_kind="task",
                item_id=task.id,
                action="deferred",
                suggested_block=body.suggested_block,
            )
        except ValueError:
            pass

    overdue = bool(task.due_date and task.due_date < target)
    when = "tomorrow" if body.days == 1 else f"in {body.days} days"
    detail = f"Moved to {when}."
    if overdue:
        detail += f" Still due {task.due_date.isoformat()}, so it stays overdue."

    return DeferResponse(
        task_id=task.id,
        title=task.title,
        scheduled_for=target,
        still_overdue=overdue,
        detail=detail,
    )
