"""AI-coach DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CoachStatus(BaseModel):
    ai_available: bool  # a key is configured AND the anthropic package is installed
    provider: Optional[str] = None  # "anthropic" when AI is available
    model: Optional[str] = None


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
