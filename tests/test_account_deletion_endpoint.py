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


def authenticated_client():
    app = create_test_app()
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 42
        user_session["username"] = "marcus"
        user_session["csrf_token"] = "csrf-token"
    return client


def deletion_request(client, password="Password1!", confirmation="DELETE marcus", csrf=True):
    headers = {"X-CSRF-Token": "csrf-token"} if csrf else {}
    with patch("api.routes.db.user_exists", return_value=True):
        return client.delete(
            "/api/account",
            json={"current_password": password, "confirmation": confirmation},
            headers=headers,
        )


def test_account_deletion_requires_authentication():
    app = create_test_app()
    with app.test_client() as client:
        with client.session_transaction() as user_session:
            user_session["csrf_token"] = "csrf-token"
        response = deletion_request(client)

    assert response.status_code == 401


def test_account_deletion_requires_csrf():
    response = deletion_request(authenticated_client(), csrf=False)
    assert response.status_code == 403


def test_account_deletion_rejects_confirmation_without_query():
    client = authenticated_client()
    with patch("api.routes.db.delete_user_account") as delete_user:
        response = deletion_request(client, confirmation="delete marcus")

    assert response.status_code == 400
    assert response.get_json()["error"] == "Confirmation text does not match."
    delete_user.assert_not_called()


def test_account_deletion_rejects_wrong_password():
    client = authenticated_client()
    with patch("api.routes.db.delete_user_account", return_value="invalid_password") as delete_user:
        response = deletion_request(client, password="WrongPassword1!")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Current password is incorrect."
    delete_user.assert_called_once_with(42, "WrongPassword1!")


def test_account_deletion_clears_session_after_commit():
    client = authenticated_client()
    with patch("api.routes.db.delete_user_account", return_value="deleted") as delete_user:
        response = deletion_request(client)

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "message": "Account deleted."}
    delete_user.assert_called_once_with(42, "Password1!")
    with client.session_transaction() as user_session:
        assert "user_id" not in user_session
        assert "username" not in user_session
        assert "csrf_token" not in user_session


def test_deleted_account_session_is_rejected():
    client = authenticated_client()
    with patch("api.routes.db.user_exists", return_value=False):
        response = client.get("/api/profile")

    assert response.status_code == 401
    with client.session_transaction() as user_session:
        assert "user_id" not in user_session
