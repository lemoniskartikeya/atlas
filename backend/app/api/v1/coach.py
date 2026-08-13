"""AI-coach endpoints (local by default; Claude when a key is configured)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import coach_service
from app.core.config import get_settings
from app.core.secrets_store import set_coach_model, set_coach_provider, set_provider_key
from app.schemas.coach import (
    ApiKeyRequest,
    CoachRequest,
    CoachResponse,
    CoachStatus,
    KeyTestResult,
    ProviderRequest,
)
from app.services.coach_service import CoachService
from app.services.llm import PROVIDERS

router = APIRouter(prefix="/coach", tags=["coach"])


@router.get("/status", response_model=CoachStatus)
def coach_status(svc: CoachService = Depends(coach_service)):
    return svc.status()


@router.post("/ask", response_model=CoachResponse)
def coach_ask(payload: CoachRequest, svc: CoachService = Depends(coach_service)):
    return svc.ask(payload.messages, use_ai=payload.use_ai)


@router.put("/provider", response_model=CoachStatus)
def choose_provider(payload: ProviderRequest, svc: CoachService = Depends(coach_service)):
    """Pick which backend answers, and optionally pin a model."""
    provider_id = payload.provider.strip().lower()
    if provider_id not in PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider '{payload.provider}'.",
        )
    set_coach_provider(provider_id)
    set_coach_model(payload.model)
    return svc.status()


@router.put("/key", response_model=CoachStatus)
def set_key(payload: ApiKeyRequest, svc: CoachService = Depends(coach_service)):
    """Persist one provider's key to backend/.env (gitignored, local only).

    Keys are stored per provider, so trying a second free tier does not discard
    the first. The key is never echoed back — only a masked hint via /status.
    """
    provider_id = (payload.provider or get_settings().coach_provider).strip().lower()
    if provider_id not in PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider '{provider_id}'.",
        )
    set_provider_key(provider_id, payload.api_key)
    return svc.status()


@router.delete("/key", response_model=CoachStatus)
def clear_key(
    provider: str | None = None, svc: CoachService = Depends(coach_service)
):
    set_provider_key((provider or get_settings().coach_provider), None)
    return svc.status()


@router.post("/key/test", response_model=KeyTestResult, status_code=status.HTTP_200_OK)
def test_key(svc: CoachService = Depends(coach_service)):
    """Live round-trip against the API so Settings can show a real verdict."""
    return svc.test_key()
