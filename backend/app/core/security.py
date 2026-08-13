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


# ------------------------------------------------------------------ email OTP
OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=10)
#: Wrong guesses allowed against one code before it is burned.
OTP_MAX_ATTEMPTS = 5


def new_otp() -> str:
    """A cryptographically secure 6-digit code.

    `secrets.randbelow` over the whole range, not six independent digits —
    the latter is equivalent here but invites an implementation that reaches
    for `random`. Zero-padded, so "004215" is a valid code and the space is a
    full 10**6.
    """
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_otp(otp: str) -> str:
    """Store the code the same way a password is stored: scrypt, salted.

    A six-digit code has only 10**6 possibilities, so a fast digest (what we
    use for session tokens) would be trivially reversible from a stolen
    database — a rainbow table for the entire keyspace fits on a phone. scrypt
    at these parameters makes enumerating the space cost tens of hours, by
    which time the code has expired many times over. The per-record salt means
    one table cannot cover every row.

    The cost is one hash per verification attempt, and attempts are capped.
    """
    return hash_password(otp)


def verify_otp(otp: str, encoded: str) -> bool:
    """Constant-time compare. A malformed or blank stored hash fails closed."""
    if not encoded:
        return False
    return verify_password(otp, encoded)


def otp_expiry(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)) + OTP_TTL


def normalize_email(email: str) -> str:
    """Trim and lowercase — the form every lookup and rate-limit key uses.

    Applied at the single point where email enters the system so that
    " Ada@Example.COM " and "ada@example.com" can never become two accounts,
    two rate-limit buckets, or a code issued to one and checked against the
    other.
    """
    return (email or "").strip().lower()
