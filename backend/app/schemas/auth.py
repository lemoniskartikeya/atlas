"""Account API DTOs."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import PASSWORD_MIN_LENGTH

# Deliberately not pydantic's EmailStr: that pulls in `email-validator`, and
# email here is an optional convenience field on a local account, not an
# identity we ever send mail to. A shape check is the right amount of rigour.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    # No min_length here on purpose: every password rule is enforced in one
    # place (`password_problems`) so the client always gets one readable 400
    # instead of a pydantic 422 array for length and a 400 for everything else.
    password: str = Field(max_length=200)
    email: Optional[str] = Field(default=None, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        if not _EMAIL_RE.match(v.strip()):
            raise ValueError("Enter a valid email address.")
        return v.strip().lower()


class LoginRequest(BaseModel):
    """`identifier` accepts either the username or the email."""

    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(max_length=200)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime


class AuthResponse(BaseModel):
    token: str
    user: UserRead


class PasswordPolicy(BaseModel):
    min_length: int
    requires_number: bool = True
    requires_special: bool = True
    requires_letter: bool = True
    description: str


class AuthStatus(BaseModel):
    """Lets the UI decide between 'create the first account' and 'sign in'."""

    has_accounts: bool
    authenticated: bool
    user: Optional[UserRead] = None
    policy: PasswordPolicy
