"""Application settings.

Values can be overridden with environment variables prefixed ``ATLAS_`` (e.g.
``ATLAS_DATABASE_URL``) or via a ``.env`` file in the backend directory.
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# True when running from a PyInstaller bundle (the packaged desktop sidecar).
FROZEN = getattr(sys, "frozen", False)


def _user_data_dir() -> Path:
    """Per-user, writable, and persistent across app updates."""
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming")
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return root / "Atlas"


# Where the app keeps its own files (database, .env, trained models).
#
# Source checkout: backend/  (config.py -> core -> app -> backend).
# Frozen bundle: a per-user data directory. PyInstaller unpacks the bundle to a
# temp folder that is deleted on exit, so anything written next to the
# executable — the database included — would silently vanish between launches.
BASE_DIR = _user_data_dir() if FROZEN else Path(__file__).resolve().parents[2]

if FROZEN:
    BASE_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATLAS_",
        # Absolute, not "./.env": the packaged desktop build spawns this backend
        # with an arbitrary working directory, and a relative path would silently
        # resolve to nothing there.
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Atlas"
    env: str = "development"
    debug: bool = True

    # Local-first default: a SQLite file alongside the backend.
    database_url: str = f"sqlite:///{(BASE_DIR / 'atlas.db').as_posix()}"
    db_echo: bool = False

    # In dev we ensure tables exist on startup (create_all). Alembic becomes the
    # source of truth for schema evolution in a later phase.
    auto_create_tables: bool = True

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # Tauri desktop shell origins (Phase 7) — so a packaged build reaching an
        # absolute API base is allowed. Dev proxies /api through Vite and needs none.
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ]

    data_dir: str = (BASE_DIR / "data").as_posix()

    # AI coach (opt-in). When a key is set AND the `anthropic` package is installed,
    # the coach can call the Claude API — which sends a compact digest of the user's
    # data to Anthropic. Unset by default: the coach runs fully local/offline.
    anthropic_api_key: Optional[str] = None
    coach_model: str = "claude-opus-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
