"""Task endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import task_service
from app.models.task import Task
from app.schemas.task import (
    CompletedTasks,
    ParsedTaskOut,
    ParseRequest,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from app.services import nl_task
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_or_404(svc: TaskService, task_id: str) -> Task:
    task = svc.get(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(
    scope: str = Query("all", pattern="^(all|today|upcoming|open)$"),
    svc: TaskService = Depends(task_service),
):
    return list(svc.list_tasks(scope))


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, svc: TaskService = Depends(task_service)):
    return svc.create(payload)


@router.post("/parse", response_model=ParsedTaskOut)
def parse_task_phrase(body: ParseRequest):
    """Read a typed phrase into task fields, without creating anything.

    A preview: the caller shows what was understood and lets the user correct
    it before saving. Deterministic and offline — no model, no key, no cost.
    """
    parsed = nl_task.parse(body.text)
    return ParsedTaskOut(
        title=parsed.title,
        due_date=parsed.due_date,
        deadline=parsed.deadline,
        priority=parsed.priority,
        estimated_effort_min=parsed.estimated_effort_min,
        tags=parsed.tags,
        understood=parsed.understood,
    )


@router.get("/completed", response_model=CompletedTasks)
def completed_tasks(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=500),
    svc: TaskService = Depends(task_service),
):
    """Completion history. Declared before /{task_id} so the literal path wins."""
    tasks, stats = svc.completed_history(days=days, limit=limit)
    return {"stats": stats, "tasks": tasks}


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: str, svc: TaskService = Depends(task_service)):
    return _get_or_404(svc, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: str, payload: TaskUpdate, svc: TaskService = Depends(task_service)):
    return svc.update(_get_or_404(svc, task_id), payload)


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: str, svc: TaskService = Depends(task_service)):
    return svc.complete(_get_or_404(svc, task_id))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, svc: TaskService = Depends(task_service)):
    svc.delete(_get_or_404(svc, task_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
