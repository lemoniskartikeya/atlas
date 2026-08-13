"""The coach's chat backends: request shaping, and readable failures.

No network here. Each provider's HTTP call is intercepted so the tests pin what
Atlas *sends* (every provider wants a different shape for the same conversation)
and what it does with what comes back.
"""
from __future__ import annotations

import pytest

from app.services.llm import PROVIDERS, ChatMessage, LLMError, get_provider
from app.services.llm.base import normalise
from app.services.llm.providers import GeminiProvider, OllamaProvider
from app.services.llm.registry import key_env_name, provider_catalog

CALL = dict(system="You are Atlas Coach.", model="m", max_tokens=64, timeout=5.0)


# ------------------------------------------------------------------ normalise
def test_normalise_drops_blanks_and_merges_same_role():
    out = normalise(
        [
            ChatMessage("user", "  "),
            ChatMessage("user", "hello"),
            ChatMessage("user", "again"),
            ChatMessage("assistant", "hi"),
        ]
    )
    assert [(m.role, m.content) for m in out] == [
        ("user", "hello\n\nagain"),
        ("assistant", "hi"),
    ]


def test_normalise_always_starts_on_a_user_turn():
    """Chat APIs reject a history that opens with the assistant."""
    out = normalise([ChatMessage("assistant", "stale reply"), ChatMessage("user", "hi")])
    assert out[0].role == "user"
    assert out[0].content == "hi"


def test_normalise_substitutes_a_prompt_when_everything_was_empty():
    out = normalise([ChatMessage("assistant", "   ")])
    assert len(out) == 1 and out[0].role == "user" and out[0].content


# ------------------------------------------------------------------- catalog
def test_every_provider_is_reachable_and_describes_itself():
    for entry in provider_catalog():
        assert entry["label"] and entry["cost_note"]
        assert entry["default_model"]
        assert get_provider(entry["id"]) is PROVIDERS[entry["id"]]
        # A provider needing a key must say where to get one — Atlas cannot
        # obtain one on the user's behalf.
        if entry["needs_key"]:
            assert entry["key_url"], f"{entry['id']} gives no way to get a key"


def test_an_unknown_provider_falls_back_rather_than_raising():
    assert get_provider("nope-not-real") is PROVIDERS["anthropic"]
    assert get_provider(None) is PROVIDERS["anthropic"]


def test_key_env_names_are_namespaced_per_provider():
    assert key_env_name("groq") == "ATLAS_GROQ_API_KEY"
    assert key_env_name("anthropic") == "ATLAS_ANTHROPIC_API_KEY"


# ------------------------------------------------- request shape per provider
def _capture(monkeypatch, module_attr: str, response: dict):
    """Replace the HTTP call and record what would have been sent."""
    seen: dict = {}

    def fake_post(url, *, headers, payload, timeout):
        seen.update(url=url, headers=headers, payload=payload)
        return response

    monkeypatch.setattr(module_attr, fake_post)
    return seen


def test_openai_compatible_puts_the_system_prompt_in_the_message_list(monkeypatch):
    seen = _capture(
        monkeypatch,
        "app.services.llm.providers._http_post",
        {"choices": [{"message": {"content": "hi there"}}]},
    )
    reply = PROVIDERS["groq"].complete(
        messages=[ChatMessage("user", "hello")], api_key="k", **CALL
    )

    assert reply == "hi there"
    assert seen["payload"]["messages"][0] == {
        "role": "system",
        "content": "You are Atlas Coach.",
    }
    assert seen["headers"]["Authorization"] == "Bearer k"


def test_gemini_uses_its_own_role_names_and_system_field(monkeypatch):
    seen = _capture(
        monkeypatch,
        "app.services.llm.providers._http_post",
        {"candidates": [{"content": {"parts": [{"text": "hi there"}]}}]},
    )
    reply = GeminiProvider().complete(
        messages=[ChatMessage("user", "hello"), ChatMessage("assistant", "yes")],
        api_key="k",
        **CALL,
    )

    assert reply == "hi there"
    # The system prompt is a dedicated field, not a message...
    assert seen["payload"]["systemInstruction"]["parts"][0]["text"] == CALL["system"]
    # ...and the assistant is called "model".
    assert [c["role"] for c in seen["payload"]["contents"]] == ["user", "model"]
    assert seen["headers"]["x-goog-api-key"] == "k"


def test_ollama_needs_no_key_and_talks_to_localhost(monkeypatch):
    seen = _capture(
        monkeypatch,
        "app.services.llm.providers._http_post",
        {"message": {"content": "hi there"}},
    )
    reply = OllamaProvider().complete(
        messages=[ChatMessage("user", "hello")], api_key=None, **CALL
    )

    assert reply == "hi there"
    assert seen["url"].startswith("http://127.0.0.1:11434")
    assert seen["headers"] == {}


# ------------------------------------------------------------------- failures
def test_a_missing_key_is_reported_before_any_network_call(monkeypatch):
    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("attempted a request with no key")

    monkeypatch.setattr("app.services.llm.providers._http_post", explode)
    with pytest.raises(LLMError, match="key"):
        PROVIDERS["groq"].complete(messages=[ChatMessage("user", "hi")], api_key=None, **CALL)


def test_an_empty_completion_is_an_error_not_an_empty_bubble(monkeypatch):
    _capture(
        monkeypatch,
        "app.services.llm.providers._http_post",
        {"choices": [{"message": {"content": "   "}}]},
    )
    with pytest.raises(LLMError, match="empty"):
        PROVIDERS["groq"].complete(messages=[ChatMessage("user", "hi")], api_key="k", **CALL)


def test_a_blocked_gemini_prompt_explains_itself(monkeypatch):
    _capture(
        monkeypatch,
        "app.services.llm.providers._http_post",
        {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}},
    )
    with pytest.raises(LLMError, match="SAFETY"):
        GeminiProvider().complete(messages=[ChatMessage("user", "hi")], api_key="k", **CALL)


def test_ollama_being_offline_tells_the_user_how_to_start_it(monkeypatch):
    def unreachable(*args, **kwargs):
        raise LLMError("Could not reach the provider: connection refused")

    monkeypatch.setattr("app.services.llm.providers._http_post", unreachable)
    with pytest.raises(LLMError, match="ollama.com|pull"):
        OllamaProvider().complete(messages=[ChatMessage("user", "hi")], api_key=None, **CALL)
