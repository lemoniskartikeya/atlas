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
    assert body["has_key"] is False
    # Status still names the provider and model that *would* answer, so
    # Settings can show the choice before any key exists.
    assert body["provider"] == "anthropic"
    assert body["model"]
    assert [p["id"] for p in body["providers"]]


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
        # Mirror the real client's tolerance for keyword args (timeout, etc.)
        # so the stub does not fail on options the SDK genuinely accepts.
        def __init__(self, api_key=None, **kwargs):
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
    assert r["model"] == "claude-opus-5"  # provider default, since none is pinned
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
    # Names the provider � with several to choose from, "no API key" alone
    # doesn't tell you which one is missing.
    assert "Anthropic" in body["detail"] and "key" in body["detail"]


# ------------------------------------------------- choosing a provider (multi)
#
# The coach used to speak only to Anthropic, which made the one optional feature
# in Atlas depend on one paid account. These pin the selection behaviour: keys
# are kept per provider, an unknown id is refused, and the local provider needs
# no key at all.
def _env(monkeypatch, tmp_path):
    from app.core import secrets_store

    monkeypatch.setattr(secrets_store, "ENV_PATH", tmp_path / ".env")
    return secrets_store


def test_status_lists_every_provider_with_a_way_to_get_a_key(client):
    providers = client.get(f"{BASE}/coach/status").json()["providers"]
    by_id = {p["id"]: p for p in providers}

    assert {"anthropic", "groq", "gemini", "openrouter", "ollama"} <= set(by_id)
    for entry in providers:
        assert entry["cost_note"], f"{entry['id']} does not say what it costs"
        if entry["needs_key"]:
            assert entry["key_url"], f"{entry['id']} gives no way to get a key"
    # The local option is the one that needs nothing.
    assert by_id["ollama"]["local"] is True
    assert by_id["ollama"]["needs_key"] is False


def test_choosing_a_provider_switches_who_answers(client, monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)

    body = client.put(f"{BASE}/coach/provider", json={"provider": "groq"}).json()
    assert body["provider"] == "groq"
    assert body["provider_label"] == "Groq"
    # No model pinned, so the provider's own default is reported.
    assert body["model"] == "llama-3.3-70b-versatile"
    # Selected but unusable until a key exists — and that is stated, not implied.
    assert body["ai_available"] is False
    assert body["needs_key"] is True


def test_a_pinned_model_overrides_the_provider_default(client, monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    body = client.put(
        f"{BASE}/coach/provider",
        json={"provider": "groq", "model": "llama-3.1-8b-instant"},
    ).json()
    assert body["model"] == "llama-3.1-8b-instant"


def test_an_unknown_provider_is_refused(client):
    res = client.put(f"{BASE}/coach/provider", json={"provider": "skynet"})
    assert res.status_code == 400
    assert "skynet" in res.json()["detail"]


def test_keys_are_kept_per_provider(client, monkeypatch, tmp_path):
    """Trying a second free tier must not discard the first one's key."""
    _env(monkeypatch, tmp_path)

    client.put(f"{BASE}/coach/key", json={"provider": "groq", "api_key": "gsk_aaaaaaaaaa"})
    client.put(f"{BASE}/coach/key", json={"provider": "gemini", "api_key": "AIza_bbbbbbbbb"})

    on_groq = client.put(f"{BASE}/coach/provider", json={"provider": "groq"}).json()
    assert on_groq["has_key"] is True
    assert on_groq["ai_available"] is True

    on_gemini = client.put(f"{BASE}/coach/provider", json={"provider": "gemini"}).json()
    assert on_gemini["has_key"] is True
    # The earlier key survived the switch.
    assert on_gemini["key_hint"] != on_groq["key_hint"]


def test_the_local_provider_needs_no_key(client, monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    body = client.put(f"{BASE}/coach/provider", json={"provider": "ollama"}).json()

    assert body["local_provider"] is True
    assert body["needs_key"] is False
    # Usable without any key — whether Ollama is actually running is proven by
    # asking it, not by configuration.
    assert body["ai_available"] is True


def test_an_unreachable_provider_falls_back_to_the_local_answer(
    client, monkeypatch, tmp_path
):
    """A dead provider must never cost the user their answer."""
    _env(monkeypatch, tmp_path)
    _habit(client, title="Stretch")
    client.put(f"{BASE}/coach/provider", json={"provider": "ollama"})

    from app.services.llm import LLMError

    def unreachable(*args, **kwargs):
        raise LLMError("Couldn't reach Ollama on this machine.")

    monkeypatch.setattr("app.services.llm.providers.OllamaProvider.complete", unreachable)

    r = client.post(
        f"{BASE}/coach/ask",
        json={"messages": [{"role": "user", "content": "how am I doing?"}]},
    ).json()
    assert r["mode"] == "local"
    assert r["reply"].strip()
