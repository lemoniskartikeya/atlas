"""Email verification codes.

The email provider is stubbed at the single seam that talks to it
(`email_service.send`), and the code is captured from the message it would have
sent — so these exercise the real generation, hashing, expiry, attempt and
rate-limit logic rather than a mock of it. Nothing here reads the plaintext out
of the database, because it is never there.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import (
    OTP_MAX_ATTEMPTS,
    hash_otp,
    new_otp,
    normalize_email,
    verify_otp,
)
from app.models.email_verification import EmailVerification, VerificationPurpose

BASE = "/api/v1"
KNOWN = "tester@example.com"  # the account conftest registers
NEW = "newcomer@example.com"


@pytest.fixture(autouse=True)
def known_account(db_session):
    """conftest registers the test account with no email; this feature is
    entirely about email, so give it the address the tests treat as known."""
    from app.models.user import User

    user = db_session.scalars(select(User)).first()
    user.email = KNOWN
    db_session.commit()
    return user


@pytest.fixture()
def outbox(monkeypatch):
    """Capture what would have been emailed, without sending anything."""
    sent: list[dict] = []

    def fake_send(message):
        code = re.search(r"\b(\d{6})\b", message.text_body)
        sent.append(
            {
                "to": message.to,
                "subject": message.subject,
                "code": code.group(1) if code else None,
                "html": message.html_body,
                "text": message.text_body,
            }
        )

    monkeypatch.setattr("app.services.email_service.send", fake_send)
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test_key")
    monkeypatch.setattr(get_settings(), "email_from", "atlas@example.com")
    return sent


@pytest.fixture()
def relaxed(monkeypatch):
    """Remove the resend cooldown for tests that legitimately send twice."""
    monkeypatch.setattr(get_settings(), "otp_resend_cooldown_seconds", 0)


def _send(client, email=KNOWN, purpose="login"):
    return client.post(f"{BASE}/auth/send-otp", json={"email": email, "purpose": purpose})


def _verify(client, email, code, purpose="login"):
    return client.post(
        f"{BASE}/auth/verify-otp", json={"email": email, "code": code, "purpose": purpose}
    )


def _record(session, email):
    return session.scalars(
        select(EmailVerification)
        .where(EmailVerification.email == email)
        .order_by(EmailVerification.created_at.desc())
        .limit(1)
    ).first()


# ------------------------------------------------------------------ primitives
def test_generated_codes_are_six_digits_and_cover_the_whole_range():
    codes = {new_otp() for _ in range(400)}
    assert all(re.fullmatch(r"\d{6}", c) for c in codes)
    # Zero-padding is what makes "004215" reachable; without it the space is
    # smaller than it looks and low codes never appear.
    assert len({c[0] for c in codes}) > 1
    assert len(codes) > 300, "codes repeat far more than chance would explain"


def test_a_code_hash_is_salted_and_verifies_only_the_right_code():
    a, b = hash_otp("123456"), hash_otp("123456")
    assert a != b, "same code hashed twice must not collide — no salt?"
    assert verify_otp("123456", a)
    assert not verify_otp("123457", a)
    assert not verify_otp("123456", "")


@pytest.mark.parametrize(
    "raw,expected",
    [("  Ada@Example.COM ", "ada@example.com"), ("x@y.z", "x@y.z"), ("", "")],
)
def test_emails_normalize_before_anything_looks_at_them(raw, expected):
    assert normalize_email(raw) == expected


# ------------------------------------------------------------------- sending
def test_login_sends_a_code_to_a_known_account(client, outbox):
    res = _send(client)
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["email"] == KNOWN
    assert body["expires_in_seconds"] > 0
    assert body["dev_code"] is None, "a code must never come back by default"

    assert len(outbox) == 1
    assert outbox[0]["to"] == KNOWN
    assert outbox[0]["subject"] == "Your verification code"
    assert re.fullmatch(r"\d{6}", outbox[0]["code"])


def test_login_to_an_unknown_address_sends_nothing(client, outbox):
    """Atlas must not be a way to mail codes to strangers."""
    res = _send(client, email="nobody@example.com")
    assert res.status_code == 404
    assert outbox == []


def test_signup_to_an_existing_address_sends_nothing(client, outbox):
    res = _send(client, email=KNOWN, purpose="signup")
    assert res.status_code == 409
    assert outbox == []


def test_the_address_is_normalized_before_the_account_lookup(client, outbox):
    res = _send(client, email="  TESTER@Example.COM  ")
    assert res.status_code == 200
    assert outbox[0]["to"] == KNOWN


@pytest.mark.parametrize("bad", ["not-an-email", "a@b", "@example.com", "a b@c.com", ""])
def test_malformed_addresses_are_refused(client, outbox, bad):
    assert _send(client, email=bad).status_code == 422
    assert outbox == []


def test_the_plaintext_code_is_never_stored(client, outbox, db_session):
    _send(client)
    code = outbox[0]["code"]

    row = _record(db_session, KNOWN)
    assert row is not None
    assert code not in row.otp_hash
    assert verify_otp(code, row.otp_hash), "stored hash must match the code sent"
    # Nothing anywhere on the row leaks it.
    assert not any(code in str(v) for v in vars(row).values() if isinstance(v, str))


def test_the_email_says_what_it_needs_to(client, outbox):
    _send(client)
    message = outbox[0]
    code = message["code"]

    for part in (message["html"], message["text"]):
        assert code in part or code in part.replace(" ", "")
        assert "10 minutes" in part
    assert "not share" in message["text"].lower()
    assert "Atlas" in message["text"]
    assert message["html"].lstrip().startswith("<!doctype html")


# ----------------------------------------------------------------- verifying
def test_a_correct_code_signs_you_in(client, outbox):
    _send(client)
    res = _verify(client, KNOWN, outbox[0]["code"])
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["token"]
    assert body["user"]["email"] == KNOWN

    # It is a real session, indistinguishable from a password sign-in.
    me = client.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200


def test_a_wrong_code_is_refused_and_counts_against_you(client, outbox, db_session):
    _send(client)
    res = _verify(client, KNOWN, "000000")

    assert res.status_code == 400
    assert "isn't right" in res.json()["detail"]
    db_session.expire_all()
    assert _record(db_session, KNOWN).attempts == 1


def test_a_used_code_cannot_be_replayed(client, outbox):
    _send(client)
    code = outbox[0]["code"]
    assert _verify(client, KNOWN, code).status_code == 200

    again = _verify(client, KNOWN, code)
    assert again.status_code == 400
    assert "already been used" in again.json()["detail"]


def test_an_expired_code_is_refused(client, outbox, db_session):
    _send(client)
    row = _record(db_session, KNOWN)
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    res = _verify(client, KNOWN, outbox[0]["code"])
    assert res.status_code == 400
    assert "expired" in res.json()["detail"]


def test_attempts_are_capped_and_the_code_dies_with_them(client, outbox):
    _send(client)
    code = outbox[0]["code"]

    for _ in range(OTP_MAX_ATTEMPTS):
        assert _verify(client, KNOWN, "000000").status_code in (400, 429)

    # Even the genuine code is worthless now — the cap protects the address,
    # not just the individual guess.
    final = _verify(client, KNOWN, code)
    assert final.status_code == 429
    assert "Too many" in final.json()["detail"]


def test_a_code_is_not_valid_for_a_different_address(client, outbox, relaxed, db_session):
    """A code proves control of the mailbox it was sent to, nothing else."""
    from app.services.auth_service import AuthService

    AuthService(db_session).register("other", "Passw0rd!", email=NEW)
    _send(client, email=KNOWN)
    code_for_known = outbox[0]["code"]

    assert _verify(client, NEW, code_for_known).status_code == 400


def test_verifying_without_ever_requesting_is_refused(client, outbox):
    res = _verify(client, KNOWN, "123456")
    assert res.status_code == 400
    assert "no longer valid" in res.json()["detail"]


@pytest.mark.parametrize("bad", ["12345", "1234567", "abcdef", ""])
def test_malformed_codes_are_refused_before_any_lookup(client, outbox, bad):
    _send(client)
    assert _verify(client, KNOWN, bad).status_code == 422


def test_a_code_pasted_with_spaces_still_works(client, outbox):
    """Mail clients love to break a code into groups."""
    _send(client)
    code = outbox[0]["code"]
    spaced = f"{code[:3]} {code[3:]}"
    assert _verify(client, KNOWN, spaced).status_code == 200


# --------------------------------------------------------------- registration
def test_signup_creates_the_account_only_after_the_code_comes_back(
    client, anon_client, outbox
):
    res = _send(anon_client, email=NEW, purpose="signup")
    assert res.status_code == 200

    # Requesting a code must not create anything: there is still no account
    # for that address, and nothing to sign in to.
    assert anon_client.post(
        f"{BASE}/auth/login", json={"identifier": NEW, "password": "Passw0rd!"}
    ).status_code == 401

    verified = _verify(anon_client, NEW, outbox[0]["code"], purpose="signup")
    assert verified.status_code == 200, verified.text
    assert verified.json()["user"]["email"] == NEW


def test_a_verified_account_records_when_it_was_proven(client, outbox, db_session):
    from app.models.user import User

    _send(client)
    _verify(client, KNOWN, outbox[0]["code"])

    db_session.expire_all()
    user = db_session.scalars(select(User).where(User.email == KNOWN)).first()
    assert user.email_verified_at is not None


def test_an_email_only_account_cannot_be_signed_into_with_a_blank_password(
    anon_client, outbox
):
    _send(anon_client, email=NEW, purpose="signup")
    _verify(anon_client, NEW, outbox[0]["code"], purpose="signup")

    for attempt in ("", " ", "Passw0rd!"):
        res = anon_client.post(
            f"{BASE}/auth/login", json={"identifier": NEW, "password": attempt}
        )
        assert res.status_code in (401, 422)
        assert "token" not in res.json()


# --------------------------------------------------------------- rate limiting
def test_a_second_request_is_refused_during_the_cooldown(client, outbox):
    assert _send(client).status_code == 200
    second = _send(client)

    assert second.status_code == 429
    assert "Retry-After" in second.headers
    assert len(outbox) == 1, "a rate-limited request must not send mail"


def test_the_hourly_cap_per_address_holds(client, outbox, relaxed, monkeypatch):
    monkeypatch.setattr(get_settings(), "otp_per_email_per_hour", 3)

    for _ in range(3):
        assert _send(client).status_code == 200

    blocked = _send(client)
    assert blocked.status_code == 429
    assert len(outbox) == 3


def test_the_per_ip_cap_holds_across_different_addresses(
    client, db_session, outbox, relaxed, monkeypatch
):
    """One machine must not farm codes by rotating the address."""
    from app.services.auth_service import AuthService

    monkeypatch.setattr(get_settings(), "otp_per_email_per_hour", 50)
    monkeypatch.setattr(get_settings(), "otp_per_ip_per_hour", 2)

    auth = AuthService(db_session)
    for i in range(4):
        auth.register(f"user{i}", "Passw0rd!", email=f"user{i}@example.com")

    results = [_send(client, email=f"user{i}@example.com").status_code for i in range(4)]
    assert results[:2] == [200, 200]
    assert 429 in results[2:]


def test_requesting_again_retires_the_previous_code(client, outbox, relaxed):
    """Otherwise every resend leaves another live code for the same mailbox."""
    _send(client)
    first = outbox[0]["code"]
    _send(client)
    second = outbox[1]["code"]

    assert _verify(client, KNOWN, first).status_code == 400
    assert _verify(client, KNOWN, second).status_code == 200


# ------------------------------------------------------- provider not set up
def test_an_unconfigured_provider_fails_loudly(client, monkeypatch):
    """Never pretend mail was sent — the user would wait on an empty inbox."""
    monkeypatch.setattr(get_settings(), "resend_api_key", None)
    monkeypatch.setattr(get_settings(), "email_from", None)

    res = _send(client)
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert "resend.com" in detail and "ATLAS_RESEND_API_KEY" in detail


def test_a_failed_send_leaves_no_code_to_verify_against(client, monkeypatch):
    from app.services.email_service import EmailSendError

    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test_key")
    monkeypatch.setattr(get_settings(), "email_from", "atlas@example.com")

    def boom(message):
        raise EmailSendError("The email provider refused the message (422).")

    monkeypatch.setattr("app.services.email_service.send", boom)

    assert _send(client).status_code == 502
    # And the cooldown did not start, so the user can immediately try again.
    monkeypatch.setattr("app.services.email_service.send", lambda m: None)
    assert _send(client).status_code == 200


def test_email_status_tells_the_ui_whether_to_offer_this(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "resend_api_key", None)
    assert client.get(f"{BASE}/auth/email-status").json()["email_configured"] is False

    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test_key")
    monkeypatch.setattr(get_settings(), "email_from", "atlas@example.com")
    assert client.get(f"{BASE}/auth/email-status").json()["email_configured"] is True


# ----------------------------------------------------------- the dev back door
def test_the_dev_echo_is_impossible_to_enable_outside_development(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "otp_dev_echo", True)

    for env in ("production", "prod", "staging", "PRODUCTION"):
        monkeypatch.setattr(settings, "env", env)
        assert settings.otp_echo_allowed() is False, f"echo leaked in env={env!r}"

    monkeypatch.setattr(settings, "env", "development")
    assert settings.otp_echo_allowed() is True

    # And it stays off in development unless explicitly asked for.
    monkeypatch.setattr(settings, "otp_dev_echo", False)
    assert settings.otp_echo_allowed() is False


def test_the_dev_echo_returns_the_real_code_when_enabled(client, outbox, monkeypatch):
    monkeypatch.setattr(get_settings(), "otp_dev_echo", True)
    monkeypatch.setattr(get_settings(), "env", "development")

    body = _send(client).json()
    assert body["dev_code"] == outbox[0]["code"]
    assert _verify(client, KNOWN, body["dev_code"]).status_code == 200


# ---------------------------------------------------------- neutral responses
def test_neutral_mode_hides_which_addresses_have_accounts(client, outbox, monkeypatch):
    monkeypatch.setattr(get_settings(), "otp_neutral_responses", True)

    unknown = _send(client, email="nobody@example.com")
    taken = _send(client, email=KNOWN, purpose="signup")

    assert unknown.status_code == 200 and taken.status_code == 200
    assert unknown.json()["detail"] == taken.json()["detail"]
    assert outbox == [], "neutral mode still must not mail a stranger"
