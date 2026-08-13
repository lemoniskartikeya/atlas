"""Sign in with Google (OAuth 2.0 + PKCE, loopback redirect).

The browser is where sign-in happens — the desktop shell opens the real one, so
the user can see the address bar and check who is asking for their password.
Google redirects back to this process, which finishes the exchange and parks a
ready Atlas session for the waiting UI to collect.

    UI ──POST /start──▶ authorize_url ──▶ system browser ──▶ Google
                                                              │
    UI ◀──GET /result── (token) ◀── GET /callback ◀───────────┘
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.deps import auth_service
from app.core.config import get_settings
from app.core.secrets_store import set_secret
from app.schemas.auth import AuthResponse
from app.services.auth_service import AuthError, AuthService
from app.services.google_auth import (
    FLOWS,
    GoogleAuthError,
    authorize_url,
    exchange_code,
    is_configured,
    redirect_uri,
)

router = APIRouter(prefix="/auth/google", tags=["auth"])


class GoogleConfigStatus(BaseModel):
    configured: bool
    #: Must be registered verbatim in the Google Cloud console, so it is shown
    #: in the UI for copying rather than left for the user to reconstruct.
    redirect_uri: str
    client_id_hint: str | None = None


class GoogleConfigRequest(BaseModel):
    client_id: str = Field(min_length=8, max_length=300)
    #: Only needed when the OAuth client was registered as a "Web application".
    client_secret: str | None = Field(default=None, max_length=300)


class StartResponse(BaseModel):
    authorize_url: str
    state: str


class ResultResponse(BaseModel):
    status: str  # "pending" | "ready" | "error"
    detail: str | None = None
    token: str | None = None
    username: str | None = None


@router.get("/status", response_model=GoogleConfigStatus)
def google_status():
    settings = get_settings()
    client_id = (settings.google_client_id or "").strip()
    return GoogleConfigStatus(
        configured=is_configured(),
        redirect_uri=redirect_uri(),
        # The client id isn't secret, but showing all of it is noise.
        client_id_hint=f"{client_id[:14]}…" if client_id else None,
    )


@router.put("/config", response_model=GoogleConfigStatus)
def set_google_config(payload: GoogleConfigRequest):
    """Store the OAuth client this machine should use.

    Atlas cannot ship a client ID — it belongs to whoever runs the app, and a
    binary anyone can read is not a place to keep one.
    """
    set_secret("ATLAS_GOOGLE_CLIENT_ID", payload.client_id.strip())
    set_secret("ATLAS_GOOGLE_CLIENT_SECRET", (payload.client_secret or "").strip() or None)
    return google_status()


@router.post("/start", response_model=StartResponse)
def start():
    try:
        flow = FLOWS.start()
        return StartResponse(authorize_url=authorize_url(flow), state=flow.state)
    except GoogleAuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/callback", response_class=HTMLResponse)
def callback(
    state: str = "",
    code: str = "",
    error: str = "",
    svc: AuthService = Depends(auth_service),
):
    """Where Google sends the browser back. Returns a page, not JSON.

    A human is looking at this, so it says what happened and that they can
    close the tab. The token goes to the app through /result, never into the
    URL bar or the page.
    """
    flow = FLOWS.get(state)
    if flow is None:
        return _page("Sign-in expired", "That sign-in took too long. Try again from Atlas.", ok=False)

    if error:
        flow.error = f"Google reported: {error}"
        return _page("Sign-in cancelled", flow.error, ok=False)
    if not code:
        flow.error = "Google didn't return an authorisation code."
        return _page("Sign-in failed", flow.error, ok=False)

    try:
        profile = exchange_code(code, flow.verifier)
        user = svc.sign_in_with_google(profile)
        flow.token = svc.start_session(user)
        flow.username = user.username
    except (GoogleAuthError, AuthError) as exc:
        flow.error = str(exc)
        return _page("Sign-in failed", flow.error, ok=False)

    return _page("You're signed in", "You can close this tab and go back to Atlas.", ok=True)


@router.get("/result", response_model=ResultResponse)
def result(state: str):
    """Collect the finished sign-in. One-shot: the flow is consumed on success."""
    flow = FLOWS.get(state)
    if flow is None:
        return ResultResponse(status="error", detail="That sign-in expired. Try again.")
    if flow.error:
        FLOWS.pop(state)
        return ResultResponse(status="error", detail=flow.error)
    if flow.token:
        FLOWS.pop(state)
        return ResultResponse(status="ready", token=flow.token, username=flow.username)
    return ResultResponse(status="pending")


def _page(title: str, message: str, *, ok: bool) -> HTMLResponse:
    """A self-contained page — this renders in a browser with no access to Atlas."""
    accent = "#6E8F63" if ok else "#B4544A"
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title} · Atlas</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin:0; min-height:100vh; display:grid; place-items:center;
         background:#FBF8F4; color:#2B2622;
         font:16px/1.5 ui-sans-serif, system-ui, -apple-system, sans-serif; }}
  @media (prefers-color-scheme: dark) {{ body {{ background:#14110E; color:#EDE6DE; }} }}
  .card {{ max-width:26rem; padding:2rem; text-align:center; }}
  .dot {{ width:.6rem; height:.6rem; border-radius:50%; background:{accent};
          display:inline-block; margin-right:.5rem; }}
  h1 {{ font:600 1.25rem/1.3 ui-serif, Georgia, serif; margin:0 0 .5rem; }}
  p {{ margin:0; opacity:.7; font-size:.9rem; }}
</style></head>
<body><div class="card"><h1><span class="dot"></span>{title}</h1><p>{message}</p></div></body>
</html>""",
        status_code=200,
    )
