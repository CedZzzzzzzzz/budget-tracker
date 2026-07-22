import hashlib
from unittest.mock import MagicMock, patch

import database as db


def transaction_with_cursor(cursor):
    transaction = MagicMock()
    transaction.return_value.__enter__.return_value = cursor
    return transaction


def test_create_verification_token_hashes_and_replaces_active_token():
    cursor = MagicMock()
    transaction = transaction_with_cursor(cursor)
    raw_token = "raw-verification-token"
    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with (
        patch("database.db_transaction", transaction),
        patch("database.secrets.token_urlsafe", return_value=raw_token),
    ):
        result = db.create_email_verification_token(42)

    assert result == raw_token
    assert cursor.execute.call_args_list[0].args[1] == (42,)
    insert_params = cursor.execute.call_args_list[1].args[1]
    assert insert_params[0] == 42
    assert insert_params[1] == expected_hash
    assert raw_token not in insert_params


def test_consume_verification_token_verifies_user_and_invalidates_tokens():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": 8,
        "user_id": 42,
        "used_at": None,
        "active": True,
        "email_verified_at": None,
    }
    with patch("database.db_transaction", transaction_with_cursor(cursor)):
        result = db.consume_email_verification_token("raw-token")

    assert result == "verified"
    assert cursor.execute.call_count == 3
    assert cursor.execute.call_args_list[1].args[1] == (42,)
    assert cursor.execute.call_args_list[2].args[1] == (42,)


def test_consume_verification_token_rejects_expired_token():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": 8,
        "user_id": 42,
        "used_at": None,
        "active": False,
        "email_verified_at": None,
    }
    with patch("database.db_transaction", transaction_with_cursor(cursor)):
        result = db.consume_email_verification_token("expired-token")

    assert result == "invalid"
    assert cursor.execute.call_count == 1


def test_consumed_token_is_safe_for_already_verified_account():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": 8,
        "user_id": 42,
        "used_at": object(),
        "active": False,
        "email_verified_at": object(),
    }
    with patch("database.db_transaction", transaction_with_cursor(cursor)):
        result = db.consume_email_verification_token("used-token")

    assert result == "verified"
    assert cursor.execute.call_count == 1
