"""Application settings.

Values can be overridden with environment variables prefixed ``ATLAS_`` (e.g.
``ATLAS_DATABASE_URL``) or via a ``.env`` file in the backend directory.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/  (config.py -> core -> app -> backend)
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATLAS_",
        env_file=".env",
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
    ]

    data_dir: str = (BASE_DIR / "data").as_posix()


@lru_cache
def get_settings() -> Settings:
    return Settings()
