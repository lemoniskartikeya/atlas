"""AI-coach DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProviderOption(BaseModel):
    """One selectable backend, with everything Settings needs to describe it."""

    id: str
    label: str
    default_model: str
    key_url: Optional[str] = None
    cost_note: str
    local: bool = False
    needs_key: bool = True
    suggested_models: list[str] = Field(default_factory=list)
    #: Local providers only: models actually pulled on this machine.
    installed_models: Optional[list[str]] = None
    available: Optional[bool] = None


class CoachStatus(BaseModel):
    ai_available: bool  # the selected provider is usable right now
    provider: Optional[str] = None
    provider_label: Optional[str] = None
    model: Optional[str] = None
    local_provider: bool = False
    needs_key: bool = True
    sdk_installed: bool = False  # the `anthropic` package (that provider only)
    has_key: bool = False
    key_hint: Optional[str] = None  # masked, e.g. "sk-ant-api0…wxyz"
    providers: list[ProviderOption] = Field(default_factory=list)


class ApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=400)
    #: Which provider this key belongs to. Omitted means the selected one.
    provider: Optional[str] = None


class ProviderRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    #: Blank/omitted keeps the provider's own default model.
    model: Optional[str] = Field(default=None, max_length=120)


class KeyTestResult(BaseModel):
    ok: bool
    detail: str


class CoachMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class CoachRequest(BaseModel):
    messages: list[CoachMessage] = Field(default_factory=list)
    use_ai: bool = True  # opt into the Claude path (only used when AI is available)


class CoachResponse(BaseModel):
    reply: str
    mode: str  # "ai" | "local"
    model: Optional[str] = None
    grounded_on: Optional[str] = None  # the date the coach's context reflects
