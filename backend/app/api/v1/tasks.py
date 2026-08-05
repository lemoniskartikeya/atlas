"""Task endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import task_service
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
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
