"""Account registration, sign-in, and session lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import (
    hash_password,
    hash_token,
    new_session_token,
    password_problems,
    session_expiry,
    verify_password,
)
from app.models import owned_models
from app.models.user import AuthSession, User

log = get_logger("atlas.auth")


class AuthError(Exception):
    """Raised for anything the caller is allowed to see a reason for."""

    def __init__(self, message: str, *, fields: Optional[list[str]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.fields = fields or []


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ lookup
    def by_username(self, username: str) -> Optional[User]:
        return self.session.scalars(
            select(User).where(User.username == username.strip().lower())
        ).first()

    def by_email(self, email: str) -> Optional[User]:
        return self.session.scalars(
            select(User).where(User.email == email.strip().lower())
        ).first()

    def user_count(self) -> int:
        return len(list(self.session.scalars(select(User.id))))

    def all_users(self) -> list[User]:
        """Every account, oldest first.

        Background work (retraining, backups) has no request to take an
        identity from, so it walks this list and acts as each account in turn.
        """
        return list(self.session.scalars(select(User).order_by(User.created_at)))

    def all_ids(self) -> list[str]:
        return list(self.session.scalars(select(User.id).order_by(User.created_at)))

    def first_user(self) -> Optional[User]:
        """The earliest-created account — the owner of a pre-accounts vault."""
        return self.session.scalars(select(User).order_by(User.created_at)).first()

    # ---------------------------------------------------------------- register
    def register(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> User:
        username = username.strip().lower()
        if len(username) < 3:
            raise AuthError("Username must be at least 3 characters.", fields=["username"])
        if not username.replace("_", "").replace("-", "").isalnum():
            raise AuthError(
                "Username may only contain letters, numbers, - and _.", fields=["username"]
            )
        if self.by_username(username):
            raise AuthError("That username is taken.", fields=["username"])

        problems = password_problems(password)
        if problems:
            raise AuthError(" ".join(problems), fields=["password"])

        email = email.strip().lower() if email else None
        if email and self.by_email(email):
            raise AuthError("That email is already registered.", fields=["email"])

        first_account = self.user_count() == 0

        user = User(
            username=username,
            email=email,
            display_name=(display_name or username).strip(),
            password_hash=hash_password(password),
        )
        self.session.add(user)
        self.session.commit()

        if first_account:
            claimed = self.claim_orphan_vault(user)
            if claimed:
                log.info(
                    "auth.vault_claimed",
                    extra={"username": user.username, "rows": claimed},
                )
        return user

    def claim_orphan_vault(self, user: User) -> int:
        """Give this account any data that predates accounts entirely.

        Atlas stored habits, logs and journals long before it had users, and an
        upgrade must not make that history vanish. Rather than have the
        migration invent an owner, unowned rows sit in the database as
        ``user_id IS NULL`` — visible to nobody — until the first account
        exists to claim them. Called exactly once, when that account is created.

        Deliberately a bulk UPDATE against ``user_id IS NULL``: it can only ever
        touch rows that no account owns, so it cannot move data between
        accounts even if it were somehow called again.
        """
        total = 0
        for model in owned_models():
            result = self.session.execute(
                update(model).where(model.user_id.is_(None)).values(user_id=user.id)
            )
            total += result.rowcount or 0
        self.session.commit()
        self._adopt_legacy_models(user)
        return total

    @staticmethod
    def _adopt_legacy_models(user: User) -> int:
        """Move a pre-scoping model registry into this account's folder.

        Models used to live directly in ``data/models/``; they are now keyed by
        account. Without this, upgrading would silently orphan a trained model
        — the app would quietly fall back to heuristics and the quality history
        would read as empty, which looks exactly like a bug.

        Plain file moves, no ``app.learning`` import: this runs on the core
        registration path and must not drag joblib in behind it.
        """
        from pathlib import Path

        from app.core.config import get_settings

        root = Path(get_settings().data_dir) / "models"
        legacy_index = root / "registry.json"
        destination = root / user.id
        if not legacy_index.exists() or (destination / "registry.json").exists():
            return 0

        destination.mkdir(parents=True, exist_ok=True)
        moved = 0
        for path in [*sorted(root.glob("*.joblib")), legacy_index]:
            path.replace(destination / path.name)
            moved += 1
        log.info("auth.models_adopted", extra={"username": user.username, "files": moved})
        return moved

    # ------------------------------------------------------------------- login
    def authenticate(self, identifier: str, password: str) -> User:
        ident = identifier.strip().lower()
        user = self.by_username(ident) or (self.by_email(ident) if "@" in ident else None)
        # Same message either way: distinguishing them tells an attacker which
        # usernames exist.
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("Incorrect username or password.")
        user.last_login_at = datetime.now(timezone.utc)
        self.session.commit()
        return user

    # ---------------------------------------------------------------- sessions
    def start_session(self, user: User) -> str:
        """Create a session and return the raw token — the only time it exists."""
        token = new_session_token()
        self.session.add(
            AuthSession(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=session_expiry(),
            )
        )
        self.session.commit()
        return token

    def resolve(self, token: str) -> Optional[User]:
        row = self.session.scalars(
            select(AuthSession).where(AuthSession.token_hash == hash_token(token))
        ).first()
        if row is None:
            return None
        expires = row.expires_at
        if expires.tzinfo is None:  # SQLite hands back naive datetimes
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            self.session.delete(row)
            self.session.commit()
            return None
        return row.user

    def end_session(self, token: str) -> None:
        row = self.session.scalars(
            select(AuthSession).where(AuthSession.token_hash == hash_token(token))
        ).first()
        if row is not None:
            self.session.delete(row)
            self.session.commit()

    def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(current, user.password_hash):
            raise AuthError("Current password is incorrect.", fields=["current_password"])
        problems = password_problems(new)
        if problems:
            raise AuthError(" ".join(problems), fields=["new_password"])
        user.password_hash = hash_password(new)
        # Every other session is invalidated — a password change should log out
        # anywhere the old one might still be held.
        for s in list(user.sessions):
            self.session.delete(s)
        self.session.commit()
