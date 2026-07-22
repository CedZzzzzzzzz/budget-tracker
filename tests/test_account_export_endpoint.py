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


def test_account_export_requires_authentication():
    response = create_test_app().test_client().get("/api/account-export")
    assert response.status_code == 401


def test_account_export_returns_private_zip_for_session_user():
    app = create_test_app()
    snapshot = {
        "profile": {
            "username": "marcus",
            "email": "marcus@example.com",
            "created_at": "2026-01-01T00:00:00",
            "onboarding_completed": True,
        }
    }
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 42
        with (
            patch("api.routes.db.user_exists", return_value=True),
            patch("api.routes.db.get_account_export_snapshot", return_value=snapshot) as query,
        ):
            response = client.get("/api/account-export", buffered=True)

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert response.data.startswith(b"PK")
    assert response.headers["Cache-Control"] == "no-store"
    assert "budget-tracker-account-export-" in response.headers["Content-Disposition"]
    query.assert_called_once_with(42)
