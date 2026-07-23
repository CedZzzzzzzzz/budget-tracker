from datetime import datetime
from unittest.mock import MagicMock, patch

from werkzeug.security import check_password_hash, generate_password_hash

import database as db


def transaction_with_cursor(cursor):
    transaction = MagicMock()
    transaction.return_value.__enter__.return_value = cursor
    return transaction


def test_terminal_admin_creation_hashes_password_verifies_email_and_audits():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"id": 77}
    with patch("database.db_transaction", transaction_with_cursor(cursor)):
        result = db.create_admin_user(
            "terminal-admin",
            "Admin.Example@example.com",
            "Password1!",
        )

    assert result == {"status": "created", "user_id": 77}
    insert_sql, insert_params = cursor.execute.call_args_list[0].args
    assert "'admin', 'active', CURRENT_TIMESTAMP" in insert_sql
    assert insert_params[0] == "terminal-admin"
    assert insert_params[1] == "admin.example@example.com"
    assert insert_params[2] != "Password1!"
    assert check_password_hash(insert_params[2], "Password1!")
    audit_sql, audit_params = cursor.execute.call_args_list[1].args
    assert "INSERT INTO admin_audit_events" in audit_sql
    assert audit_params[0] == 77
    assert "Password1!" not in repr(cursor.execute.call_args_list)


def target_user(status="active"):
    return {
        "id": 7,
        "username": "sample-user",
        "email": "sample@example.com",
        "role": "user",
        "account_status": status,
        "email_verified_at": datetime(2026, 7, 1),
        "created_at": datetime(2026, 7, 1),
        "last_login_at": None,
        "status_changed_at": None,
    }


def test_status_change_locks_actor_and_target_then_writes_audit():
    cursor = MagicMock()
    updated = target_user(status="suspended")
    cursor.fetchone.side_effect = [
        {
            "id": 42,
            "password_hash": generate_password_hash("Password1!"),
            "role": "admin",
            "account_status": "active",
        },
        target_user(),
        updated,
    ]
    with patch("database.db_transaction", transaction_with_cursor(cursor)):
        result = db.change_user_account_status(
            42,
            7,
            "Password1!",
            "suspended",
            "  Compromised\naccount  ",
            request_id="request-1",
        )

    assert result == {"status": "updated", "user": updated}
    assert "FOR UPDATE" in cursor.execute.call_args_list[0].args[0]
    assert "FOR UPDATE" in cursor.execute.call_args_list[1].args[0]
    assert "UPDATE users SET account_status" in cursor.execute.call_args_list[2].args[0]
    audit_sql, audit_params = cursor.execute.call_args_list[3].args
    assert "INSERT INTO admin_audit_events" in audit_sql
    assert audit_params == (42, 7, "suspend_user", "Compromised account", "request-1")
    assert "Password1!" not in repr(cursor.execute.call_args_list)


def test_status_change_rejects_wrong_admin_password_before_target_lookup():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": 42,
        "password_hash": generate_password_hash("Password1!"),
        "role": "admin",
        "account_status": "active",
    }
    with patch("database.db_transaction", transaction_with_cursor(cursor)):
        result = db.change_user_account_status(
            42,
            7,
            "WrongPassword1!",
            "suspended",
            "Compromised account",
        )

    assert result == {"status": "invalid_password"}
    assert cursor.execute.call_count == 1


def test_status_change_protects_admin_accounts():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        {
            "id": 42,
            "password_hash": generate_password_hash("Password1!"),
            "role": "admin",
            "account_status": "active",
        },
        {**target_user(), "role": "admin"},
    ]
    with patch("database.db_transaction", transaction_with_cursor(cursor)):
        result = db.change_user_account_status(
            42,
            7,
            "Password1!",
            "suspended",
            "Administrative review",
        )

    assert result == {"status": "admin_target"}
    assert cursor.execute.call_count == 2


def test_operator_command_cannot_revoke_last_active_admin():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        {"id": 42, "username": "admin-user", "role": "admin", "account_status": "active"},
        {"total": 1},
    ]
    with patch("database.db_transaction", transaction_with_cursor(cursor)):
        result = db.set_admin_role("admin-user", False)

    assert result == "last_admin"
    assert cursor.execute.call_count == 3
    assert "pg_advisory_xact_lock" in cursor.execute.call_args_list[0].args[0]


def test_force_sign_out_increments_session_version_and_audits():
    cursor = MagicMock()
    updated = {**target_user(), "sessions_revoked_at": datetime(2026, 7, 22, 12, 0)}
    cursor.fetchone.side_effect = [
        {
            "id": 42,
            "password_hash": generate_password_hash("Password1!"),
            "role": "admin",
            "account_status": "active",
        },
        {"id": 7, "role": "user"},
        updated,
    ]
    with patch("database.db_transaction", transaction_with_cursor(cursor)):
        result = db.revoke_user_sessions(
            42,
            7,
            "Password1!",
            "Compromised session review",
            request_id="request-2",
        )

    assert result == {"status": "updated", "user": updated}
    assert "session_version = session_version + 1" in cursor.execute.call_args_list[2].args[0]
    assert "INSERT INTO auth_security_events" in cursor.execute.call_args_list[3].args[0]
    assert "INSERT INTO admin_audit_events" in cursor.execute.call_args_list[4].args[0]
    assert "Password1!" not in repr(cursor.execute.call_args_list)
