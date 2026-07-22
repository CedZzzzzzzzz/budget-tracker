import json
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from zipfile import ZipFile

import database
from api.account_export import build_account_export


EXPECTED_FILES = {
    "manifest.json",
    "account-summary.pdf",
    "profile.json",
    "budgets.csv",
    "expense-items.csv",
    "custom-categories.json",
    "category-limits.json",
    "recurring-expenses.json",
    "savings-goals.json",
    "income-sources.json",
    "category-rules.json",
}


def sample_snapshot():
    return {
        "profile": {
            "username": "marcus",
            "email": "marcus@example.com",
            "created_at": datetime(2026, 1, 2, 3, 4, 5),
            "onboarding_completed": True,
            "password_hash": "secret-password-hash",
            "reset_token": "secret-reset-token",
        },
        "budgets": [{
            "week_start_date": date(2026, 7, 19),
            "week_end_date": date(2026, 7, 25),
            "allowance": Decimal("2500.00"),
            "created_at": datetime(2026, 7, 19, 8, 0),
        }],
        "expense_items": [{
            "expense_date": date(2026, 7, 19),
            "day": "Sunday",
            "name": "=SUM(A1:A2)",
            "category": "food",
            "amount": Decimal("260.50"),
            "notes": "Café with Ana",
            "tags": ["gcash", "friends"],
            "created_at": datetime(2026, 7, 19, 9, 0),
        }],
        "custom_categories": [{"slug": "health", "label": "Health", "color": "#10b981"}],
        "category_limits": [{"category": "food", "weekly_limit": Decimal("1000.00")}],
        "recurring_expenses": [{
            "name": "Rent", "amount": Decimal("5000.00"), "category": "bills",
            "frequency": "monthly", "apply_day": None, "apply_day_of_month": 1,
            "active": True, "created_at": datetime(2026, 1, 1),
        }],
        "recurring_applications": [{
            "recurring_name": "Rent", "period_key": "2026-07", "applied_at": datetime(2026, 7, 1),
            "expense_item_name": "Rent", "expense_date": date(2026, 7, 1),
        }],
        "savings_goals": [{
            "name": "Laptop", "target_amount": Decimal("50000.00"),
            "current_amount": Decimal("10000.00"), "deadline": date(2026, 12, 31),
            "status": "active", "created_at": datetime(2026, 1, 1),
            "updated_at": datetime(2026, 7, 1),
        }],
        "income_sources": [{
            "label": "Allowance", "amount": Decimal("2500.00"), "active": True,
            "sort_order": 0, "created_at": datetime(2026, 1, 1), "updated_at": datetime(2026, 1, 1),
        }],
        "category_rules": [{
            "pattern": "jeep", "category": "fare", "hit_count": 3,
            "updated_at": datetime(2026, 7, 1),
        }],
    }


def test_archive_contains_versioned_files_and_unicode_data():
    archive, manifest = build_account_export(
        sample_snapshot(),
        exported_at=datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc),
    )
    try:
        with ZipFile(archive) as bundle:
            assert set(bundle.namelist()) == EXPECTED_FILES
            stored_manifest = json.loads(bundle.read("manifest.json"))
            assert stored_manifest == manifest
            assert stored_manifest["schema_version"] == 1
            assert stored_manifest["exported_at"] == "2026-07-22T04:00:00Z"
            expense_csv = bundle.read("expense-items.csv")
            assert expense_csv.startswith(b"\xef\xbb\xbf")
            expense_text = expense_csv.decode("utf-8-sig")
            assert "Café with Ana" in expense_text
            assert "'=SUM(A1:A2)" in expense_text
            summary_pdf = bundle.read("account-summary.pdf")
            assert summary_pdf.startswith(b"%PDF")
            assert b"%%EOF" in summary_pdf[-32:]
    finally:
        archive.close()


def test_archive_excludes_sensitive_and_internal_fields():
    snapshot = sample_snapshot()
    snapshot["custom_categories"][0]["id"] = 999
    archive, manifest = build_account_export(snapshot)
    try:
        with ZipFile(archive) as bundle:
            content = b"\n".join(bundle.read(name) for name in bundle.namelist())
        assert b"secret-password-hash" not in content
        assert b"secret-reset-token" not in content
        assert b"password_hash" not in content
        assert b"reset_token" not in content
        assert b'"id"' not in content
        assert manifest["schema_version"] == 1
    finally:
        archive.close()


def test_empty_snapshot_creates_every_file():
    archive, manifest = build_account_export({})
    try:
        with ZipFile(archive) as bundle:
            assert set(bundle.namelist()) == EXPECTED_FILES
            assert bundle.read("budgets.csv").decode("utf-8-sig").startswith("Week Start")
            counts = {file["name"]: file["records"] for file in manifest["files"]}
            assert counts["account-summary.pdf"] == 1
            assert all(count == 0 for name, count in counts.items() if name != "account-summary.pdf")
    finally:
        archive.close()


def test_database_snapshot_scopes_every_query_to_user():
    executions = []
    state = {"query": ""}

    def execute(query, params=None):
        state["query"] = query
        executions.append((query, params))

    def fetchone():
        if "FROM users" in state["query"]:
            return {
                "username": "marcus",
                "email": "marcus@example.com",
                "created_at": datetime(2026, 1, 1),
                "onboarding_completed_at": datetime(2026, 1, 2),
            }
        return None

    def fetchall():
        return []

    cursor = SimpleNamespace(execute=execute, fetchone=fetchone, fetchall=fetchall)

    @contextmanager
    def fake_transaction(**options):
        assert options == {"dict_cursor": True}
        yield cursor

    original_transaction = database.db_transaction
    database.db_transaction = fake_transaction
    try:
        snapshot = database.get_account_export_snapshot(42)
    finally:
        database.db_transaction = original_transaction

    assert snapshot["profile"]["username"] == "marcus"
    assert executions[0][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    user_queries = executions[1:]
    assert len(user_queries) == 10
    assert all(params == (42,) for query, params in user_queries)
    assert all("user_id = %s" in query or "WHERE id = %s" in query for query, params in user_queries)
