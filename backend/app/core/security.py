"""Password hashing, password policy, and session-token primitives.

Everything here is standard library on purpose. Atlas ships as a local-first
desktop app, so the install must stay small and must not depend on a native
wheel building on the user's machine. `hashlib.scrypt` is a memory-hard KDF
that ships with CPython and is a legitimate choice for password storage.

Sessions are opaque random tokens, not JWTs: only the *hash* of a token is
stored, so a leaked database yields nothing usable, and logging out can
genuinely revoke a session (a signed stateless token cannot be).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

# scrypt work factors. n is the dominant cost knob; 2**14 keeps a login well
# under ~100ms on ordinary hardware while making offline cracking expensive.
_N = 2**14
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16

PASSWORD_MIN_LENGTH = 8
SESSION_TTL = timedelta(days=30)

_SPECIAL = re.compile(r"[^A-Za-z0-9]")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# --------------------------------------------------------------------- policy
def password_problems(password: str) -> list[str]:
    """Return every rule the password fails, so the UI can show them all at once.

    Policy: at least 8 characters, and it must contain a letter, a digit, and a
    special character.
    """
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Must be at least {PASSWORD_MIN_LENGTH} characters.")
    if not any(c.isalpha() for c in password):
        problems.append("Must include a letter.")
    if not any(c.isdigit() for c in password):
        problems.append("Must include a number.")
    if not _SPECIAL.search(password):
        problems.append("Must include a special character.")
    return problems


# -------------------------------------------------------------------- hashing
def hash_password(password: str) -> str:
    """Encode as `scrypt$n$r$p$salt$hash` so parameters can change over time."""
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verify. Any malformed stored value fails closed."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_unb64(hash_b64)),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, _unb64(hash_b64))


# -------------------------------------------------------------------- sessions
def new_session_token() -> str:
    """A high-entropy bearer token. Shown to the client exactly once."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are already high-entropy, so a fast digest is the right tool —
    scrypt here would only slow every authenticated request down."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)) + SESSION_TTL
