"""How a verification email actually leaves the machine.

Two transports: SMTP through an ordinary mailbox (free, no domain needed) and
Resend over HTTPS. These tests cover the choice between them and the SMTP path
itself — the message that gets built, and what each failure is translated into.

No socket is opened. `smtplib.SMTP` is replaced with a recorder that behaves
like the real thing at the four points the service touches: `starttls`, `login`,
`send_message`, and the context-manager protocol.
"""
from __future__ import annotations

import logging
import logging.handlers
import smtplib

import pytest

from app.core.config import Settings, get_settings
from app.services import email_service
from app.services.email_service import EmailNotConfigured, EmailSendError


def _settings(**overrides) -> Settings:
    """A settings object with nothing configured but the overrides.

    Built directly rather than by patching the cached instance, so a stray
    ATLAS_* variable in the developer's own .env cannot decide the outcome.
    """
    base = dict(
        email_provider="auto",
        smtp_host=None,
        smtp_user=None,
        smtp_password=None,
        resend_api_key=None,
        email_from=None,
    )
    base.update(overrides)
    return Settings(**base)


SMTP_CREDS = dict(smtp_host="smtp.gmail.com", smtp_user="me@gmail.com", smtp_password="app-pw")
RESEND_CREDS = dict(resend_api_key="re_test", email_from="no-reply@mine.test")


class FakeSMTP:
    """Records what the service does to a connection, and sends nothing."""

    instances: list["FakeSMTP"] = []
    #: Raised from login(), to exercise the error translation.
    login_error: Exception | None = None

    def __init__(self, host=None, port=None, timeout=None, context=None):
        self.host, self.port, self.context = host, port, context
        self.started_tls = False
        self.credentials = None
        self.messages = []
        self.closed = False
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False

    def starttls(self, context=None):
        self.started_tls = True

    def login(self, user, password):
        if FakeSMTP.login_error:
            raise FakeSMTP.login_error
        self.credentials = (user, password)

    def send_message(self, mime):
        self.messages.append(mime)


@pytest.fixture()
def smtp(monkeypatch):
    FakeSMTP.instances = []
    FakeSMTP.login_error = None
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


@pytest.fixture()
def captured_logs():
    """Everything the email logger would actually write, as text.

    Records are run through the app's own JsonFormatter rather than read off
    `record.message`: the fields at issue arrive via `extra=`, which the plain
    message never contains — so asserting on it would pass no matter what.
    """
    from app.core.logging import JsonFormatter

    handler = logging.handlers.MemoryHandler(capacity=1000, flushLevel=logging.CRITICAL + 1)
    logger = logging.getLogger("atlas.email")
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        formatter = JsonFormatter()
        yield lambda: "\n".join(formatter.format(r) for r in handler.buffer)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


def _use(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr(email_service, "get_settings", lambda: settings)


def _message() -> email_service.EmailMessage:
    return email_service.otp_message("you@example.com", "123456", 10, "Atlas")


# ------------------------------------------------------------ which provider
def test_nothing_configured_is_nothing_configured():
    assert _settings().active_email_provider() is None


def test_smtp_alone_is_enough():
    """No ATLAS_EMAIL_FROM required — a mailbox sends as itself."""
    assert _settings(**SMTP_CREDS).active_email_provider() == "smtp"


def test_partial_smtp_credentials_do_not_count():
    """Half a configuration would fail at send time, which is far too late."""
    assert _settings(smtp_host="smtp.gmail.com").active_email_provider() is None
    assert _settings(smtp_host="smtp.gmail.com", smtp_user="me@gmail.com").active_email_provider() is None


def test_resend_needs_a_from_address():
    """It has no mailbox to fall back to; the API rejects a missing sender."""
    assert _settings(resend_api_key="re_test").active_email_provider() is None
    assert _settings(**RESEND_CREDS).active_email_provider() == "resend"


def test_auto_prefers_smtp_when_both_are_configured():
    """The free one wins by default. Resend still costs money past its tier."""
    both = _settings(**SMTP_CREDS, **RESEND_CREDS)
    assert both.active_email_provider() == "smtp"


def test_an_explicit_choice_is_honoured():
    both = dict(**SMTP_CREDS, **RESEND_CREDS)
    assert _settings(email_provider="resend", **both).active_email_provider() == "resend"
    assert _settings(email_provider="smtp", **both).active_email_provider() == "smtp"


def test_pinning_a_provider_that_is_not_configured_does_not_fall_back():
    """Silently sending through the other one would defeat the point of pinning."""
    assert _settings(email_provider="smtp", **RESEND_CREDS).active_email_provider() is None
    assert _settings(email_provider="resend", **SMTP_CREDS).active_email_provider() is None


def test_send_refuses_when_unconfigured(monkeypatch):
    _use(monkeypatch, _settings())
    with pytest.raises(EmailNotConfigured) as exc:
        email_service.send(_message())
    # The message has to be enough to fix it: the free route, and the variables.
    assert "App Password" in str(exc.value)
    assert "ATLAS_SMTP_HOST" in str(exc.value)


def test_dispatch_follows_the_active_provider(monkeypatch):
    calls = []
    monkeypatch.setattr(email_service, "_send_smtp", lambda m: calls.append("smtp"))
    monkeypatch.setattr(email_service, "_send_resend", lambda m: calls.append("resend"))

    _use(monkeypatch, _settings(**SMTP_CREDS))
    email_service.send(_message())
    _use(monkeypatch, _settings(**RESEND_CREDS))
    email_service.send(_message())

    assert calls == ["smtp", "resend"]


# ------------------------------------------------------------- the SMTP send
def test_a_sent_message_carries_both_parts(monkeypatch, smtp):
    _use(monkeypatch, _settings(**SMTP_CREDS))
    email_service.send(_message())

    (conn,) = smtp.instances
    (mime,) = conn.messages
    assert mime["To"] == "you@example.com"
    assert mime["Subject"] == "Your verification code"
    # multipart/alternative: clients that refuse HTML still show the code, and
    # a text part is what keeps a bare-HTML mail out of the spam folder.
    assert mime.is_multipart()
    types = {p.get_content_type() for p in mime.walk() if not p.is_multipart()}
    assert types == {"text/plain", "text/html"}
    assert "123456" in mime.get_body(("plain",)).get_content()


def test_the_mailbox_sends_as_itself_by_default(monkeypatch, smtp):
    """Gmail rewrites a mismatched From; defaulting to it avoids a silent lie."""
    _use(monkeypatch, _settings(**SMTP_CREDS, email_from_name=""))
    email_service.send(_message())
    assert smtp.instances[0].messages[0]["From"] == "me@gmail.com"


def test_a_display_name_is_used_when_set(monkeypatch, smtp):
    _use(monkeypatch, _settings(**SMTP_CREDS, email_from_name="Atlas"))
    email_service.send(_message())
    assert smtp.instances[0].messages[0]["From"] == "Atlas <me@gmail.com>"


def test_port_587_upgrades_with_starttls(monkeypatch, smtp):
    _use(monkeypatch, _settings(**SMTP_CREDS, smtp_port=587))
    email_service.send(_message())

    (conn,) = smtp.instances
    assert conn.port == 587
    assert conn.started_tls, "587 starts in the clear and must be upgraded"
    assert conn.credentials == ("me@gmail.com", "app-pw")
    assert conn.closed


def test_port_465_is_already_encrypted(monkeypatch, smtp):
    """Calling STARTTLS on an implicit-TLS connection hangs rather than errors."""
    _use(monkeypatch, _settings(**SMTP_CREDS, smtp_port=465))
    email_service.send(_message())

    (conn,) = smtp.instances
    assert conn.port == 465
    assert not conn.started_tls
    assert conn.context is not None, "implicit TLS still needs a verified context"


def test_starttls_can_be_turned_off(monkeypatch, smtp):
    """For a local relay on 25 that has no TLS at all."""
    _use(monkeypatch, _settings(**SMTP_CREDS, smtp_port=25, smtp_starttls=False))
    email_service.send(_message())
    assert not smtp.instances[0].started_tls


# --------------------------------------------------------------- what breaks
def test_a_normal_password_gets_the_app_password_hint(monkeypatch, smtp):
    """The single most likely setup mistake, so it names its own fix."""
    smtp.login_error = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    _use(monkeypatch, _settings(**SMTP_CREDS))

    with pytest.raises(EmailSendError) as exc:
        email_service.send(_message())
    assert "App Password" in str(exc.value)


def test_an_unreachable_server_is_reported_not_swallowed(monkeypatch, smtp):
    smtp.login_error = OSError("[Errno 11001] getaddrinfo failed")
    _use(monkeypatch, _settings(**{**SMTP_CREDS, "smtp_host": "smtp.typo.invalid"}))

    with pytest.raises(EmailSendError) as exc:
        email_service.send(_message())
    assert "smtp.typo.invalid" in str(exc.value)


def test_the_password_never_reaches_the_error_text(monkeypatch, smtp):
    smtp.login_error = smtplib.SMTPException("connection reset")
    _use(monkeypatch, _settings(**{**SMTP_CREDS, "smtp_password": "hunter2-secret"}))

    with pytest.raises(EmailSendError) as exc:
        email_service.send(_message())
    assert "hunter2-secret" not in str(exc.value)


def test_a_failed_send_never_logs_success(monkeypatch, smtp, captured_logs):
    """A logged success on a failed send is worse than no log at all."""
    smtp.login_error = smtplib.SMTPAuthenticationError(535, b"nope")
    _use(monkeypatch, _settings(**SMTP_CREDS))

    with pytest.raises(EmailSendError):
        email_service.send(_message())
    assert "email.sent" not in captured_logs()


def test_the_code_is_never_logged(monkeypatch, smtp, captured_logs):
    """Anyone who can read a log file must not be able to read a live code."""
    _use(monkeypatch, _settings(**SMTP_CREDS))
    email_service.send(_message())

    written = captured_logs()
    assert "email.sent" in written, "the send should still leave a trace"
    assert "123456" not in written
    assert "app-pw" not in written


def test_is_configured_tracks_the_active_provider(monkeypatch):
    """What the sign-in screen asks before offering the button at all."""
    _use(monkeypatch, _settings())
    assert not email_service.is_configured()
    _use(monkeypatch, _settings(**SMTP_CREDS))
    assert email_service.is_configured()


def test_the_real_settings_object_is_still_the_one_being_read():
    """Guards the _settings() shortcut above from drifting out of the app."""
    live = get_settings()
    for field in ("smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_starttls"):
        assert hasattr(live, field), f"{field} missing from Settings"
    assert callable(live.active_email_provider)
