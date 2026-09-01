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


def csrf_client(authenticated=False, user_id=42):
    client = create_test_app().test_client()
    with client.session_transaction() as user_session:
        user_session["csrf_token"] = "csrf-token"
        if authenticated:
            user_session["user_id"] = user_id
            user_session["username"] = "marcus"
            user_session["session_version"] = 1
    return client


def post_with_csrf(client, path, payload=None):
    return client.post(path, json=payload or {}, headers={"X-CSRF-Token": "csrf-token"})


def test_saturday_reminder_requires_authentication():
    client = csrf_client(authenticated=False)
    response = post_with_csrf(client, "/api/user/send-saturday-reminder")
    assert response.status_code == 401
    assert response.get_json()["error"] == "Authentication required"


def test_saturday_reminder_fails_without_email():
    client = csrf_client(authenticated=True)
    with (
        patch("api.routes.db.user_exists", return_value=True),
        patch("api.routes.db.get_user_by_id", return_value={"id": 42, "email": None}),
    ):
        response = post_with_csrf(client, "/api/user/send-saturday-reminder")
    assert response.status_code == 400
    assert "No verified email" in response.get_json()["error"]


def test_saturday_reminder_triggers_background_email():
    client = csrf_client(authenticated=True)
    user = {"id": 42, "email": "marcus@example.com", "username": "marcus"}
    with (
        patch("api.routes.db.user_exists", return_value=True),
        patch("api.routes.db.get_user_by_id", return_value=user),
        patch("api.routes.send_saturday_reminder_email_background") as sender,
    ):
        response = post_with_csrf(client, "/api/user/send-saturday-reminder")

    assert response.status_code == 200
    assert "Saturday expense reminder email sent to marcus@example.com" in response.get_json()["message"]
    sender.assert_called_once()
    assert sender.call_args[0][0] == "marcus@example.com"
