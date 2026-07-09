import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

_BREVO_SMTP_KEY_PREFIX = "xsmtpsib-"
_BREVO_API_KEY_PREFIX = "xkeysib-"
_BREVO_SHORT_SMTP_KEY_LEN = 15

BREVO_SMTP_HOST = "smtp-relay.brevo.com"
BREVO_SMTP_PORT = 587


def smtp_password():
    return os.environ.get("SMTP_PASSWORD") or os.environ.get("BREVO_SMTP_KEY")


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
    """Log a hint when the key does not look like a Brevo SMTP key."""
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
    """True when Brevo/SMTP is set up enough to send mail."""
    password = smtp_password()
    if password:
        validate_smtp_key_format(password)
    return bool(smtp_host() and os.environ.get("SMTP_FROM") and password)


def send_password_reset_email(to_email, reset_url):
    """
    Send a password reset email via Brevo SMTP (or any SMTP).

    Returns:
        True  — email sent, or skipped intentionally (no SMTP; use console / API link)
        False — SMTP was configured but sending failed
    """
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
            "No SMTP configured — password reset link for %s:\n  %s",
            to_email,
            reset_url,
        )
        return True

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
        with smtplib.SMTP(host, port, timeout=30) as server:
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
        logger.exception("Failed to send password reset email to %s", to_email)
        return False
