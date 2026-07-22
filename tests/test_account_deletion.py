from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

import database as db


def connection_with_user(password="Password1!"):
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": 42,
        "password_hash": generate_password_hash(password),
    }
    cursor.rowcount = 1
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


def test_delete_user_account_locks_and_deletes_user():
    connection, cursor = connection_with_user()
    with patch("database.db_connect", return_value=connection), patch("database.release_connection"):
        result = db.delete_user_account(42, "Password1!")

    assert result == "deleted"
    assert cursor.execute.call_args_list[0].args == (
        "SELECT id, password_hash FROM users WHERE id = %s FOR UPDATE",
        (42,),
    )
    assert cursor.execute.call_args_list[1].args == (
        "DELETE FROM users WHERE id = %s",
        (42,),
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    cursor.close.assert_called_once_with()


def test_delete_user_account_rolls_back_for_wrong_password():
    connection, cursor = connection_with_user()
    with patch("database.db_connect", return_value=connection), patch("database.release_connection"):
        result = db.delete_user_account(42, "WrongPassword1!")

    assert result == "invalid_password"
    assert cursor.execute.call_count == 1
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()


def test_delete_user_account_rolls_back_database_error():
    connection, cursor = connection_with_user()
    cursor.execute.side_effect = RuntimeError("database failure")
    with patch("database.db_connect", return_value=connection), patch("database.release_connection"):
        try:
            db.delete_user_account(42, "Password1!")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected database failure")

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
