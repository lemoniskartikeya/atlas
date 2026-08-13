"""Pending email verification codes.

Deliberately **not** an ``OwnedMixin`` model. Every other table in Atlas belongs
to an account and is filtered by the scoping layer, but these rows are written
and read *before* anyone is signed in — during registration there is no account
yet, and during login the whole point is that we have not authenticated the
caller. An owned model would have its query refused by ``app.core.scoping``,
which raises rather than silently returning nothing.

The plaintext code never touches this table: only a salted scrypt hash of it,
alongside everything needed to decide whether a guess should be honoured.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class VerificationPurpose:
    """What the code is for. Not an Enum column: SQLite stores these as text
    anyway, and the surrounding code reads better against plain constants."""

    LOGIN = "login"
    SIGNUP = "signup"

    ALL = (LOGIN, SIGNUP)


class EmailVerification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "email_verifications"

    #: Always normalized (trimmed + lowercased) before it gets here, so this
    #: doubles as the rate-limit key and can be compared directly.
    email: Mapped[str] = mapped_column(String(255), index=True)
    purpose: Mapped[str] = mapped_column(String(16), default=VerificationPurpose.LOGIN)

    #: scrypt, salted, same encoding as a password. Never the code itself.
    otp_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    #: Wrong guesses so far. Compared against OTP_MAX_ATTEMPTS.
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    #: Set the moment a code is accepted. A consumed row can never be used
    #: again — this is what makes replay impossible, rather than deleting the
    #: row, which would lose the audit trail of when it was redeemed.
    consumed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )

    #: Set for login (the account is known); null for signup (it does not exist
    #: yet). SET NULL rather than CASCADE: deleting an account should not erase
    #: the record that a code was issued.
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, default=None
    )

    #: Best-effort caller address, for per-IP rate limiting. Not trusted for
    #: anything security-critical: behind a proxy it is whatever the proxy says.
    request_ip: Mapped[Optional[str]] = mapped_column(String(64), default=None)

    def is_live(self, now: datetime) -> bool:
        """Usable right now: not spent, not expired, not out of attempts."""
        from app.core.security import OTP_MAX_ATTEMPTS

        expires = self.expires_at
        if expires.tzinfo is None:  # stored naive UTC by SQLite
            from datetime import timezone

            expires = expires.replace(tzinfo=timezone.utc)
        return (
            self.consumed_at is None
            and self.attempts < OTP_MAX_ATTEMPTS
            and expires > now
        )
