"""Tests for the AI coach: local mode (offline) + the guarded Claude path."""
from __future__ import annotations

import sys
import types

from app.core.config import get_settings

BASE = "/api/v1"


def _habit(client, **body):
    body.setdefault("title", "Meditate")
    return client.post(f"{BASE}/habits", json=body).json()["id"]


# ------------------------------------------------------------------ status/local

def test_status_defaults_to_local(client):
    body = client.get(f"{BASE}/coach/status").json()
    assert body["ai_available"] is False
    assert body["model"] is None


def test_local_reply_is_grounded_and_offline(client):
    hid = _habit(client, title="Meditate")
    client.post(f"{BASE}/habits/{hid}/logs", json={})

    r = client.post(
        f"{BASE}/coach/ask",
        json={"messages": [{"role": "user", "content": "what should I focus on today?"}]},
    ).json()
    assert r["mode"] == "local"
    assert r["reply"]
    assert r["grounded_on"]


def test_local_answers_about_a_named_habit(client):
    _habit(client, title="Deep Work")
    r = client.post(
        f"{BASE}/coach/ask",
        json={"messages": [{"role": "user", "content": "how is my deep work habit going?"}]},
    ).json()
    assert r["mode"] == "local"
    assert "Deep Work" in r["reply"]


# ---------------------------------------------------------------- Claude path

class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_Block(text)]
        self.stop_reason = stop_reason


def _install_fake_anthropic(monkeypatch, resp):
    class _Messages:
        def create(self, **kwargs):
            _Messages.captured = kwargs
            return resp

    class _Anthropic:
        def __init__(self, api_key=None):
            self.messages = _Messages()

    module = types.ModuleType("anthropic")
    module.Anthropic = _Anthropic
    monkeypatch.setitem(sys.modules, "anthropic", module)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key")


def test_ai_mode_uses_claude_when_configured(client, monkeypatch):
    _habit(client, title="Journal")
    _install_fake_anthropic(monkeypatch, _Resp("Protect Journal today — it's most at risk."))

    r = client.post(
        f"{BASE}/coach/ask",
        json={"messages": [{"role": "user", "content": "what should I focus on?"}]},
    ).json()
    assert r["mode"] == "ai"
    assert r["model"] == get_settings().coach_model
    assert "Journal" in r["reply"]

    status = client.get(f"{BASE}/coach/status").json()
    assert status["ai_available"] is True
    assert status["provider"] == "anthropic"


def test_ai_refusal_falls_back_to_local(client, monkeypatch):
    _habit(client, title="Read")
    _install_fake_anthropic(monkeypatch, _Resp("", stop_reason="refusal"))

    r = client.post(
        f"{BASE}/coach/ask",
        json={"messages": [{"role": "user", "content": "how am I doing?"}]},
    ).json()
    assert r["mode"] == "local"  # refusal -> graceful local fallback
    assert r["reply"]


def test_use_ai_false_stays_local(client, monkeypatch):
    _habit(client, title="Exercise")
    _install_fake_anthropic(monkeypatch, _Resp("should not be used"))

    r = client.post(
        f"{BASE}/coach/ask",
        json={"messages": [{"role": "user", "content": "hello"}], "use_ai": False},
    ).json()
    assert r["mode"] == "local"
    assert "should not be used" not in r["reply"]
