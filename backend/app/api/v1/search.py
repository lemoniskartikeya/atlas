"""Natural-language search endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import search_service
from app.schemas.search import SearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query("", description="Natural-language query"),
    limit: int = Query(30, ge=1, le=100),
    svc: SearchService = Depends(search_service),
):
    if not q.strip():
        return SearchResponse(query=q, interpretation="everything", total=0, results=[])
    return svc.search(q, limit=limit)
