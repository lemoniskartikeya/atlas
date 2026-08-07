"""Account registration, sign-in, sessions, and the password policy."""
from __future__ import annotations

import pytest

from app.core.security import hash_password, password_problems, verify_password

GOOD = "Atlas#2026"


def _register(client, username="kartikeya", password=GOOD, **extra):
    return client.post(
        "/api/v1/auth/register", json={"username": username, "password": password, **extra}
    )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------- hashing
def test_password_hash_roundtrip():
    encoded = hash_password(GOOD)
    assert encoded.startswith("scrypt$")
    assert GOOD not in encoded  # never stored in the clear
    assert verify_password(GOOD, encoded)
    assert not verify_password(GOOD + "x", encoded)


def test_hash_is_salted():
    """Two users with the same password must not share a stored hash."""
    assert hash_password(GOOD) != hash_password(GOOD)


def test_malformed_hash_fails_closed():
    for junk in ("", "nonsense", "scrypt$bad", "md5$1$1$1$aa$bb"):
        assert not verify_password(GOOD, junk)


# -------------------------------------------------------------------- policy
@pytest.mark.parametrize(
    "password,expected_fragment",
    [
        ("Ab1!", "at least 8"),
        ("nodigitshere!", "number"),
        ("nospecial12345", "special"),
        ("12345678!", "letter"),
    ],
)
def test_policy_rejects(password, expected_fragment):
    problems = " ".join(password_problems(password)).lower()
    assert expected_fragment in problems


def test_policy_accepts_compliant_password():
    assert password_problems(GOOD) == []


def test_policy_reports_every_failure_at_once():
    # Short, no digit, no special — the UI should be able to show all three.
    assert len(password_problems("abc")) == 3


# ------------------------------------------------------------------ register
def test_register_returns_token_and_user(client):
    res = _register(client)
    assert res.status_code == 201
    body = res.json()
    assert body["token"]
    assert body["user"]["username"] == "kartikeya"
    assert "password" not in body["user"] and "password_hash" not in body["user"]


def test_register_rejects_weak_password_with_readable_message(client):
    res = _register(client, password="weak")
    assert res.status_code == 400
    assert isinstance(res.json()["detail"], str)  # not a pydantic error array


def test_register_rejects_duplicate_username(client):
    _register(client)
    res = _register(client, password="Other#2026")
    assert res.status_code == 400
    assert "taken" in res.json()["detail"].lower()


def test_username_is_normalised_to_lowercase(client):
    _register(client, username="Kartikeya")
    assert client.post(
        "/api/v1/auth/login", json={"identifier": "KARTIKEYA", "password": GOOD}
    ).status_code == 200


def test_register_rejects_bad_email(client):
    assert _register(client, email="not-an-email").status_code == 422


# --------------------------------------------------------------------- login
def test_login_with_username_and_with_email(client):
    _register(client, email="k@example.com")
    for ident in ("kartikeya", "k@example.com"):
        res = client.post("/api/v1/auth/login", json={"identifier": ident, "password": GOOD})
        assert res.status_code == 200, ident


def test_login_failure_does_not_reveal_whether_user_exists(client):
    _register(client)
    wrong_pw = client.post(
        "/api/v1/auth/login", json={"identifier": "kartikeya", "password": "Wrong#2026"}
    )
    no_user = client.post(
        "/api/v1/auth/login", json={"identifier": "ghost", "password": "Wrong#2026"}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["detail"] == no_user.json()["detail"]


# ------------------------------------------------------------------ sessions
def test_me_requires_a_valid_token(client):
    token = _register(client).json()["token"]
    assert client.get("/api/v1/auth/me", headers=_auth(token)).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=_auth("bogus")).status_code == 401


def test_logout_revokes_the_token(client):
    token = _register(client).json()["token"]
    assert client.post("/api/v1/auth/logout", headers=_auth(token)).status_code == 204
    assert client.get("/api/v1/auth/me", headers=_auth(token)).status_code == 401


def test_status_drives_first_run_setup(client):
    before = client.get("/api/v1/auth/status").json()
    assert before["has_accounts"] is False and before["authenticated"] is False
    assert before["policy"]["min_length"] == 8

    token = _register(client).json()["token"]
    after = client.get("/api/v1/auth/status", headers=_auth(token)).json()
    assert after["has_accounts"] is True and after["authenticated"] is True
    assert after["user"]["username"] == "kartikeya"


def test_change_password_invalidates_existing_sessions(client):
    token = _register(client).json()["token"]
    res = client.post(
        "/api/v1/auth/change-password",
        headers=_auth(token),
        json={"current_password": GOOD, "new_password": "Newpass#99"},
    )
    assert res.status_code == 204
    # The token used to make the change is revoked along with every other one.
    assert client.get("/api/v1/auth/me", headers=_auth(token)).status_code == 401
    assert client.post(
        "/api/v1/auth/login", json={"identifier": "kartikeya", "password": "Newpass#99"}
    ).status_code == 200


def test_change_password_enforces_policy(client):
    token = _register(client).json()["token"]
    res = client.post(
        "/api/v1/auth/change-password",
        headers=_auth(token),
        json={"current_password": GOOD, "new_password": "weak"},
    )
    assert res.status_code == 400
