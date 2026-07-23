from unittest.mock import patch

from flask import Flask

from api.routes import api
from extensions import limiter


def create_test_app(receipt_enabled=True):
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        RATELIMIT_ENABLED=False,
        RECEIPT_OCR_ENABLED=receipt_enabled,
    )
    app.secret_key = "test-secret"
    limiter.init_app(app)
    app.register_blueprint(api)
    return app


def authenticated_client(receipt_enabled=True):
    client = create_test_app(receipt_enabled).test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 42
        user_session["username"] = "marcus"
        user_session["session_version"] = 0
        user_session["csrf_token"] = "csrf-token"
    return client


def csrf_headers(extra=None):
    return {"X-CSRF-Token": "csrf-token", **(extra or {})}


def test_receipt_extraction_disabled_returns_503():
    client = authenticated_client(receipt_enabled=False)
    with patch("api.routes.db.user_exists", return_value=True):
        response = client.post(
            "/api/receipt-scans/extract",
            headers=csrf_headers(),
        )

    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store, max-age=0"


def test_receipt_extraction_returns_editable_draft():
    client = authenticated_client()
    extracted = {
        "merchant": "Sample Market",
        "purchase_date": "2026-07-23",
        "currency": "PHP",
        "total": 90.0,
        "reconciled": True,
        "mode": "total",
        "items": [{
            "name": "Milk",
            "amount": 90.0,
            "category": "groceries",
            "confidence": 0.9,
            "source": "keyword_score",
            "needs_review": False,
        }],
        "warnings": [],
        "image": {"width": 600, "height": 900, "input_bytes": 1000},
    }
    with (
        patch("api.routes.db.user_exists", return_value=True),
        patch("api.routes.db.get_user_categories", return_value=[]),
        patch("api.routes.db.get_user_category_rules", return_value=[]),
        patch("api.routes.extract_receipt", return_value=extracted),
    ):
        response = client.post(
            "/api/receipt-scans/extract",
            data={"receipt": (io_bytes(), "receipt.jpg")},
            headers=csrf_headers(),
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    assert response.get_json()["items"][0]["category"] == "groceries"
    assert response.headers["Cache-Control"] == "no-store, max-age=0"


def io_bytes():
    import io
    return io.BytesIO(b"image")


def test_batch_save_requires_idempotency_key():
    client = authenticated_client()
    with patch("api.routes.db.user_exists", return_value=True):
        response = client.post(
            "/api/expense-items/batch",
            json={"day": "Thursday", "items": []},
            headers=csrf_headers(),
        )

    assert response.status_code == 400
    assert "idempotency" in response.get_json()["error"].lower()


def test_batch_save_rejects_non_finite_amount():
    client = authenticated_client()
    with (
        patch("api.routes.db.user_exists", return_value=True),
        patch("api.routes.db.allowed_category_slugs", return_value=["groceries", "other"]),
    ):
        response = client.post(
            "/api/expense-items/batch",
            json={
                "day": "Thursday",
                "items": [{
                    "name": "Milk",
                    "amount": "NaN",
                    "category": "groceries",
                }],
            },
            headers=csrf_headers({
                "Idempotency-Key": "d13a7e4b-d2e1-4ec9-a50a-ff9f84fbf8fd",
            }),
        )

    assert response.status_code == 400
    assert "amount" in response.get_json()["error"].lower()


def test_batch_save_is_atomic_service_call():
    client = authenticated_client()
    result = {
        "duplicate": False,
        "day": "Thursday",
        "expense": {"total": 90.0, "items": []},
        "totals": {"groceries": 90.0, "spent": 90.0, "remaining": 910.0},
        "items": [{"id": 1, "name": "Milk", "amount": 90.0, "category": "groceries"}],
    }
    with (
        patch("api.routes.db.user_exists", return_value=True),
        patch("api.routes.db.allowed_category_slugs", return_value=["groceries", "other"]),
        patch("api.routes.db.get_budget_by_week", return_value={"id": 7}),
        patch("api.routes.db.add_expense_items_batch", return_value=result) as add_batch,
        patch("api.routes.db.learn_category_correction"),
        patch("api.routes.db.get_category_limits", return_value={}),
        patch("api.routes.db.build_category_status", return_value={}),
        patch("api.routes.db.get_user_category_rules", return_value=[]),
        patch("api.routes.db.get_user_categories", return_value=[]),
    ):
        response = client.post(
            "/api/expense-items/batch",
            json={
                "day": "Thursday",
                "items": [{
                    "name": "Milk",
                    "amount": 90,
                    "category": "groceries",
                    "notes": "",
                    "tags": [],
                }],
            },
            headers=csrf_headers({
                "Idempotency-Key": "d13a7e4b-d2e1-4ec9-a50a-ff9f84fbf8fd",
            }),
        )

    assert response.status_code == 200
    assert response.get_json()["duplicate"] is False
    add_batch.assert_called_once()
