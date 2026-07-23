import json
import logging
import os
import smtplib
import threading
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr
from html import escape

logger = logging.getLogger(__name__)

BREVO_SMTP_KEY_PREFIX = "xsmtpsib-"
BREVO_API_KEY_PREFIX = "xkeysib-"
BREVO_SHORT_SMTP_KEY_LEN = 15

BREVO_SMTP_HOST = "smtp-relay.brevo.com"
BREVO_SMTP_PORT = 587
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
SMTP_TIMEOUT_SEC = 15


def build_action_email(
    preheader,
    eyebrow,
    title,
    message,
    action_label,
    action_url,
    expiry_message,
    ignore_message,
):
    safe_url = escape(action_url, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:#f3eeff;color:#2a1a4a;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{escape(preheader)}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#f3eeff;">
    <tr>
      <td align="center" style="padding:36px 16px 44px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;">
          <tr>
            <td align="center" style="padding:0 0 20px;">
              <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td align="center" width="54" height="54" style="width:54px;height:54px;border-radius:16px;background:#7b2cbf;background-image:linear-gradient(135deg,#7b2cbf,#9d4edd);box-shadow:0 12px 28px rgba(123,44,191,.28);color:#ffffff;font-size:20px;font-weight:800;letter-spacing:-1px;">BT</td>
                </tr>
              </table>
              <div style="padding-top:10px;color:#4a3a68;font-size:15px;font-weight:700;letter-spacing:.2px;">Budget Tracker</div>
            </td>
          </tr>
          <tr>
            <td style="border-radius:24px;background:#ffffff;box-shadow:0 24px 60px rgba(74,27,120,.16);overflow:hidden;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td align="center" style="padding:42px 28px 38px;background:#2b0d55;background-image:linear-gradient(135deg,#2b0d55 0%,#6d2fb3 58%,#8b3ce0 100%);">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                      <tr>
                        <td align="center" width="76" height="76" style="width:76px;height:76px;border-radius:24px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.28);color:#ffffff;font-size:34px;line-height:76px;">&#9993;</td>
                      </tr>
                    </table>
                    <div style="padding-top:18px;color:#e8dff8;font-size:12px;font-weight:800;letter-spacing:2px;text-transform:uppercase;">{escape(eyebrow)}</div>
                  </td>
                </tr>
                <tr>
                  <td align="center" style="padding:44px 44px 20px;">
                    <h1 style="margin:0;color:#2a1a4a;font-size:30px;line-height:1.22;font-weight:800;letter-spacing:-.6px;">{escape(title)}</h1>
                    <p style="margin:18px 0 0;color:#5f5776;font-size:16px;line-height:1.7;">{escape(message)}</p>
                  </td>
                </tr>
                <tr>
                  <td align="center" style="padding:10px 32px 26px;">
                    <a href="{safe_url}" style="display:inline-block;min-width:210px;padding:16px 28px;border-radius:14px;background:#7b2cbf;background-image:linear-gradient(135deg,#7b2cbf,#9d4edd);box-shadow:0 10px 24px rgba(123,44,191,.3);color:#ffffff;font-size:15px;font-weight:800;line-height:20px;text-align:center;text-decoration:none;letter-spacing:.2px;">{escape(action_label)} &rarr;</a>
                  </td>
                </tr>
                <tr>
                  <td style="padding:0 44px 30px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f5f0ff;border:1px solid #e8dff8;border-radius:14px;">
                      <tr>
                        <td style="padding:14px 16px;color:#5f5776;font-size:13px;line-height:1.55;text-align:center;">{escape(expiry_message)}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:0 44px 40px;">
                    <p style="margin:0;color:#7c7590;font-size:13px;line-height:1.65;text-align:center;">{escape(ignore_message)}</p>
                    <p style="margin:22px 0 8px;color:#7c7590;font-size:12px;line-height:1.5;text-align:center;">Button not working? Copy and paste this link into your browser:</p>
                    <p style="margin:0;word-break:break-all;text-align:center;"><a href="{safe_url}" style="color:#7b2cbf;font-size:12px;line-height:1.55;text-decoration:underline;">{safe_url}</a></p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:22px 24px 0;color:#7c7590;font-size:12px;line-height:1.6;">Budget Tracker &middot; A secure account notification</td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def smtp_password():
    return os.environ.get("SMTP_PASSWORD") or os.environ.get("BREVO_SMTP_KEY")


def brevo_api_key():
    return os.environ.get("BREVO_API_KEY")


def smtp_host():
    return os.environ.get("SMTP_HOST") or (
        BREVO_SMTP_HOST if smtp_password() else None
    )


def looks_like_brevo_smtp_key(password):
    if password.startswith(BREVO_SMTP_KEY_PREFIX):
        return True
    if len(password) == BREVO_SHORT_SMTP_KEY_LEN and password.isalnum():
        return True
    return False


def validate_smtp_key_format(password):
    if not password:
        return
    host = smtp_host() or ""
    if "brevo" not in host:
        return
    if password.startswith(BREVO_API_KEY_PREFIX):
        logger.warning(
            "BREVO_SMTP_KEY looks like a Brevo API key (%s). Use an SMTP key from "
            "Brevo → SMTP & API → SMTP tab instead.",
            BREVO_API_KEY_PREFIX,
        )
        return
    if not looks_like_brevo_smtp_key(password):
        logger.warning(
            "BREVO_SMTP_KEY may be invalid — use an SMTP key from "
            "Brevo → SMTP & API → SMTP tab (standard xsmtpsib- or 15-char short key).",
        )


def preferred_email_transport():
    transport = os.environ.get("EMAIL_TRANSPORT", "").strip().lower()
    if transport == "smtp":
        return "smtp"
    if transport == "api":
        return "api"
    if os.environ.get("FLASK_ENV", "development") == "development" and smtp_password():
        return "smtp"
    if brevo_api_key():
        return "api"
    if smtp_password():
        return "smtp"
    return None


def delivery_transport_name():
    transport = preferred_email_transport()
    if transport:
        return transport
    if os.environ.get("FLASK_ENV", "development") != "production":
        return "development_log"
    return "unconfigured"


def mail_configured():
    if not os.environ.get("SMTP_FROM"):
        return False
    if preferred_email_transport() == "api" and brevo_api_key():
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
                    "Email sent to %s via Brevo API (from %s)",
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
        logger.info("Email sent to %s via %s (from %s)", to_email, host, msg["From"])
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
        logger.exception("Failed to send email to %s via SMTP", to_email)
        return False


def send_password_reset_email(to_email, reset_url):
    subject = "Reset your Budget Tracker password"
    text_body = (
        "You requested a password reset for Budget Tracker.\n\n"
        f"Open this link to choose a new password (expires in 1 hour):\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    html_body = build_action_email(
        preheader="Reset your Budget Tracker password securely.",
        eyebrow="Password reset",
        title="Choose a new password",
        message="We received a request to reset your Budget Tracker password. Use the secure button below to choose a new one.",
        action_label="Reset password",
        action_url=reset_url,
        expiry_message="For your security, this password reset link expires in 1 hour and can only be used once.",
        ignore_message="If you did not request a password reset, you can safely ignore this email. Your password will stay unchanged.",
    )

    if not mail_configured():
        if os.environ.get("FLASK_ENV", "development") != "production":
            logger.warning(
                "No email configured — password reset link for %s:\n  %s",
                to_email,
                reset_url,
            )
            return True
        logger.error("Password reset email could not be sent because email is not configured")
        return False

    transport = preferred_email_transport()
    if transport == "api" and brevo_api_key():
        return send_via_brevo_api(to_email, subject, text_body, html_body)
    if transport == "smtp":
        return send_via_smtp(to_email, subject, text_body, html_body)
    return False


def send_email_background(sender, args, name, on_complete=None):
    def run():
        success = sender(*args)
        if on_complete:
            try:
                on_complete(success)
            except Exception:
                logger.exception("Email delivery completion callback failed")

    thread = threading.Thread(target=run, daemon=True, name=name)
    thread.start()
    return thread


def send_password_reset_email_background(to_email, reset_url, on_complete=None):
    return send_email_background(
        send_password_reset_email,
        (to_email, reset_url),
        "password-reset-email",
        on_complete,
    )


def send_email_verification(to_email, verification_url):
    subject = "Verify your Budget Tracker email"
    text_body = (
        "Verify your email address for Budget Tracker.\n\n"
        f"Open this link within 24 hours:\n{verification_url}\n\n"
        "If you did not create or update this account, you can ignore this email.\n"
    )
    html_body = build_action_email(
        preheader="Verify your email to finish setting up Budget Tracker.",
        eyebrow="Email verification",
        title="Verify your email address",
        message="Welcome to Budget Tracker. Confirm your email address to activate your account and start managing your money with confidence.",
        action_label="Verify email address",
        action_url=verification_url,
        expiry_message="This verification link expires in 24 hours. If it expires, request a new link from the sign-in page.",
        ignore_message="If you did not create or update this account, you can safely ignore this email.",
    )

    if not mail_configured():
        if os.environ.get("FLASK_ENV", "development") != "production":
            logger.warning("Email verification link for local development:\n  %s", verification_url)
            return True
        logger.error("Email verification could not be sent because email is not configured")
        return False

    transport = preferred_email_transport()
    if transport == "api" and brevo_api_key():
        return send_via_brevo_api(to_email, subject, text_body, html_body)
    if transport == "smtp":
        return send_via_smtp(to_email, subject, text_body, html_body)
    return False


def send_email_verification_background(to_email, verification_url, on_complete=None):
    return send_email_background(
        send_email_verification,
        (to_email, verification_url),
        "email-verification",
        on_complete,
    )
