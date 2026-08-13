"""Pluggable chat-completion backends for the AI coach.

The coach used to speak only to Anthropic. That made the one genuinely optional
feature in Atlas depend on one paid account, which is a poor fit for an app that
is otherwise free and local-first. This package puts a small interface in front
of several providers — including two with usable free tiers and a fully local
one — so the user can pick whichever they can actually get a key for.

Deliberately thin: one non-streaming "given these messages, return text" call.
Anything richer belongs in the provider's own SDK, and the coach doesn't need it.
"""
from __future__ import annotations

from app.services.llm.base import ChatMessage, LLMError, Provider
from app.services.llm.registry import (
    PROVIDERS,
    default_provider_id,
    get_provider,
    provider_catalog,
)

__all__ = [
    "ChatMessage",
    "LLMError",
    "Provider",
    "PROVIDERS",
    "default_provider_id",
    "get_provider",
    "provider_catalog",
]
