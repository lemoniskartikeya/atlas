"""Sign in with Google, for a desktop app.

The flow is OAuth 2.0 authorization code + PKCE, with the loopback redirect
that Google documents for installed apps: the browser sends the user back to
``http://127.0.0.1:<backend port>/api/v1/auth/google/callback``, which is this
process. No client secret is needed, and none is stored.

**Atlas cannot supply the credential.** A Google OAuth client ID belongs to
whoever runs the app — it is created in that person's own Google Cloud project
and cannot be shipped in a binary that anyone can read. So the client ID is
configuration, set in Settings, and every one of these calls says plainly when
it is missing rather than failing with something cryptic.

The access token is exchanged over TLS directly with Google and then spent
immediately on the userinfo endpoint, also over TLS. That is why no JWT
signature verification appears here: nothing untrusted is ever parsed. Taking
the ID token out of a redirect and trusting its claims *would* require
verification — this flow deliberately avoids that shape.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("atlas.google")

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = ["openid", "email", "profile"]

#: A pending sign-in is short-lived by design — long enough to pick an account,
#: not long enough for an abandoned attempt to sit around being replayable.
FLOW_TTL_SECONDS = 300


class GoogleAuthError(RuntimeError):
    """Written for a person: shown directly on the sign-in screen."""


@dataclass
class PendingFlow:
    state: str
    verifier: str
    created_at: float
    #: Set once Google has answered, then collected by the waiting UI.
    token: Optional[str] = None
    error: Optional[str] = None
    username: Optional[str] = None

    @property
    def expired(self) -> bool:
        return (time.time() - self.created_at) > FLOW_TTL_SECONDS


class GoogleFlowStore:
    """In-memory, single-process, deliberately not persisted.

    A pending sign-in is worthless after a restart and keeping one on disk
    would only widen the window in which a code could be replayed.
    """

    def __init__(self) -> None:
        self._flows: dict[str, PendingFlow] = {}

    def start(self) -> PendingFlow:
        self._prune()
        flow = PendingFlow(
            state=secrets.token_urlsafe(24),
            verifier=_pkce_verifier(),
            created_at=time.time(),
        )
        self._flows[flow.state] = flow
        return flow

    def get(self, state: str) -> Optional[PendingFlow]:
        flow = self._flows.get(state)
        if flow and flow.expired:
            self._flows.pop(state, None)
            return None
        return flow

    def pop(self, state: str) -> Optional[PendingFlow]:
        flow = self.get(state)
        if flow:
            self._flows.pop(state, None)
        return flow

    def _prune(self) -> None:
        for state in [s for s, f in self._flows.items() if f.expired]:
            self._flows.pop(state, None)


#: One store per process. The desktop app is one process serving one person.
FLOWS = GoogleFlowStore()


def _pkce_verifier() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def redirect_uri() -> str:
    settings = get_settings()
    return f"http://127.0.0.1:{settings.port}/api/v1/auth/google/callback"


def is_configured() -> bool:
    return bool((get_settings().google_client_id or "").strip())


def authorize_url(flow: PendingFlow) -> str:
    """The URL to open in the user's real browser — never in a webview.

    Google blocks its sign-in page inside embedded webviews, and rightly so:
    the user cannot see the address bar to check who is asking for their
    password. The desktop shell opens this externally.
    """
    settings = get_settings()
    if not is_configured():
        raise GoogleAuthError(
            "No Google client ID is configured. Add one in Settings → Account to "
            "enable Google sign-in."
        )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": flow.state,
        "code_challenge": _pkce_challenge(flow.verifier),
        "code_challenge_method": "S256",
        # Ask every time rather than silently reusing whoever is signed in —
        # a shared machine should not sign you in as someone else.
        "prompt": "select_account",
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code(code: str, verifier: str) -> dict:
    """Swap the one-time code for tokens, then read who the user is."""
    import httpx

    settings = get_settings()
    payload = {
        "code": code,
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }
    # Google issues a "secret" even for installed apps. It isn't one — it ships
    # inside the client — but the token endpoint wants it when the client was
    # registered as a Web application, so send it when present.
    if settings.google_client_secret:
        payload["client_secret"] = settings.google_client_secret

    try:
        token_res = httpx.post(TOKEN_ENDPOINT, data=payload, timeout=20.0)
    except httpx.HTTPError as exc:
        raise GoogleAuthError(f"Couldn't reach Google: {exc}") from exc

    if token_res.status_code >= 400:
        raise GoogleAuthError(_explain_token_error(token_res))

    access_token = token_res.json().get("access_token")
    if not access_token:
        raise GoogleAuthError("Google's response contained no access token.")

    try:
        info_res = httpx.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20.0,
        )
        info_res.raise_for_status()
    except httpx.HTTPError as exc:
        raise GoogleAuthError(f"Couldn't read your Google profile: {exc}") from exc

    profile = info_res.json()
    if not profile.get("sub"):
        raise GoogleAuthError("Google's profile response had no account id.")
    return profile


def _explain_token_error(res) -> str:
    """Turn Google's error codes into something a person can act on."""
    try:
        body = res.json()
    except Exception:
        return f"Google rejected the sign-in ({res.status_code})."

    code = body.get("error", "")
    detail = body.get("error_description") or code or "unknown error"
    hints = {
        "redirect_uri_mismatch": (
            f"Add {redirect_uri()} to your OAuth client's authorised redirect URIs "
            "in the Google Cloud console."
        ),
        "invalid_client": "Check the client ID (and secret, if your client needs one).",
        "invalid_grant": "That sign-in expired or was already used. Try again.",
    }
    hint = hints.get(code)
    return f"Google rejected the sign-in: {detail}." + (f" {hint}" if hint else "")


def suggest_username(profile: dict, taken: set[str]) -> str:
    """Derive a username from the Google account, without colliding.

    Only used when creating an account; an existing one keeps whatever
    username it already has.
    """
    email = (profile.get("email") or "").strip()
    base = "".join(c for c in email.split("@")[0].lower() if c.isalnum() or c in "._-")
    base = (base or "user")[:30].strip("._-") or "user"
    if base not in taken:
        return base
    for n in range(2, 500):
        candidate = f"{base}{n}"
        if candidate not in taken:
            return candidate
    return f"{base}{secrets.token_hex(3)}"
