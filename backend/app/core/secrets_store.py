"""Read/write local secrets in ``backend/.env``.

The desktop app has no server to hold credentials, so the Anthropic API key the
user pastes into Settings is persisted to the same ``.env`` the app already
reads at startup. That file is gitignored, and this module only ever touches
the one key it is asked about — surrounding lines, comments, and ordering are
preserved so a hand-edited .env survives a write from the UI.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from app.core.config import BASE_DIR, get_settings

ENV_PATH = BASE_DIR / ".env"
_KEY = "ATLAS_ANTHROPIC_API_KEY"


def _quote(value: str) -> str:
    # Keys are opaque tokens; quoting keeps any stray character from being read
    # as shell/dotenv syntax.
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def set_secret(name: str, value: Optional[str]) -> None:
    """Upsert (or, when value is None, delete) one variable in .env."""
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    pattern = re.compile(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=")
    kept = [ln for ln in lines if not pattern.match(ln)]

    if value:
        kept.append(f"{name}={_quote(value)}")

    text = "\n".join(kept).strip()
    ENV_PATH.write_text(text + "\n" if text else "", encoding="utf-8")

    # Also update the live environment. The file is what survives a restart, but
    # the *running* process must reflect the change immediately — and env vars
    # outrank the .env file, so this works no matter which .env got written.
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)

    # Settings is lru_cached; without this the running process keeps serving the
    # old value and the UI would report "saved" while the coach stayed offline.
    get_settings.cache_clear()


def set_anthropic_key(value: Optional[str]) -> None:
    set_secret(_KEY, value.strip() if value else None)


def mask(value: Optional[str]) -> Optional[str]:
    """`sk-ant-api03-abc…wxyz` — enough to recognise, not enough to use."""
    if not value:
        return None
    if len(value) <= 12:
        return "•" * len(value)
    return f"{value[:11]}…{value[-4:]}"
