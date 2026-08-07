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


# ------------------------------------------------- general questions & key mgmt

def test_local_mode_admits_it_cannot_answer_general_questions(client):
    """Offline, an unrelated question must not get an unrelated stats dump."""
    r = client.post(
        f"{BASE}/coach/ask",
        json={"messages": [{"role": "user", "content": "what is the capital of France?"}]},
    ).json()
    assert r["mode"] == "local"
    assert "can't answer that one offline" in r["reply"]
    assert "Settings" in r["reply"]  # points at how to enable it


def test_ai_mode_answers_general_questions(client, monkeypatch):
    """With a key, a non-Atlas question goes to Claude and comes back answered."""
    _install_fake_anthropic(monkeypatch, _Resp("Paris."))
    r = client.post(
        f"{BASE}/coach/ask",
        json={"messages": [{"role": "user", "content": "what is the capital of France?"}]},
    ).json()
    assert r["mode"] == "ai"
    assert r["reply"] == "Paris."


def test_system_prompt_permits_general_assistance(client, monkeypatch):
    """The prompt must not corner the model into habit-coaching only."""
    _install_fake_anthropic(monkeypatch, _Resp("ok"))
    client.post(f"{BASE}/coach/ask", json={"messages": [{"role": "user", "content": "hi"}]})

    import sys as _sys

    system = _sys.modules["anthropic"].Anthropic().messages.__class__.captured["system"]
    assert "general-purpose assistant first" in system
    assert "Do NOT deflect a general question" in system
    # Still grounded: the user's data rides along.
    assert "USER'S ATLAS DATA" in system


def test_status_reports_key_and_sdk_state(client):
    body = client.get(f"{BASE}/coach/status").json()
    assert body["has_key"] is False
    assert body["key_hint"] is None
    assert "sdk_installed" in body


def test_key_can_be_saved_and_cleared(client, monkeypatch, tmp_path):
    """Saving writes to .env, clears the settings cache, and never echoes the key."""
    from app.core import secrets_store

    monkeypatch.setattr(secrets_store, "ENV_PATH", tmp_path / ".env")

    res = client.put(f"{BASE}/coach/key", json={"api_key": "sk-ant-api03-SECRETVALUE-1234"})
    assert res.status_code == 200
    body = res.json()
    assert body["has_key"] is True
    assert "SECRETVALUE" not in str(body)  # masked, never returned in full
    assert body["key_hint"].endswith("1234")

    assert "sk-ant-api03-SECRETVALUE-1234" in (tmp_path / ".env").read_text()

    cleared = client.delete(f"{BASE}/coach/key").json()
    assert cleared["has_key"] is False


def test_saving_a_key_preserves_other_env_lines(client, monkeypatch, tmp_path):
    from app.core import secrets_store

    env = tmp_path / ".env"
    env.write_text("# my notes\nATLAS_DEBUG=true\nATLAS_ANTHROPIC_API_KEY=old\n")
    monkeypatch.setattr(secrets_store, "ENV_PATH", env)

    client.put(f"{BASE}/coach/key", json={"api_key": "sk-ant-new"})
    text = env.read_text()
    assert "# my notes" in text
    assert "ATLAS_DEBUG=true" in text
    assert "old" not in text  # replaced, not duplicated
    assert text.count("ATLAS_ANTHROPIC_API_KEY") == 1


def test_key_test_reports_missing_key(client, monkeypatch, tmp_path):
    from app.core import secrets_store

    monkeypatch.setattr(secrets_store, "ENV_PATH", tmp_path / ".env")
    secrets_store.set_anthropic_key(None)

    body = client.post(f"{BASE}/coach/key/test").json()
    assert body["ok"] is False
    assert "No API key" in body["detail"]
