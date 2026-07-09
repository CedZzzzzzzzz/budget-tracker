import json
import logging
import os
import smtplib
import threading
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr

logger = logging.getLogger(__name__)

_BREVO_SMTP_KEY_PREFIX = "xsmtpsib-"
_BREVO_API_KEY_PREFIX = "xkeysib-"
_BREVO_SHORT_SMTP_KEY_LEN = 15

BREVO_SMTP_HOST = "smtp-relay.brevo.com"
BREVO_SMTP_PORT = 587
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
SMTP_TIMEOUT_SEC = 15


def smtp_password():
    return os.environ.get("SMTP_PASSWORD") or os.environ.get("BREVO_SMTP_KEY")


def brevo_api_key():
    return os.environ.get("BREVO_API_KEY")


def smtp_host():
    return os.environ.get("SMTP_HOST") or (
        BREVO_SMTP_HOST if smtp_password() else None
    )


def looks_like_brevo_smtp_key(password):
    if password.startswith(_BREVO_SMTP_KEY_PREFIX):
        return True
    if len(password) == _BREVO_SHORT_SMTP_KEY_LEN and password.isalnum():
        return True
    return False


def validate_smtp_key_format(password):
    if not password:
        return
    host = smtp_host() or ""
    if "brevo" not in host:
        return
    if password.startswith(_BREVO_API_KEY_PREFIX):
        logger.warning(
            "BREVO_SMTP_KEY looks like a Brevo API key (%s). Use an SMTP key from "
            "Brevo → SMTP & API → SMTP tab instead.",
            _BREVO_API_KEY_PREFIX,
        )
        return
    if not looks_like_brevo_smtp_key(password):
        logger.warning(
            "BREVO_SMTP_KEY may be invalid — use an SMTP key from "
            "Brevo → SMTP & API → SMTP tab (standard xsmtpsib- or 15-char short key).",
        )


def mail_configured():
    if not os.environ.get("SMTP_FROM"):
        return False
    if brevo_api_key():
        return True
    password = smtp_password()
    if password:
        validate_smtp_key_format(password)
    return bool(smtp_host() and password)


def parse_smtp_from(from_header):
    name, email = parseaddr(from_header)
    if not email:
        email = from_header.strip()
    if not name:
        name = "Budget Tracker"
    return name, email


def send_via_brevo_api(to_email, subject, text_body, html_body):
    api_key = brevo_api_key()
    if not api_key:
        return False

    sender_name, sender_email = parse_smtp_from(os.environ["SMTP_FROM"])
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": text_body,
        "htmlContent": html_body,
    }
    req = urllib.request.Request(
        BREVO_API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=SMTP_TIMEOUT_SEC) as resp:
            if 200 <= resp.status < 300:
                logger.info(
                    "Password reset email sent to %s via Brevo API (from %s)",
                    to_email,
                    sender_email,
                )
                return True
        return False
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        logger.error("Brevo API email failed (%s) for %s: %s", exc.code, to_email, body)
        return False
    except Exception:
        logger.exception("Brevo API email failed for %s", to_email)
        return False


def send_via_smtp(to_email, subject, text_body, html_body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    host = smtp_host()
    port = int(os.environ.get("SMTP_PORT", str(BREVO_SMTP_PORT)))
    user = os.environ.get("SMTP_USER")
    password = smtp_password()
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

    try:
        with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SEC) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        logger.info("Password reset email sent to %s via %s (from %s)", to_email, host, msg["From"])
        return True
    except smtplib.SMTPAuthenticationError as exc:
        code = exc.smtp_code if hasattr(exc, "smtp_code") else None
        if code == 525:
            logger.exception(
                "SMTP blocked for %s — Brevo rejected this server's IP address. "
                "Authorize your IP in Brevo → Settings → Security → Authorized IPs.",
                user,
            )
        else:
            logger.exception(
                "SMTP authentication failed for %s — check SMTP_USER (Brevo SMTP login) "
                "and BREVO_SMTP_KEY (SMTP key, not API key).",
                user,
            )
        return False
    except Exception:
        logger.exception("Failed to send password reset email to %s via SMTP", to_email)
        return False


def send_password_reset_email(to_email, reset_url):
    subject = "Reset your Budget Tracker password"
    text_body = (
        "You requested a password reset for Budget Tracker.\n\n"
        f"Open this link to choose a new password (expires in 1 hour):\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    html_body = (
        "<p>You requested a password reset for <strong>Budget Tracker</strong>.</p>"
        f'<p><a href="{reset_url}">Choose a new password</a> '
        "(this link expires in 1 hour).</p>"
        "<p>If you did not request this, you can ignore this email.</p>"
    )

    if not mail_configured():
        logger.warning(
            "No email configured — password reset link for %s:\n  %s",
            to_email,
            reset_url,
        )
        return True

    transport = os.environ.get("EMAIL_TRANSPORT", "").lower()
    if brevo_api_key() and transport != "smtp":
        return send_via_brevo_api(to_email, subject, text_body, html_body)
    return send_via_smtp(to_email, subject, text_body, html_body)


def send_password_reset_email_background(to_email, reset_url):
    threading.Thread(
        target=send_password_reset_email,
        args=(to_email, reset_url),
        daemon=True,
        name="password-reset-email",
    ).start()
