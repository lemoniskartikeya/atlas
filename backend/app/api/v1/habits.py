"""Habit + habit-log endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import habit_service
from app.models.habit import Habit
from app.schemas.habit import (
    HabitCreate,
    HabitLogCreate,
    HabitLogRead,
    HabitRead,
    HabitStats,
    HabitUpdate,
    HabitWithStats,
)
from app.services.habit_service import HabitService

router = APIRouter(prefix="/habits", tags=["habits"])


def _get_or_404(svc: HabitService, habit_id: str) -> Habit:
    habit = svc.get_habit(habit_id)
    if habit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Habit not found")
    return habit


@router.get("", response_model=list[HabitRead])
def list_habits(include_archived: bool = False, svc: HabitService = Depends(habit_service)):
    return list(svc.list_habits(include_archived))


@router.post("", response_model=HabitRead, status_code=status.HTTP_201_CREATED)
def create_habit(payload: HabitCreate, svc: HabitService = Depends(habit_service)):
    return svc.create_habit(payload)


@router.get("/{habit_id}", response_model=HabitWithStats)
def get_habit(habit_id: str, svc: HabitService = Depends(habit_service)):
    habit = _get_or_404(svc, habit_id)
    base = HabitRead.model_validate(habit).model_dump()
    return HabitWithStats(**base, stats=svc.compute_stats(habit))


@router.patch("/{habit_id}", response_model=HabitRead)
def update_habit(habit_id: str, payload: HabitUpdate, svc: HabitService = Depends(habit_service)):
    habit = _get_or_404(svc, habit_id)
    return svc.update_habit(habit, payload)


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_habit(habit_id: str, svc: HabitService = Depends(habit_service)):
    habit = _get_or_404(svc, habit_id)
    svc.delete_habit(habit)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{habit_id}/stats", response_model=HabitStats)
def habit_stats(habit_id: str, svc: HabitService = Depends(habit_service)):
    habit = _get_or_404(svc, habit_id)
    return svc.compute_stats(habit)


@router.get("/{habit_id}/logs", response_model=list[HabitLogRead])
def list_logs(habit_id: str, svc: HabitService = Depends(habit_service)):
    habit = _get_or_404(svc, habit_id)
    return list(svc.logs_for(habit))


@router.post(
    "/{habit_id}/logs",
    response_model=HabitLogRead,
    status_code=status.HTTP_201_CREATED,
)
def log_habit(habit_id: str, payload: HabitLogCreate, svc: HabitService = Depends(habit_service)):
    habit = _get_or_404(svc, habit_id)
    return svc.log_habit(habit, payload)


@router.delete("/{habit_id}/logs/{log_date}", status_code=status.HTTP_204_NO_CONTENT)
def unlog_habit(habit_id: str, log_date: date, svc: HabitService = Depends(habit_service)):
    habit = _get_or_404(svc, habit_id)
    if not svc.unlog_habit(habit, log_date):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No log for that date")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
