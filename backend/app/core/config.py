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

# Where *read-only* bundled resources live (alembic.ini, the migration scripts).
# These ship inside the executable and are unpacked to a temp dir, so they are
# emphatically NOT under BASE_DIR once frozen.
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


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

    # Run Alembic migrations on startup. This is how a packaged install picks up
    # schema changes; create_all can add tables but never columns.
    run_migrations: bool = True
    # Fallback used only when migrations are off (tests, throwaway databases).
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

    #: Port the backend listens on. Needed to build Google's loopback redirect
    #: URI, which has to match what is registered in the Cloud console exactly.
    port: int = 8000

    # Sign in with Google. The client ID belongs to whoever runs Atlas: it is
    # created in their own Google Cloud project and cannot be shipped inside a
    # binary anyone can read, so it is configuration rather than a constant.
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None

    # --------------------------------------------------------------- email OTP
    # Transactional email, for verification codes. Credentials live on the
    # server only; the desktop client never holds them and never sends mail.
    #
    # Two ways to deliver. "auto" (the default) picks whichever is configured,
    # preferring SMTP — so setting the SMTP variables is enough, with no second
    # switch to remember. Set explicitly to pin one.
    email_provider: str = "auto"  # "auto" | "smtp" | "resend"

    #: SMTP. Works with an ordinary mailbox (e.g. a Gmail App Password), so it
    #: needs no paid plan and no domain of your own.
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    #: STARTTLS on 587 (the usual case); implicit TLS is used for port 465.
    smtp_starttls: bool = True

    #: Resend. Free to a point, but only delivers to arbitrary recipients once
    #: you have verified a domain you own.
    resend_api_key: Optional[str] = None

    email_from: Optional[str] = None
    email_from_name: str = "Atlas"

    def smtp_configured(self) -> bool:
        return bool(
            (self.smtp_host or "").strip()
            and (self.smtp_user or "").strip()
            and (self.smtp_password or "").strip()
        )

    def resend_configured(self) -> bool:
        return bool((self.resend_api_key or "").strip())

    def active_email_provider(self) -> Optional[str]:
        """Which sender will actually be used, or None if nothing can send.

        An address to send *from* is required either way: SMTP falls back to
        the login user, Resend has nothing to fall back to.
        """
        choice = (self.email_provider or "auto").strip().lower()
        if choice == "smtp":
            return "smtp" if self.smtp_configured() else None
        if choice == "resend":
            return "resend" if self.resend_configured() and (self.email_from or "").strip() else None
        if self.smtp_configured():
            return "smtp"
        if self.resend_configured() and (self.email_from or "").strip():
            return "resend"
        return None

    #: Requests per address, and the enforced quiet period between them.
    otp_per_email_per_hour: int = 5
    otp_resend_cooldown_seconds: int = 60
    #: Ceiling per caller address, so one machine cannot farm codes across many
    #: mailboxes even while each individual address stays under its own limit.
    otp_per_ip_per_hour: int = 15

    #: Answer "unknown address" and "already registered" with the same neutral
    #: response, hiding which addresses have accounts. Off by default because
    #: the product's sign-in flow tells the user which of the two applies.
    otp_neutral_responses: bool = False

    #: Development only: return the code in the API response instead of relying
    #: on a mailbox. Ignored unless `env` is exactly "development" — see
    #: `otp_echo_allowed()`, which is the only thing that should read this.
    otp_dev_echo: bool = False

    def otp_echo_allowed(self) -> bool:
        """Whether a code may be handed back to the caller.

        Two independent conditions, both required, and the environment check is
        not something a stray env var can flip on a deployed instance: setting
        ATLAS_OTP_DEV_ECHO=true in production does nothing at all.
        """
        return self.otp_dev_echo and self.env.strip().lower() == "development"

    # AI coach (opt-in). With no key the coach runs fully offline, answering from
    # the user's own numbers. Configuring a provider sends a compact digest of
    # that data to whoever it names — except "ollama", which is a model running
    # on this machine and never leaves it.
    #
    # Keys live one per provider (ATLAS_GROQ_API_KEY, ATLAS_GEMINI_API_KEY, ...)
    # so switching provider doesn't discard the key for the previous one.
    coach_provider: str = "anthropic"
    #: Blank means "whatever that provider's default model is".
    coach_model: str = ""

    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None

    def coach_key_for(self, provider_id: str) -> Optional[str]:
        """The stored key for one provider, if any. Local providers have none."""
        return getattr(self, f"{provider_id.strip().lower()}_api_key", None)

    # Background jobs (retraining, automatic backups). Runs in-process; set
    # false to keep the API purely request-driven.
    jobs_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
