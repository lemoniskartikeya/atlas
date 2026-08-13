"""Sign in with Google.

The live round-trip needs a real Google OAuth client, which belongs to whoever
runs Atlas and cannot be shipped — so Google itself is stubbed at the one seam
that talks to it (`exchange_code`). Everything on this side of that seam is
exercised for real: PKCE, state handling, expiry, account matching, and the
rules that decide whether an existing account gets linked.
"""
from __future__ import annotations

import time

import pytest

from app.services import google_auth
from app.services.google_auth import (
    FLOWS,
    GoogleAuthError,
    _pkce_challenge,
    authorize_url,
    suggest_username,
)

BASE = "/api/v1"

PROFILE = {
    "sub": "108154',",
    "email": "ada@example.com",
    "email_verified": True,
    "name": "Ada Lovelace",
}


@pytest.fixture()
def configured(monkeypatch):
    """A client id is present, so the flow can start."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_client_id", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(get_settings(), "google_client_secret", None)
    return get_settings()


def _stub_google(monkeypatch, profile=None, error=None):
    def fake_exchange(code, verifier):
        if error:
            raise GoogleAuthError(error)
        return profile if profile is not None else PROFILE

    monkeypatch.setattr("app.api.v1.google.exchange_code", fake_exchange)


# ------------------------------------------------------------------- configuration
def test_status_reports_unconfigured_and_shows_the_redirect_to_register(anon_client):
    body = anon_client.get(f"{BASE}/auth/google/status").json()
    assert body["configured"] is False
    # The URI has to be registered verbatim in the Cloud console, so it is
    # handed to the user rather than left for them to reconstruct.
    assert body["redirect_uri"].startswith("http://127.0.0.1:")
    assert body["redirect_uri"].endswith("/api/v1/auth/google/callback")


def test_starting_without_a_client_id_says_what_is_missing(anon_client):
    res = anon_client.post(f"{BASE}/auth/google/start")
    assert res.status_code == 400
    assert "client ID" in res.json()["detail"]


# ------------------------------------------------------------------------- PKCE
def test_authorize_url_carries_pkce_and_asks_which_account(configured):
    flow = FLOWS.start()
    url = authorize_url(flow)

    assert url.startswith("https://accounts.google.com/")
    assert "code_challenge_method=S256" in url
    # The challenge is the hash, never the verifier itself.
    assert _pkce_challenge(flow.verifier) in url
    assert flow.verifier not in url
    assert "prompt=select_account" in url
    assert f"state={flow.state}" in url


def test_each_start_gets_its_own_state_and_verifier(configured):
    a, b = FLOWS.start(), FLOWS.start()
    assert a.state != b.state
    assert a.verifier != b.verifier


def test_an_expired_flow_is_forgotten(configured, monkeypatch):
    flow = FLOWS.start()
    monkeypatch.setattr(flow, "created_at", time.time() - google_auth.FLOW_TTL_SECONDS - 1)
    assert FLOWS.get(flow.state) is None


# -------------------------------------------------------------------- the round trip
def test_a_successful_sign_in_creates_an_account_and_hands_back_a_session(
    anon_client, configured, monkeypatch
):
    _stub_google(monkeypatch)
    state = anon_client.post(f"{BASE}/auth/google/start").json()["state"]

    page = anon_client.get(f"{BASE}/auth/google/callback", params={"state": state, "code": "abc"})
    assert page.status_code == 200
    assert "signed in" in page.text.lower()
    # The token never travels through the browser.
    assert "token" not in page.text.lower()

    result = anon_client.get(f"{BASE}/auth/google/result", params={"state": state}).json()
    assert result["status"] == "ready"
    assert result["token"]
    assert result["username"] == "ada"

    # And it is a real Atlas session.
    me = anon_client.get(
        f"{BASE}/auth/me", headers={"Authorization": f"Bearer {result['token']}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == "ada"


def test_the_result_is_collected_once(anon_client, configured, monkeypatch):
    """A token left sitting where it can be fetched twice is a token to steal."""
    _stub_google(monkeypatch)
    state = anon_client.post(f"{BASE}/auth/google/start").json()["state"]
    anon_client.get(f"{BASE}/auth/google/callback", params={"state": state, "code": "abc"})

    assert anon_client.get(f"{BASE}/auth/google/result", params={"state": state}).json()["status"] == "ready"
    second = anon_client.get(f"{BASE}/auth/google/result", params={"state": state}).json()
    assert second["status"] == "error"


def test_result_is_pending_until_google_answers(anon_client, configured):
    state = anon_client.post(f"{BASE}/auth/google/start").json()["state"]
    body = anon_client.get(f"{BASE}/auth/google/result", params={"state": state}).json()
    assert body["status"] == "pending" and body["token"] is None


def test_an_unknown_state_is_refused(anon_client, configured, monkeypatch):
    """The callback must not act on a state it never issued."""
    _stub_google(monkeypatch)
    page = anon_client.get(
        f"{BASE}/auth/google/callback", params={"state": "forged", "code": "abc"}
    )
    assert "expired" in page.text.lower()


def test_a_cancelled_consent_screen_is_reported_not_swallowed(
    anon_client, configured, monkeypatch
):
    state = anon_client.post(f"{BASE}/auth/google/start").json()["state"]
    anon_client.get(
        f"{BASE}/auth/google/callback", params={"state": state, "error": "access_denied"}
    )
    body = anon_client.get(f"{BASE}/auth/google/result", params={"state": state}).json()
    assert body["status"] == "error" and "access_denied" in body["detail"]


def test_googles_own_failure_reaches_the_user(anon_client, configured, monkeypatch):
    _stub_google(monkeypatch, error="Google rejected the sign-in: redirect_uri_mismatch.")
    state = anon_client.post(f"{BASE}/auth/google/start").json()["state"]
    anon_client.get(f"{BASE}/auth/google/callback", params={"state": state, "code": "abc"})

    body = anon_client.get(f"{BASE}/auth/google/result", params={"state": state}).json()
    assert body["status"] == "error"
    assert "redirect_uri_mismatch" in body["detail"]


# ------------------------------------------------------------------ account matching
def test_signing_in_twice_reuses_the_same_account(anon_client, configured, monkeypatch):
    _stub_google(monkeypatch)
    names = set()
    for _ in range(2):
        state = anon_client.post(f"{BASE}/auth/google/start").json()["state"]
        anon_client.get(f"{BASE}/auth/google/callback", params={"state": state, "code": "abc"})
        names.add(anon_client.get(f"{BASE}/auth/google/result", params={"state": state}).json()["username"])
    assert names == {"ada"}


def test_a_verified_address_links_to_an_existing_password_account(
    anon_client, configured, monkeypatch
):
    anon_client.post(
        f"{BASE}/auth/register",
        json={"username": "ada", "password": "Passw0rd!", "email": "ada@example.com"},
    )
    _stub_google(monkeypatch)

    state = anon_client.post(f"{BASE}/auth/google/start").json()["state"]
    anon_client.get(f"{BASE}/auth/google/callback", params={"state": state, "code": "abc"})
    body = anon_client.get(f"{BASE}/auth/google/result", params={"state": state}).json()

    # Linked, not duplicated — same account, same username.
    assert body["status"] == "ready"
    assert body["username"] == "ada"


def test_an_unverified_address_never_takes_over_an_account(
    anon_client, configured, monkeypatch
):
    """Otherwise anyone who can claim your address in Google adopts your vault."""
    anon_client.post(
        f"{BASE}/auth/register",
        json={"username": "ada", "password": "Passw0rd!", "email": "ada@example.com"},
    )
    _stub_google(monkeypatch, profile={**PROFILE, "email_verified": False})

    state = anon_client.post(f"{BASE}/auth/google/start").json()["state"]
    anon_client.get(f"{BASE}/auth/google/callback", params={"state": state, "code": "abc"})
    body = anon_client.get(f"{BASE}/auth/google/result", params={"state": state}).json()

    assert body["status"] == "ready"
    assert body["username"] != "ada", "an unverified address linked to an existing account"


def test_a_google_only_account_cannot_be_signed_into_with_a_blank_password(
    anon_client, configured, monkeypatch
):
    """The stored hash is empty; nothing may compare equal to it."""
    _stub_google(monkeypatch)
    state = anon_client.post(f"{BASE}/auth/google/start").json()["state"]
    anon_client.get(f"{BASE}/auth/google/callback", params={"state": state, "code": "abc"})

    for attempt in ("", " ", "Passw0rd!"):
        res = anon_client.post(
            f"{BASE}/auth/login", json={"identifier": "ada", "password": attempt}
        )
        # 401 from the empty-hash guard, or 422 when the schema rejects the
        # password outright. Either is a refusal; what matters is that no
        # session comes back.
        assert res.status_code in (401, 422), f"blank-hash account accepted {attempt!r}"
        assert "token" not in res.json()


# --------------------------------------------------------------------- usernames
@pytest.mark.parametrize(
    "email,taken,expected",
    [
        ("ada@example.com", set(), "ada"),
        ("ada@example.com", {"ada"}, "ada2"),
        ("ada.lovelace@example.com", set(), "ada.lovelace"),
        ("!!!@example.com", set(), "user"),
        ("", set(), "user"),
    ],
)
def test_usernames_are_derived_without_collisions(email, taken, expected):
    assert suggest_username({"email": email}, taken) == expected
