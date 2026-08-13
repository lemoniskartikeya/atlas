"""Email verification codes: issuing them, and deciding whether a guess counts.

Every rule the feature promises lives here rather than in the router, so the
router stays a thin translation to HTTP and the rules can be tested without one.

The shape of the flow:

* **Login** — the address must already have an account. An unknown address is
  refused and no mail is sent, so Atlas is never a way to send mail to
  arbitrary strangers.
* **Signup** — the address must *not* have an account. The account is created
  only once a code sent to that mailbox comes back, which is what makes
  "verified" mean something.

A successful verification always ends the same way every other sign-in does:
``AuthService.start_session``. There is one session mechanism in Atlas, and
this is not a second one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import (
    OTP_MAX_ATTEMPTS,
    OTP_TTL,
    hash_otp,
    new_otp,
    normalize_email,
    otp_expiry,
    verify_otp,
)
from app.models.email_verification import EmailVerification, VerificationPurpose
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.email_service import (
    EmailNotConfigured,
    EmailSendError,
    send_otp,
)
from app.services.google_auth import suggest_username

log = get_logger("atlas.otp")

#: Deliberately vague, and identical for "no account" and "already registered",
#: for deployments that turn `otp_neutral_responses` on.
NEUTRAL = "If that address can receive a code, one is on its way."


class OtpError(Exception):
    """Something the caller is allowed to see a reason for."""

    def __init__(self, message: str, *, status_code: int = 400, retry_after: int = 0):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        #: Seconds until a retry could succeed; surfaced as Retry-After.
        self.retry_after = retry_after


@dataclass
class SendOutcome:
    email: str
    purpose: str
    expires_in_seconds: int
    resend_in_seconds: int
    detail: str
    #: Development only. Always None unless `otp_echo_allowed()`.
    dev_code: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; every comparison here is in UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class OtpService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.auth = AuthService(session)

    # ------------------------------------------------------------------ send
    def send(
        self,
        raw_email: str,
        purpose: str,
        request_ip: Optional[str] = None,
    ) -> SendOutcome:
        settings = get_settings()
        email = normalize_email(raw_email)
        if purpose not in VerificationPurpose.ALL:
            raise OtpError("Unknown verification purpose.")

        existing = self.auth.by_email(email)

        # Who is allowed a code, and who is not. Refusing here is what stops
        # Atlas being used to mail codes to addresses nobody asked about.
        if purpose == VerificationPurpose.LOGIN and existing is None:
            log.info("otp.refused_unknown_account", extra={"email": email})
            if settings.otp_neutral_responses:
                return self._pretend(email, purpose)
            raise OtpError("No Atlas account uses that email address.", status_code=404)

        if purpose == VerificationPurpose.SIGNUP and existing is not None:
            log.info("otp.refused_existing_account", extra={"email": email})
            if settings.otp_neutral_responses:
                return self._pretend(email, purpose)
            raise OtpError(
                "That email already has an Atlas account — sign in instead.",
                status_code=409,
            )

        self._enforce_rate_limits(email, request_ip)

        # Any code already outstanding for this address is retired. Without
        # this, "resend" would leave several live codes for one mailbox, and
        # the attempt cap would apply per code rather than per address.
        self._retire_live_codes(email)

        code = new_otp()
        record = EmailVerification(
            email=email,
            purpose=purpose,
            otp_hash=hash_otp(code),
            expires_at=otp_expiry(),
            user_id=existing.id if existing else None,
            request_ip=request_ip,
        )
        self.session.add(record)
        # Committed before the send so a provider timeout cannot leave a
        # delivered code with no matching row to verify against.
        self.session.commit()

        minutes = int(OTP_TTL.total_seconds() // 60)
        try:
            send_otp(email, code, minutes)
        except EmailNotConfigured as exc:
            # The row is useless without a delivered code — drop it so it does
            # not sit in the way of the next attempt.
            self._discard(record)
            raise OtpError(str(exc), status_code=503) from exc
        except EmailSendError as exc:
            self._discard(record)
            raise OtpError(str(exc), status_code=502) from exc

        # `code` is never logged, in any branch, at any level.
        log.info("otp.sent", extra={"email": email, "purpose": purpose})

        return SendOutcome(
            email=email,
            purpose=purpose,
            expires_in_seconds=int(OTP_TTL.total_seconds()),
            resend_in_seconds=settings.otp_resend_cooldown_seconds,
            detail=f"We sent a 6-digit code to {email}. It expires in {minutes} minutes.",
            dev_code=code if settings.otp_echo_allowed() else None,
        )

    def _pretend(self, email: str, purpose: str) -> SendOutcome:
        """The neutral answer: same shape, same timing story, no mail sent."""
        settings = get_settings()
        return SendOutcome(
            email=email,
            purpose=purpose,
            expires_in_seconds=int(OTP_TTL.total_seconds()),
            resend_in_seconds=settings.otp_resend_cooldown_seconds,
            detail=NEUTRAL,
        )

    # ---------------------------------------------------------------- verify
    def verify(
        self,
        raw_email: str,
        code: str,
        purpose: str,
        request_ip: Optional[str] = None,
    ) -> tuple[str, User]:
        """Check a code and, if it holds up, return ``(session_token, user)``."""
        email = normalize_email(raw_email)
        code = (code or "").strip()
        now = _now()

        record = self._latest_for(email, purpose)
        if record is None:
            raise OtpError("Request a new code — that one is no longer valid.")

        if record.consumed_at is not None:
            # Replay. The row stays consumed; this is not a failed attempt
            # against a live code, it is a use of a spent one.
            log.info("otp.replay_rejected", extra={"email": email})
            raise OtpError("That code has already been used. Request a new one.")

        if _aware(record.expires_at) <= now:
            raise OtpError("That code has expired. Request a new one.")

        if record.attempts >= OTP_MAX_ATTEMPTS:
            raise OtpError(
                "Too many incorrect attempts. Request a new code.", status_code=429
            )

        if not verify_otp(code, record.otp_hash):
            # Count the failure first and commit it, so a client that hangs up
            # mid-request has still spent its attempt.
            record.attempts += 1
            self.session.commit()
            remaining = max(0, OTP_MAX_ATTEMPTS - record.attempts)
            if remaining == 0:
                raise OtpError(
                    "Too many incorrect attempts. Request a new code.", status_code=429
                )
            raise OtpError(
                f"That code isn't right. {remaining} "
                f"{'attempt' if remaining == 1 else 'attempts'} left."
            )

        # Correct. Burn it before anything else can fail, so no path exists in
        # which a code is honoured twice.
        record.consumed_at = now
        self.session.flush()

        user = self._resolve_account(record, email, now)
        token = self.auth.start_session(user)
        self.session.commit()

        log.info(
            "otp.verified",
            extra={"email": email, "purpose": purpose, "username": user.username},
        )
        return token, user

    def _resolve_account(self, record: EmailVerification, email: str, now: datetime) -> User:
        """The account behind a verified address, creating it for signup."""
        user = self.auth.by_email(email)

        if user is None:
            if record.purpose != VerificationPurpose.SIGNUP:
                # The account existed when the code was issued and is gone now.
                raise OtpError("That account no longer exists.", status_code=404)
            taken = {u.username for u in self.auth.all_users()}
            first_account = self.auth.user_count() == 0
            user = User(
                username=suggest_username({"email": email}, taken),
                email=email,
                display_name=None,
                # No password: this account signs in by email. `authenticate`
                # refuses an empty hash outright, so this is not a way in.
                password_hash="",
                email_verified_at=now,
            )
            self.session.add(user)
            self.session.flush()
            if first_account:
                # Same courtesy the other sign-up paths get: a pre-accounts
                # vault is adopted by whoever registers first.
                self.auth.claim_orphan_vault(user)
        else:
            # Proving the mailbox is what "verified" means, so record it even
            # for an account that already existed.
            user.email_verified_at = now

        user.last_login_at = now
        return user

    # ----------------------------------------------------------- rate limits
    def _enforce_rate_limits(self, email: str, request_ip: Optional[str]) -> None:
        """Cooldown and hourly caps, counted from the rows themselves.

        No Redis and no in-memory counter: a desktop app restarts constantly,
        and an in-process tally would reset with it — which is precisely the
        window someone would use. The table is the source of truth.
        """
        settings = get_settings()
        now = _now()
        hour_ago = now - timedelta(hours=1)

        last = self.session.scalars(
            select(EmailVerification)
            .where(EmailVerification.email == email)
            .order_by(EmailVerification.created_at.desc())
            .limit(1)
        ).first()
        if last is not None:
            since = (now - _aware(last.created_at)).total_seconds()
            wait = settings.otp_resend_cooldown_seconds - int(since)
            if wait > 0:
                raise OtpError(
                    f"A code was just sent. Try again in {wait} seconds.",
                    status_code=429,
                    retry_after=wait,
                )

        recent_for_email = self._count_since(hour_ago, email=email)
        if recent_for_email >= settings.otp_per_email_per_hour:
            raise OtpError(
                "Too many codes requested for that address. Try again later.",
                status_code=429,
                retry_after=3600,
            )

        if request_ip:
            recent_for_ip = self._count_since(hour_ago, ip=request_ip)
            if recent_for_ip >= settings.otp_per_ip_per_hour:
                log.warning("otp.ip_rate_limited", extra={"ip": request_ip})
                raise OtpError(
                    "Too many codes requested from this device. Try again later.",
                    status_code=429,
                    retry_after=3600,
                )

    def _count_since(
        self, cutoff: datetime, *, email: Optional[str] = None, ip: Optional[str] = None
    ) -> int:
        stmt = select(func.count()).select_from(EmailVerification).where(
            EmailVerification.created_at >= cutoff
        )
        if email is not None:
            stmt = stmt.where(EmailVerification.email == email)
        if ip is not None:
            stmt = stmt.where(EmailVerification.request_ip == ip)
        return int(self.session.scalar(stmt) or 0)

    # --------------------------------------------------------------- helpers
    def _latest_for(self, email: str, purpose: str) -> Optional[EmailVerification]:
        return self.session.scalars(
            select(EmailVerification)
            .where(
                EmailVerification.email == email,
                EmailVerification.purpose == purpose,
            )
            .order_by(EmailVerification.created_at.desc())
            .limit(1)
        ).first()

    def _retire_live_codes(self, email: str) -> None:
        """Expire anything still outstanding for this address."""
        now = _now()
        for row in self.session.scalars(
            select(EmailVerification).where(
                EmailVerification.email == email,
                EmailVerification.consumed_at.is_(None),
            )
        ):
            if _aware(row.expires_at) > now:
                row.expires_at = now
        self.session.flush()

    def _discard(self, record: EmailVerification) -> None:
        self.session.delete(record)
        self.session.commit()
