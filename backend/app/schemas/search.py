"""Search DTOs."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel

# A field named ``date`` with a default shadows the ``date`` type during pydantic's
# deferred-annotation resolution; alias the type so the field keeps it.
_Date = date


class SearchResult(BaseModel):
    type: str  # "habit" | "task" | "journal" | "note" | "log"
    id: str
    title: str
    snippet: Optional[str] = None
    date: Optional[_Date] = None
    status: Optional[str] = None
    route: Optional[str] = None
    score: float


class SearchResponse(BaseModel):
    query: str
    interpretation: str  # how the query was understood (transparent)
    total: int
    results: list[SearchResult]
