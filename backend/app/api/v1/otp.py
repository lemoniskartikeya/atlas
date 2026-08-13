"""Email verification-code endpoints.

Thin: validation and HTTP translation only. Every rule about who may receive a
code, how long it lives, and what a guess costs lives in ``OtpService``.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.email_verification import VerificationPurpose
from app.schemas.auth import AuthResponse, UserRead
from app.services.email_service import is_configured as email_configured
from app.services.otp_service import OtpError, OtpService

router = APIRouter(prefix="/auth", tags=["auth"])

# Same shape check the rest of the auth surface uses. Deliberately not
# pydantic's EmailStr, which would pull in `email-validator` — a dependency the
# packaged desktop build does not need for a format check this simple.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CODE_RE = re.compile(r"^\d{6}$")


class _EmailBody(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    purpose: str = Field(default=VerificationPurpose.LOGIN)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        cleaned = (v or "").strip().lower()
        if not _EMAIL_RE.match(cleaned):
            raise ValueError("Enter a valid email address.")
        return cleaned

    @field_validator("purpose")
    @classmethod
    def _known_purpose(cls, v: str) -> str:
        cleaned = (v or "").strip().lower()
        if cleaned not in VerificationPurpose.ALL:
            raise ValueError("purpose must be 'login' or 'signup'.")
        return cleaned


class SendOtpRequest(_EmailBody):
    pass


class VerifyOtpRequest(_EmailBody):
    code: str = Field(min_length=1, max_length=12)

    @field_validator("code")
    @classmethod
    def _six_digits(cls, v: str) -> str:
        # Strip the spaces and dashes people paste in from an email client.
        cleaned = re.sub(r"[\s-]", "", v or "")
        if not _CODE_RE.match(cleaned):
            raise ValueError("Enter the 6-digit code.")
        return cleaned


class SendOtpResponse(BaseModel):
    email: str
    purpose: str
    detail: str
    expires_in_seconds: int
    resend_in_seconds: int
    #: Development only, and only when explicitly enabled there. Never set on a
    #: deployed instance — see `Settings.otp_echo_allowed`.
    dev_code: Optional[str] = None


class EmailStatus(BaseModel):
    """Lets the sign-in screen hide the email option when it cannot work."""

    email_configured: bool


def _client_ip(request: Request) -> Optional[str]:
    """Best-effort caller address for rate limiting.

    Atlas binds to loopback and is spoken to by its own desktop shell, so this
    is normally 127.0.0.1 and the per-IP cap is a backstop rather than the main
    defence. `X-Forwarded-For` is honoured for anyone putting this behind a
    proxy, and is not trusted for anything beyond bucketing.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client else None


@router.get("/email-status", response_model=EmailStatus)
def email_status():
    return EmailStatus(email_configured=email_configured())


@router.post("/send-otp", response_model=SendOtpResponse)
def send_otp(
    payload: SendOtpRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    try:
        outcome = OtpService(session).send(
            payload.email, payload.purpose, request_ip=_client_ip(request)
        )
    except OtpError as exc:
        if exc.retry_after:
            # Give the client something to count down from rather than making
            # it guess when to try again.
            response.headers["Retry-After"] = str(exc.retry_after)
            raise HTTPException(
                status_code=exc.status_code,
                detail=exc.message,
                headers={"Retry-After": str(exc.retry_after)},
            ) from exc
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return SendOtpResponse(
        email=outcome.email,
        purpose=outcome.purpose,
        detail=outcome.detail,
        expires_in_seconds=outcome.expires_in_seconds,
        resend_in_seconds=outcome.resend_in_seconds,
        dev_code=outcome.dev_code,
    )


@router.post("/verify-otp", response_model=AuthResponse)
def verify_otp(
    payload: VerifyOtpRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    """On success this returns the same `{token, user}` as every other sign-in."""
    try:
        token, user = OtpService(session).verify(
            payload.email, payload.code, payload.purpose, request_ip=_client_ip(request)
        )
    except OtpError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return AuthResponse(token=token, user=UserRead.model_validate(user))
