"""Account registration, sign-in, and session lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password,
    hash_token,
    new_session_token,
    password_problems,
    session_expiry,
    verify_password,
)
from app.models.user import AuthSession, User


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

        user = User(
            username=username,
            email=email,
            display_name=(display_name or username).strip(),
            password_hash=hash_password(password),
        )
        self.session.add(user)
        self.session.commit()
        return user

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
