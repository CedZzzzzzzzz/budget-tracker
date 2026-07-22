from unittest.mock import patch

from flask import Flask

from api.routes import api
from extensions import limiter


def create_test_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    app.secret_key = "test-secret"
    limiter.init_app(app)
    app.register_blueprint(api)
    return app


def csrf_client(authenticated=False):
    client = create_test_app().test_client()
    with client.session_transaction() as user_session:
        user_session["csrf_token"] = "csrf-token"
        if authenticated:
            user_session["user_id"] = 42
            user_session["username"] = "marcus"
    return client


def post_with_csrf(client, path, payload):
    return client.post(path, json=payload, headers={"X-CSRF-Token": "csrf-token"})


def test_registration_creates_pending_account_without_session():
    client = csrf_client()
    user = {
        "id": 42,
        "username": "marcus",
        "email": "marcus@example.com",
        "email_verified_at": None,
    }
    with (
        patch("api.routes.db.get_user_by_username", return_value=None),
        patch("api.routes.db.get_user_by_email", side_effect=[None, user]),
        patch("api.routes.db.create_user", return_value=42),
        patch("api.routes.deliver_verification_email", return_value=True) as deliver,
    ):
        response = post_with_csrf(client, "/api/register", {
            "username": "marcus",
            "email": "marcus@example.com",
            "password": "Password1!",
        })

    assert response.status_code == 200
    assert response.get_json()["verification_required"] is True
    deliver.assert_called_once_with(42, "marcus@example.com")
    with client.session_transaction() as user_session:
        assert "user_id" not in user_session


def test_login_blocks_unverified_account_only_after_correct_password():
    client = csrf_client()
    user = {
        "id": 42,
        "username": "marcus",
        "email": "marcus@example.com",
        "email_verified_at": None,
    }
    with (
        patch("api.routes.db.get_user_by_username", return_value=user),
        patch("api.routes.db.verify_password", return_value=True),
    ):
        response = post_with_csrf(client, "/api/login", {
            "username": "marcus",
            "password": "Password1!",
        })

    assert response.status_code == 403
    assert response.get_json()["verification_required"] is True


def test_wrong_password_does_not_reveal_verification_state():
    client = csrf_client()
    user = {
        "id": 42,
        "username": "marcus",
        "email": "marcus@example.com",
        "email_verified_at": None,
    }
    with (
        patch("api.routes.db.get_user_by_username", return_value=user),
        patch("api.routes.db.verify_password", return_value=False),
    ):
        response = post_with_csrf(client, "/api/login", {
            "username": "marcus",
            "password": "WrongPassword1!",
        })

    assert response.status_code == 401
    assert "verification_required" not in response.get_json()


def test_verification_endpoint_accepts_valid_token_without_csrf():
    client = create_test_app().test_client()
    with patch("api.routes.db.consume_email_verification_token", return_value="verified") as consume:
        response = client.post("/api/verify-email", json={"token": "valid-token"})

    assert response.status_code == 200
    consume.assert_called_once_with("valid-token")


def test_verification_endpoint_returns_generic_invalid_error():
    client = create_test_app().test_client()
    with patch("api.routes.db.consume_email_verification_token", return_value="invalid"):
        response = client.post("/api/verify-email", json={"token": "expired-token"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid or expired verification link."


def test_resend_response_is_generic_for_missing_account():
    client = create_test_app().test_client()
    with (
        patch("api.routes.db.get_user_by_email", return_value=None),
        patch("api.routes.deliver_verification_email") as deliver,
    ):
        response = client.post("/api/resend-verification", json={"email": "missing@example.com"})

    assert response.status_code == 200
    assert "unverified account exists" in response.get_json()["message"]
    deliver.assert_not_called()


def test_email_change_requires_verification_and_clears_session():
    client = csrf_client(authenticated=True)
    user = {
        "id": 42,
        "username": "marcus",
        "email": "old@example.com",
        "email_verified_at": object(),
    }
    with (
        patch("api.routes.db.user_exists", return_value=True),
        patch("api.routes.db.get_user_by_id", return_value=user),
        patch("api.routes.db.get_user_by_email", return_value=None),
        patch("api.routes.db.update_user_profile", return_value=True) as update,
        patch("api.routes.deliver_verification_email", return_value=True) as deliver,
    ):
        response = client.put(
            "/api/profile",
            json={"username": "marcus", "email": "new@example.com"},
            headers={"X-CSRF-Token": "csrf-token"},
        )

    assert response.status_code == 200
    assert response.get_json()["verification_required"] is True
    update.assert_called_once_with(
        42,
        username="marcus",
        email="new@example.com",
        reset_email_verification=True,
    )
    deliver.assert_called_once_with(42, "new@example.com")
    with client.session_transaction() as user_session:
        assert "user_id" not in user_session
