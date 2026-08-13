"""Concrete chat backends.

Anthropic goes through the official ``anthropic`` SDK. Everything else is plain
HTTP against the provider's documented endpoint — no third-party client
libraries, so the packaged backend gains no new dependencies beyond ``httpx``,
which FastAPI already pulls in.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from app.services.llm.base import ChatMessage, LLMError, ProviderInfo, normalise

_UA = {"User-Agent": "Atlas/0.1 (+https://github.com/atlas)"}


def _http_post(url: str, *, headers: dict, payload: dict, timeout: float) -> dict:
    """POST JSON and return JSON, translating failures into readable errors."""
    import httpx

    try:
        res = httpx.post(url, headers={**_UA, **headers}, json=payload, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise LLMError(f"The request timed out after {timeout:.0f}s.") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach the provider: {exc}") from exc

    if res.status_code == 401 or res.status_code == 403:
        raise LLMError("That API key was rejected. Check it and try again.")
    if res.status_code == 429:
        raise LLMError("Rate limited by the provider — wait a moment and retry.")
    if res.status_code >= 400:
        raise LLMError(_explain(res.status_code, res.text))

    try:
        return res.json()
    except json.JSONDecodeError as exc:
        raise LLMError("The provider returned something that wasn't JSON.") from exc


def _explain(status: int, body: str) -> str:
    """Pull the provider's own message out of an error body when there is one."""
    try:
        data = json.loads(body)
    except Exception:
        return f"Provider error {status}."
    for key in ("error", "message", "detail"):
        node = data.get(key) if isinstance(data, dict) else None
        if isinstance(node, str):
            return f"Provider error {status}: {node}"
        if isinstance(node, dict) and isinstance(node.get("message"), str):
            return f"Provider error {status}: {node['message']}"
    return f"Provider error {status}."


# --------------------------------------------------------------------- Anthropic
class AnthropicProvider:
    info = ProviderInfo(
        id="anthropic",
        label="Anthropic (Claude)",
        default_model="claude-opus-5",
        key_url="https://console.anthropic.com/settings/keys",
        cost_note="Paid. Highest quality; needs billing set up.",
        suggested_models=["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
    )

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        model: str,
        api_key: Optional[str],
        max_tokens: int,
        timeout: float,
    ) -> str:
        if not api_key:
            raise LLMError("No Anthropic API key is set.")
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError(
                "The `anthropic` package isn't installed. Run: pip install -r requirements-ai.txt"
            ) from exc

        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": m.role, "content": m.content} for m in normalise(messages)],
            )
        except Exception as exc:  # SDK raises typed errors; surface the message
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        # A refusal is a successful HTTP call with no usable content — treat it
        # as "no answer" so the caller falls back rather than showing an empty box.
        if getattr(resp, "stop_reason", None) == "refusal":
            raise LLMError("The model declined to answer that one.")
        text = "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"
        )
        if not text.strip():
            raise LLMError("The model returned an empty response.")
        return text.strip()


# ------------------------------------------------------- OpenAI-compatible chat
class OpenAICompatibleProvider:
    """Groq, OpenRouter, and anything else speaking /chat/completions."""

    def __init__(self, info: ProviderInfo, base_url: str, extra_headers: Optional[dict] = None):
        self.info = info
        self._base_url = base_url.rstrip("/")
        self._extra_headers = extra_headers or {}

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        model: str,
        api_key: Optional[str],
        max_tokens: int,
        timeout: float,
    ) -> str:
        if not api_key:
            raise LLMError(f"No {self.info.label} API key is set.")

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}]
            + [{"role": m.role, "content": m.content} for m in normalise(messages)],
        }
        data = _http_post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", **self._extra_headers},
            payload=payload,
            timeout=timeout,
        )
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("The provider's response had no message content.") from exc
        if not isinstance(text, str) or not text.strip():
            raise LLMError("The model returned an empty response.")
        return text.strip()


# ------------------------------------------------------------------- Gemini
class GeminiProvider:
    """Google's Generative Language API — its own request shape, not OpenAI's."""

    info = ProviderInfo(
        id="gemini",
        label="Google Gemini",
        default_model="gemini-2.0-flash",
        key_url="https://aistudio.google.com/apikey",
        cost_note="Free tier available. Rate-limited but no card required.",
        suggested_models=["gemini-2.0-flash", "gemini-2.0-flash-lite"],
    )

    _BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        model: str,
        api_key: Optional[str],
        max_tokens: int,
        timeout: float,
    ) -> str:
        if not api_key:
            raise LLMError("No Google Gemini API key is set.")

        payload = {
            # Gemini names the assistant role "model" and carries the system
            # prompt in its own field rather than as a message.
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": "model" if m.role == "assistant" else "user",
                    "parts": [{"text": m.content}],
                }
                for m in normalise(messages)
            ],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        data = _http_post(
            f"{self._BASE}/{model}:generateContent",
            headers={"x-goog-api-key": api_key},
            payload=payload,
            timeout=timeout,
        )

        candidates = data.get("candidates") or []
        if not candidates:
            blocked = (data.get("promptFeedback") or {}).get("blockReason")
            raise LLMError(
                f"Gemini returned no answer ({blocked})." if blocked
                else "Gemini returned no answer."
            )
        parts = ((candidates[0].get("content") or {}).get("parts")) or []
        text = "".join(p.get("text", "") for p in parts)
        if not text.strip():
            raise LLMError("The model returned an empty response.")
        return text.strip()


# ------------------------------------------------------------------- Ollama
class OllamaProvider:
    """A model running on this machine. No key, no network, nothing leaves."""

    info = ProviderInfo(
        id="ollama",
        label="Local model (Ollama)",
        default_model="llama3.2",
        key_url="https://ollama.com/download",
        cost_note="Free and fully offline. Needs Ollama installed and a model pulled.",
        local=True,
        suggested_models=["llama3.2", "llama3.1", "qwen2.5", "mistral", "phi4"],
    )

    BASE_URL = "http://127.0.0.1:11434"

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        model: str,
        api_key: Optional[str],
        max_tokens: int,
        timeout: float,
    ) -> str:
        payload = {
            "model": model,
            "stream": False,
            "options": {"num_predict": max_tokens},
            "messages": [{"role": "system", "content": system}]
            + [{"role": m.role, "content": m.content} for m in normalise(messages)],
        }
        try:
            data = _http_post(
                f"{self.BASE_URL}/api/chat", headers={}, payload=payload, timeout=timeout
            )
        except LLMError as exc:
            # The overwhelmingly likely cause is that Ollama simply isn't running.
            if "Could not reach" in str(exc):
                raise LLMError(
                    "Couldn't reach Ollama on this machine. Start it (or install it "
                    "from ollama.com), then pull a model with: ollama pull llama3.2"
                ) from exc
            raise

        text = ((data.get("message") or {}).get("content")) or ""
        if not text.strip():
            raise LLMError(
                f"Ollama returned nothing. Is the model '{model}' pulled? "
                f"Run: ollama pull {model}"
            )
        return text.strip()

    @classmethod
    def installed_models(cls, timeout: float = 3.0) -> list[str]:
        """Models already pulled locally, for the Settings dropdown. Never raises."""
        import httpx

        try:
            res = httpx.get(f"{cls.BASE_URL}/api/tags", timeout=timeout)
            res.raise_for_status()
            return [m["name"] for m in res.json().get("models", []) if m.get("name")]
        except Exception:
            return []
