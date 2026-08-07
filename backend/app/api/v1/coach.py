"""AI-coach endpoints (local by default; Claude when a key is configured)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import coach_service
from app.core.secrets_store import set_anthropic_key
from app.schemas.coach import (
    ApiKeyRequest,
    CoachRequest,
    CoachResponse,
    CoachStatus,
    KeyTestResult,
)
from app.services.coach_service import CoachService

router = APIRouter(prefix="/coach", tags=["coach"])


@router.get("/status", response_model=CoachStatus)
def coach_status(svc: CoachService = Depends(coach_service)):
    return svc.status()


@router.post("/ask", response_model=CoachResponse)
def coach_ask(payload: CoachRequest, svc: CoachService = Depends(coach_service)):
    return svc.ask(payload.messages, use_ai=payload.use_ai)


@router.put("/key", response_model=CoachStatus)
def set_key(payload: ApiKeyRequest, svc: CoachService = Depends(coach_service)):
    """Persist the Anthropic key to backend/.env (gitignored, local only).

    The key is never echoed back — only a masked hint via /status.
    """
    set_anthropic_key(payload.api_key)
    return svc.status()


@router.delete("/key", response_model=CoachStatus)
def clear_key(svc: CoachService = Depends(coach_service)):
    set_anthropic_key(None)
    return svc.status()


@router.post("/key/test", response_model=KeyTestResult, status_code=status.HTTP_200_OK)
def test_key(svc: CoachService = Depends(coach_service)):
    """Live round-trip against the API so Settings can show a real verdict."""
    return svc.test_key()
