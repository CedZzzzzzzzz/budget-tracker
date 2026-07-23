from datetime import datetime
from unittest.mock import patch

from flask import Flask

from api.routes import api
from extensions import limiter


def create_test_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        RATELIMIT_ENABLED=False,
        ADMIN_DASHBOARD_ENABLED=True,
    )
    app.secret_key = "test-secret"
    limiter.init_app(app)
    app.register_blueprint(api)
    return app


def authenticated_client():
    app = create_test_app()
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 42
        user_session["username"] = "admin-user"
        user_session["csrf_token"] = "csrf-token"
    return client


def auth_state(role="admin", status="active"):
    return {
        "id": 42,
        "username": "admin-user",
        "email_verified_at": datetime(2026, 7, 1),
        "onboarding_completed_at": datetime(2026, 7, 1),
        "role": role,
        "account_status": status,
    }


def admin_user(user_id=7, status="active", role="user"):
    return {
        "id": user_id,
        "username": "sample-user",
        "email": "sample@example.com",
        "role": role,
        "account_status": status,
        "email_verified_at": datetime(2026, 7, 2),
        "created_at": datetime(2026, 7, 1, 10, 30),
        "last_login_at": datetime(2026, 7, 21, 9, 15),
        "status_changed_at": None,
    }


def test_admin_endpoint_requires_authentication():
    app = create_test_app()
    response = app.test_client().get("/api/admin/overview")

    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store, max-age=0"


def test_admin_endpoint_denies_normal_user_even_when_navigation_is_bypassed():
    client = authenticated_client()
    with patch("api.routes.db.get_user_auth_state", return_value=auth_state(role="user")):
        response = client.get("/api/admin/overview")

    assert response.status_code == 403
    assert response.get_json()["error"] == "Administrator access required"


def test_admin_overview_returns_aggregate_metrics_only():
    client = authenticated_client()
    metrics = {
        "total_users": 10,
        "verified_users": 8,
        "unverified_users": 2,
        "active_users": 9,
        "suspended_users": 1,
        "new_users_7d": 2,
        "new_users_30d": 5,
        "logins_7d": 4,
        "logins_30d": 7,
    }
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch("api.routes.db.get_admin_overview", return_value=metrics),
    ):
        response = client.get("/api/admin/overview")

    assert response.status_code == 200
    assert response.get_json() == {"metrics": metrics}
    assert "password" not in response.get_data(as_text=True).lower()


def test_admin_user_directory_is_paginated_and_excludes_secrets():
    client = authenticated_client()
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch("api.routes.db.list_admin_users", return_value=([admin_user()], 1)) as query,
    ):
        response = client.get("/api/admin/users?q=sample&status=active&page=1&page_size=20")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["pagination"] == {"page": 1, "page_size": 20, "total": 1, "pages": 1}
    assert payload["users"][0]["username"] == "sample-user"
    assert payload["users"][0]["email_verified"] is True
    assert "password_hash" not in payload["users"][0]
    query.assert_called_once_with(
        query="sample",
        status="active",
        role="",
        page=1,
        page_size=20,
        sort="created_at",
        direction="desc",
    )


def test_admin_user_directory_rejects_unapproved_sort_before_query():
    client = authenticated_client()
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch("api.routes.db.list_admin_users") as query,
    ):
        response = client.get("/api/admin/users?sort=password_hash")

    assert response.status_code == 400
    query.assert_not_called()


def test_admin_mutation_requires_csrf():
    client = authenticated_client()
    with patch("api.routes.db.get_user_auth_state", return_value=auth_state()):
        response = client.post(
            "/api/admin/users/7/suspend",
            json={"current_password": "Password1!", "reason": "Compromised account"},
        )

    assert response.status_code == 403


def test_admin_can_suspend_user_with_password_and_reason():
    client = authenticated_client()
    updated = admin_user(status="suspended")
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch(
            "api.routes.db.change_user_account_status",
            return_value={"status": "updated", "user": updated},
        ) as change_status,
    ):
        response = client.post(
            "/api/admin/users/7/suspend",
            json={"current_password": "Password1!", "reason": "Compromised account"},
            headers={"X-CSRF-Token": "csrf-token"},
        )

    assert response.status_code == 200
    assert response.get_json()["user"]["account_status"] == "suspended"
    change_status.assert_called_once()
    args = change_status.call_args.args
    assert args[:5] == (42, 7, "Password1!", "suspended", "Compromised account")


def test_wrong_admin_password_is_denied_and_never_returned():
    client = authenticated_client()
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch(
            "api.routes.db.change_user_account_status",
            return_value={"status": "invalid_password"},
        ),
        patch("api.routes.db.record_admin_audit_event") as audit,
    ):
        response = client.post(
            "/api/admin/users/7/reactivate",
            json={"current_password": "WrongPassword1!", "reason": "Support review complete"},
            headers={"X-CSRF-Token": "csrf-token"},
        )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Current password is incorrect."
    assert "WrongPassword1!" not in response.get_data(as_text=True)
    audit.assert_called_once()
    assert audit.call_args.args[1] is None


def test_suspended_account_is_blocked_after_correct_password():
    app = create_test_app()
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["csrf_token"] = "csrf-token"
    user = {
        "id": 8,
        "username": "suspended-user",
        "email": "user@example.com",
        "password_hash": "unused",
        "email_verified_at": datetime(2026, 7, 1),
        "account_status": "suspended",
        "role": "user",
    }
    with (
        patch("api.routes.db.get_user_by_username", return_value=user),
        patch("api.routes.db.verify_password", return_value=True),
        patch("api.routes.db.mark_user_login") as mark_login,
    ):
        response = client.post(
            "/api/login",
            json={"username": "suspended-user", "password": "Password1!"},
            headers={"X-CSRF-Token": "csrf-token"},
        )

    assert response.status_code == 403
    assert response.get_json()["error"] == "This account is currently unavailable."
    mark_login.assert_not_called()


def test_admin_user_detail_returns_security_metadata_without_secrets():
    client = authenticated_client()
    history = [{
        "id": 9,
        "category": "authentication",
        "event_type": "login_failed",
        "outcome": "failed",
        "source": "self_service",
        "detail": "",
        "created_at": datetime(2026, 7, 22, 10, 0),
        "actor_username": None,
    }]
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch("api.routes.db.get_admin_user_detail", return_value=admin_user()),
        patch("api.routes.db.list_user_security_history", return_value=history),
    ):
        response = client.get("/api/admin/users/7")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["user"]["username"] == "sample-user"
    assert payload["security_events"][0]["event_type"] == "login_failed"
    assert "password_hash" not in response.get_data(as_text=True)
    assert "token" not in response.get_data(as_text=True).lower()


def test_admin_can_resend_verification_after_reauthentication():
    client = authenticated_client()
    target = admin_user()
    target["email_verified_at"] = None
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch(
            "api.routes.db.authorize_admin_user_action",
            return_value={"status": "authorized", "user": target},
        ),
        patch("api.routes.deliver_verification_email", return_value=True) as deliver,
        patch("api.routes.db.email_delivery_on_cooldown", return_value=False),
        patch("api.routes.mail_configured", return_value=True),
        patch("api.routes.db.record_admin_audit_event") as audit,
    ):
        response = client.post(
            "/api/admin/users/7/resend-verification",
            json={"current_password": "Password1!", "reason": "User requested support"},
            headers={"X-CSRF-Token": "csrf-token"},
        )

    assert response.status_code == 200
    assert response.get_json()["delivery_status"] == "queued"
    deliver.assert_called_once_with(
        7,
        "sample@example.com",
        source="admin",
        actor_user_id=42,
    )
    assert audit.call_args.args[2:4] == ("resend_verification", "success")
    assert "Password1!" not in response.get_data(as_text=True)


def test_admin_can_send_password_reset_without_receiving_token():
    client = authenticated_client()
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch(
            "api.routes.db.authorize_admin_user_action",
            return_value={"status": "authorized", "user": admin_user()},
        ),
        patch("api.routes.deliver_password_reset_email", return_value=True) as deliver,
        patch("api.routes.db.email_delivery_on_cooldown", return_value=False),
        patch("api.routes.mail_configured", return_value=True),
        patch("api.routes.db.record_admin_audit_event"),
    ):
        response = client.post(
            "/api/admin/users/7/send-password-reset",
            json={"current_password": "Password1!", "reason": "Account recovery request"},
            headers={"X-CSRF-Token": "csrf-token"},
        )

    assert response.status_code == 200
    assert set(response.get_json()) == {"success", "message", "delivery_status"}
    deliver.assert_called_once()
    assert "token" not in response.get_data(as_text=True).lower()


def test_admin_can_force_sign_out_and_receives_minimal_user_metadata():
    client = authenticated_client()
    updated = {**admin_user(), "sessions_revoked_at": datetime(2026, 7, 22, 12, 0)}
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch(
            "api.routes.db.revoke_user_sessions",
            return_value={"status": "updated", "user": updated},
        ) as revoke,
    ):
        response = client.post(
            "/api/admin/users/7/revoke-sessions",
            json={"current_password": "Password1!", "reason": "Compromised session review"},
            headers={"X-CSRF-Token": "csrf-token"},
        )

    assert response.status_code == 200
    assert response.get_json()["user"]["sessions_revoked_at"] is not None
    revoke.assert_called_once()
    assert "session_version" not in response.get_data(as_text=True)


def test_admin_audit_history_validates_and_forwards_filters():
    client = authenticated_client()
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch("api.routes.db.list_admin_audit_events", return_value=([], 0)) as audit_query,
    ):
        response = client.get(
            "/api/admin/audit-events?q=sample&action=revoke_sessions&outcome=success"
            "&source=web&date_from=2026-07-01&date_to=2026-07-22"
        )

    assert response.status_code == 200
    forwarded = audit_query.call_args.kwargs
    assert forwarded["query"] == "sample"
    assert forwarded["action"] == "revoke_sessions"
    assert forwarded["outcome"] == "success"
    assert forwarded["source"] == "web"
    assert forwarded["date_from"] == datetime(2026, 7, 1)
    assert forwarded["date_to"] == datetime(2026, 7, 23)


def test_admin_system_health_exposes_status_without_email_credentials():
    client = authenticated_client()
    health = {
        "authentication": {
            "login_success_24h": 4,
            "login_failed_24h": 1,
            "sessions_revoked_24h": 1,
        },
        "email": {
            "queued_24h": 0,
            "sent_24h": 3,
            "failed_24h": 0,
            "last_delivery_at": datetime(2026, 7, 22, 12, 0),
        },
        "database": {
            "migration_count": 15,
            "latest_migration": "015_admin_support_tools",
            "latest_migration_at": datetime(2026, 7, 22, 11, 0),
        },
    }
    with (
        patch("api.routes.db.get_user_auth_state", return_value=auth_state()),
        patch("api.routes.db.get_admin_system_health", return_value=health),
        patch("api.routes.mail_configured", return_value=True),
        patch("api.routes.delivery_transport_name", return_value="api"),
    ):
        response = client.get("/api/admin/system-health")

    assert response.status_code == 200
    body = response.get_data(as_text=True).lower()
    assert response.get_json()["health"]["email"]["transport"] == "api"
    assert "database" not in response.get_json()["health"]
    assert "smtp_password" not in body
    assert "api_key" not in body


def test_revoked_admin_session_is_rejected():
    client = authenticated_client()
    state = {**auth_state(), "session_version": 2}
    with patch("api.routes.db.get_user_auth_state", return_value=state):
        response = client.get("/api/admin/overview")

    assert response.status_code == 401
