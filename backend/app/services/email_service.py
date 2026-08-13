"""Transactional email.

Two ways out, chosen by configuration:

* **SMTP** (stdlib `smtplib`) — works with an ordinary mailbox such as Gmail
  with an App Password. Free, and needs no domain of your own, which makes it
  the sensible default for a personal desktop app.
* **Resend** over plain HTTPS, mirroring how the coach's providers talk to
  their APIs: no SDK, no dependency beyond the httpx the backend already has.
  Free to a point, but only reaches arbitrary recipients once you have verified
  a domain you own.

Credentials live only here, on the server. The desktop client never sees them,
never sends mail itself, and has no way to ask for them — every message goes
Desktop -> Atlas backend -> provider -> mailbox.

When nothing is configured this raises. It deliberately does **not** pretend to
have sent something: a silent no-op would leave a user staring at an inbox
waiting for a code that was never going to arrive.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("atlas.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"
_TIMEOUT = 20.0

SETUP_HINT = (
    "Email isn't configured yet. The free route is SMTP with an ordinary "
    "mailbox: for Gmail, turn on 2-Step Verification, create an App Password at "
    "myaccount.google.com/apppasswords, then set ATLAS_SMTP_HOST=smtp.gmail.com, "
    "ATLAS_SMTP_USER and ATLAS_SMTP_PASSWORD in backend/.env and restart Atlas. "
    "See .env.example."
)


class EmailNotConfigured(RuntimeError):
    """No provider credentials. Distinct from a send failure — the fix differs."""


class EmailSendError(RuntimeError):
    """The provider was reachable and refused, or could not be reached."""


@dataclass
class EmailMessage:
    to: str
    subject: str
    html_body: str
    text_body: str


def is_configured() -> bool:
    return get_settings().active_email_provider() is not None


def _from_address() -> str:
    """The bare address mail is sent from.

    SMTP falls back to the login user, because a mailbox almost always has to
    send as itself — Gmail silently rewrites anything else, so making people
    set a second variable that is ignored would be a trap.
    """
    settings = get_settings()
    explicit = (settings.email_from or "").strip()
    if explicit:
        return explicit
    return (settings.smtp_user or "").strip()


def _sender() -> str:
    """`Name <you@domain>` when a display name is set, else the bare address."""
    address = _from_address()
    name = (get_settings().email_from_name or "").strip()
    return f"{name} <{address}>" if name else address


def send(message: EmailMessage) -> None:
    """Deliver one message, or raise something the caller can explain.

    The only entry point. Callers never choose a provider — that is settled by
    configuration here, so adding a third one later touches nothing upstream.
    """
    provider = get_settings().active_email_provider()
    if provider is None:
        raise EmailNotConfigured(SETUP_HINT)
    if provider == "smtp":
        _send_smtp(message)
    else:
        _send_resend(message)


# --------------------------------------------------------------------- SMTP
def _send_smtp(message: EmailMessage) -> None:
    """Send through an ordinary mailbox. Free, and needs no domain of your own.

    Uses the standard library: no dependency, and nothing new in the packaged
    sidecar. A single multipart/alternative message carries both the plain-text
    and HTML parts, which is what mail clients and spam filters expect.
    """
    import smtplib
    import ssl
    from email.message import EmailMessage as MimeMessage

    settings = get_settings()

    mime = MimeMessage()
    mime["Subject"] = message.subject
    mime["From"] = _sender()
    mime["To"] = message.to
    mime.set_content(message.text_body)
    mime.add_alternative(message.html_body, subtype="html")

    context = ssl.create_default_context()
    try:
        # 465 is implicit TLS; 587 connects in the clear and upgrades. Getting
        # this backwards is the most common cause of a hang rather than an error.
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=_TIMEOUT, context=context
            )
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=_TIMEOUT)

        with server:
            if settings.smtp_port != 465 and settings.smtp_starttls:
                server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(mime)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailSendError(
            "The mail server rejected those credentials. For Gmail you need an "
            "App Password (16 characters, 2-Step Verification on) — your normal "
            "account password will not work."
        ) from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise EmailSendError(f"The mail server refused the recipient {message.to}.") from exc
    except (smtplib.SMTPException, OSError) as exc:
        # Covers connection refused, DNS failure, timeouts and TLS mismatches.
        # str(exc) never contains the password — smtplib does not echo it.
        raise EmailSendError(f"Couldn't send through {settings.smtp_host}: {exc}") from exc

    log.info("email.sent", extra={"to": message.to, "via": "smtp", "subject": message.subject})


# ------------------------------------------------------------------- Resend
def _send_resend(message: EmailMessage) -> None:
    import httpx

    settings = get_settings()
    payload = {
        "from": _sender(),
        "to": [message.to],
        "subject": message.subject,
        "html": message.html_body,
        "text": message.text_body,
    }

    try:
        res = httpx.post(
            RESEND_ENDPOINT,
            headers={
                # The only place this key is ever used. Never logged, never
                # returned to a client, never written into an error message.
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Couldn't reach the email provider: {exc}") from exc

    if res.status_code >= 400:
        raise EmailSendError(_explain(res))

    # Recipient is logged; the message id helps trace a delivery in Resend's
    # dashboard. The code itself is never in scope here.
    log.info(
        "email.sent",
        extra={
            "to": message.to,
            "via": "resend",
            "id": (res.json() or {}).get("id"),
            "subject": message.subject,
        },
    )


def _explain(res) -> str:
    """Provider errors, translated. The key is never echoed back."""
    try:
        body = res.json()
    except Exception:
        body = {}
    detail = body.get("message") or body.get("error") or ""

    if res.status_code in (401, 403):
        return "The email provider rejected the API key. Check ATLAS_RESEND_API_KEY."
    if res.status_code == 422 and "from" in str(detail).lower():
        return (
            "The provider rejected the sender address. ATLAS_EMAIL_FROM must be on a "
            "domain you have verified with Resend (its onboarding@resend.dev only "
            "delivers to your own account's address)."
        )
    if res.status_code == 429:
        return "The email provider is rate limiting us. Try again shortly."
    return f"The email provider refused the message ({res.status_code})." + (
        f" {detail}" if detail else ""
    )


# ------------------------------------------------------------------ templates
def otp_message(to: str, code: str, minutes: int, app_name: str) -> EmailMessage:
    """The verification email.

    Plain text alongside the HTML so it stays readable in clients that refuse
    HTML, and so spam filters see a well-formed multipart message. The code is
    spaced in the HTML for legibility but kept intact in the text part, where a
    reader is more likely to copy it.
    """
    safe_app = html.escape(app_name)
    safe_code = html.escape(code)

    text_body = (
        f"Your {app_name} verification code is {code}.\n\n"
        f"It expires in {minutes} minutes.\n\n"
        "Do not share this code with anyone. "
        f"If you did not request it, you can ignore this email — no changes were made.\n"
    )

    html_body = f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:24px;background:#FBF8F4;
               font-family:ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;
               color:#2B2622;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"
           style="max-width:440px;margin:0 auto;background:#FFFFFF;border-radius:16px;
                  border:1px solid rgba(43,38,34,0.08);">
      <tr>
        <td style="padding:28px 28px 8px;">
          <div style="font-size:13px;font-weight:600;letter-spacing:0.08em;
                      text-transform:uppercase;color:#9C9289;">{safe_app}</div>
          <h1 style="margin:12px 0 4px;font-family:Georgia,'Times New Roman',serif;
                     font-size:22px;font-weight:600;">Your verification code</h1>
          <p style="margin:0;font-size:14px;line-height:1.6;color:#6B6259;">
            Enter this code in {safe_app} to confirm your email address.
          </p>
        </td>
      </tr>
      <tr>
        <td style="padding:20px 28px;">
          <div style="background:#FBF8F4;border:1px solid rgba(43,38,34,0.08);
                      border-radius:12px;padding:18px;text-align:center;
                      font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
                      font-size:30px;font-weight:700;letter-spacing:0.28em;
                      color:#C2703D;">{safe_code}</div>
        </td>
      </tr>
      <tr>
        <td style="padding:0 28px 26px;">
          <p style="margin:0 0 10px;font-size:13px;line-height:1.6;color:#6B6259;">
            This code expires in <strong>{minutes} minutes</strong>.
          </p>
          <p style="margin:0 0 10px;font-size:13px;line-height:1.6;color:#6B6259;">
            <strong>Do not share this code with anyone.</strong> {safe_app} will never
            ask you for it.
          </p>
          <p style="margin:0;font-size:12px;line-height:1.6;color:#9C9289;">
            If you didn't request this, you can safely ignore this email — nothing
            has changed on your account.
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>"""

    return EmailMessage(
        to=to,
        subject="Your verification code",
        html_body=html_body,
        text_body=text_body,
    )


def send_otp(to: str, code: str, minutes: int, app_name: Optional[str] = None) -> None:
    send(otp_message(to, code, minutes, app_name or get_settings().app_name))
