"""Daily journal endpoints (one entry per date, upsert via PUT)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import journal_service
from app.schemas.journal import JournalRead, JournalUpsert
from app.services.journal_service import JournalService

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("", response_model=list[JournalRead])
def recent_entries(
    limit: int = Query(14, ge=1, le=366),
    svc: JournalService = Depends(journal_service),
):
    return list(svc.recent(limit))


@router.get("/{entry_date}", response_model=JournalRead)
def get_entry(entry_date: date, svc: JournalService = Depends(journal_service)):
    entry = svc.get(entry_date)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No entry for that date")
    return entry


@router.put("/{entry_date}", response_model=JournalRead)
def upsert_entry(
    entry_date: date,
    payload: JournalUpsert,
    svc: JournalService = Depends(journal_service),
):
    return svc.upsert(entry_date, payload)
