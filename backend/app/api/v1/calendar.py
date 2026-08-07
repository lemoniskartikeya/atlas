"""Calendar endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import calendar_service
from app.schemas.calendar import CalendarMonth
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("", response_model=CalendarMonth)
def get_month(
    year: int = Query(default=0, ge=0, le=9999),
    month: int = Query(default=0, ge=0, le=12),
    svc: CalendarService = Depends(calendar_service),
):
    """One month of habits, tasks, journal, and focus. Defaults to this month."""
    today = date.today()
    return svc.month(year or today.year, month or today.month, today=today)
