"""The set of chat backends Atlas offers, and how to look one up."""
from __future__ import annotations

from typing import Optional

from app.services.llm.base import Provider, ProviderInfo
from app.services.llm.providers import (
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)

#: Groq and OpenRouter both speak the OpenAI chat shape, so they share one class
#: and differ only in their metadata and base URL.
_GROQ = OpenAICompatibleProvider(
    ProviderInfo(
        id="groq",
        label="Groq",
        default_model="llama-3.3-70b-versatile",
        key_url="https://console.groq.com/keys",
        cost_note="Free tier available. Very fast; no card required.",
        suggested_models=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
        ],
    ),
    base_url="https://api.groq.com/openai/v1",
)

_OPENROUTER = OpenAICompatibleProvider(
    ProviderInfo(
        id="openrouter",
        label="OpenRouter",
        default_model="meta-llama/llama-3.3-70b-instruct:free",
        key_url="https://openrouter.ai/keys",
        cost_note="Has genuinely free models (the ':free' suffix). One key, many models.",
        suggested_models=[
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-2-9b-it:free",
            "mistralai/mistral-7b-instruct:free",
        ],
    ),
    base_url="https://openrouter.ai/api/v1",
    # OpenRouter asks callers to identify themselves; these are the documented
    # attribution headers and carry nothing about the user.
    extra_headers={"HTTP-Referer": "https://atlas.local", "X-Title": "Atlas"},
)

PROVIDERS: dict[str, Provider] = {
    p.info.id: p
    for p in (
        AnthropicProvider(),
        _GROQ,
        GeminiProvider(),
        _OPENROUTER,
        OllamaProvider(),
    )
}


def default_provider_id() -> str:
    """Anthropic stays the default so existing installs keep their behaviour."""
    return "anthropic"


def get_provider(provider_id: Optional[str]) -> Provider:
    """Look up a provider, falling back to the default rather than raising.

    A stale or hand-edited setting must not break the coach — the worst case
    is that it answers from the wrong backend, which the UI shows plainly.
    """
    return PROVIDERS.get((provider_id or "").strip().lower()) or PROVIDERS[default_provider_id()]


def provider_catalog() -> list[dict]:
    """What Settings renders: every provider, what it costs, where to get a key."""
    catalog = []
    for provider in PROVIDERS.values():
        info = provider.info
        entry = {
            "id": info.id,
            "label": info.label,
            "default_model": info.default_model,
            "key_url": info.key_url,
            "cost_note": info.cost_note,
            "local": info.local,
            "needs_key": not info.local,
            "suggested_models": list(info.suggested_models),
        }
        # For the local provider, offer what is actually pulled on this machine.
        if isinstance(provider, OllamaProvider):
            installed = provider.installed_models()
            entry["installed_models"] = installed
            entry["available"] = bool(installed)
        catalog.append(entry)
    return catalog


#: Environment variable holding each provider's key, e.g. ATLAS_GROQ_API_KEY.
def key_env_name(provider_id: str) -> str:
    return f"ATLAS_{provider_id.strip().upper()}_API_KEY"
