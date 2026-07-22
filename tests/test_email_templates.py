from unittest.mock import patch

from api.email_service import (
    build_action_email,
    send_email_verification,
    send_password_reset_email,
)


MAIL_ENV = {
    "EMAIL_TRANSPORT": "api",
    "BREVO_API_KEY": "test-api-key",
    "SMTP_FROM": "Budget Tracker <noreply@example.com>",
}


def test_action_email_is_branded_responsive_and_escapes_url():
    html = build_action_email(
        preheader="Preview",
        eyebrow="Email verification",
        title="Verify your email address",
        message="Welcome to Budget Tracker.",
        action_label="Verify email address",
        action_url='https://example.com/verify?token=a&next="budget"',
        expiry_message="Expires in 24 hours.",
        ignore_message="Ignore this email.",
    )

    assert html.startswith("<!doctype html>")
    assert 'name="viewport"' in html
    assert 'role="presentation"' in html
    assert "Budget Tracker" in html
    assert "linear-gradient(135deg,#2b0d55" in html
    assert "Verify email address &rarr;" in html
    assert "token=a&amp;next=&quot;budget&quot;" in html
    assert 'token=a&next="budget"' not in html


def test_password_reset_email_has_plain_text_and_branded_html():
    with (
        patch.dict("api.email_service.os.environ", MAIL_ENV, clear=True),
        patch("api.email_service.send_via_brevo_api", return_value=True) as send,
    ):
        result = send_password_reset_email(
            "person@example.com",
            "https://app.example.com/reset-password?token=secret",
        )

    assert result is True
    to_email, subject, text_body, html_body = send.call_args.args
    assert to_email == "person@example.com"
    assert subject == "Reset your Budget Tracker password"
    assert "expires in 1 hour" in text_body
    assert "Choose a new password" in html_body
    assert "Reset password &rarr;" in html_body
    assert "Your password will stay unchanged" in html_body


def test_verification_email_has_plain_text_and_branded_html():
    with (
        patch.dict("api.email_service.os.environ", MAIL_ENV, clear=True),
        patch("api.email_service.send_via_brevo_api", return_value=True) as send,
    ):
        result = send_email_verification(
            "person@example.com",
            "https://app.example.com/verify-email?token=secret",
        )

    assert result is True
    to_email, subject, text_body, html_body = send.call_args.args
    assert to_email == "person@example.com"
    assert subject == "Verify your Budget Tracker email"
    assert "within 24 hours" in text_body
    assert "Verify your email address" in html_body
    assert "Verify email address &rarr;" in html_body
    assert "request a new link from the sign-in page" in html_body
