from datetime import date
from unittest.mock import patch

from flask import Flask

from api.routes import api


def test_anomaly_endpoint_requires_authentication():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(api)

    response = app.test_client().get("/api/spending-anomalies")

    assert response.status_code == 401


def test_anomaly_endpoint_scopes_query_to_session_user():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(api)
    history = [
        {
            "item_id": item_id,
            "name": "Lunch",
            "amount": 100,
            "category": "food",
            "expense_date": date(2026, 7, 1),
            "is_current": False,
        }
        for item_id in range(1, 9)
    ]
    history.append({
        "item_id": 20,
        "name": "Celebration dinner",
        "amount": 600,
        "category": "food",
        "expense_date": date(2026, 7, 20),
        "is_current": True,
    })

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 42
        with (
            patch("api.routes.db.user_exists", return_value=True),
            patch("api.routes.get_week_range", return_value=(date(2026, 7, 19), date(2026, 7, 25))),
            patch("api.routes.db.get_spending_anomaly_candidates", return_value=history) as query,
        ):
            response = client.get("/api/spending-anomalies")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["window_days"] == 90
    assert payload["sample_size"] == 8
    assert payload["anomalies"][0]["item_id"] == 20
    query.assert_called_once_with(42, date(2026, 7, 19), date(2026, 7, 25), date(2026, 4, 20))


def test_anomaly_endpoint_returns_an_empty_report_for_no_history():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(api)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 7
        with (
            patch("api.routes.db.user_exists", return_value=True),
            patch("api.routes.get_week_range", return_value=(date(2026, 7, 19), date(2026, 7, 25))),
            patch("api.routes.db.get_spending_anomaly_candidates", return_value=[]),
        ):
            response = client.get("/api/spending-anomalies")

    assert response.status_code == 200
    assert response.get_json() == {
        "anomalies": [],
        "eligible_category_count": 0,
        "sample_size": 0,
        "window_days": 90,
    }
