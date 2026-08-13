"""Atlas account + session ORM models.

Accounts are an identity layer over a single local vault: signing in tells
Atlas *who you are* (and gates the UI), it does not partition habits/tasks per
user. Multi-tenant scoping would mean re-keying every table and is a separate
piece of work.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, index=True, default=None
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    # Blank for accounts that only ever sign in with Google: there is no
    # password to check, and `authenticate` refuses an empty hash outright
    # rather than letting an empty string compare equal to anything.
    password_hash: Mapped[str] = mapped_column(String(255))
    #: Google's stable account id ("sub"). Not the email — people change those,
    #: and matching on a mutable field is how accounts get taken over.
    google_sub: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, index=True, default=None
    )
    #: Set when the address was proven by entering a code sent to it (or by
    #: Google vouching for it). Null means "we have an address on file but
    #: nobody has shown they can read that mailbox".
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )

    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "auth_sessions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Only the digest is stored — a stolen database yields no usable tokens.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="sessions")
