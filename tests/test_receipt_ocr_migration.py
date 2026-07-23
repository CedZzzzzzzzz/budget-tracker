from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_receipt_migration_adds_category_metadata_and_idempotency():
    migration = (ROOT / "migrations" / "015_receipt_ocr_categories.sql").read_text(
        encoding="utf-8"
    ).lower()

    assert "add column if not exists description" in migration
    assert "add column if not exists keywords" in migration
    assert "create table if not exists receipt_imports" in migration
    assert "unique (user_id, idempotency_key)" in migration
    assert "on delete cascade" in migration
    assert "idx_receipt_imports_user_created" in migration


def test_receipt_migration_runs_after_admin_support_tools():
    runner = (ROOT / "migrations" / "runner.py").read_text(encoding="utf-8")

    support = runner.index('("015_admin_support_tools"')
    receipt = runner.index('("016_receipt_ocr_categories"')
    assert support < receipt
    assert '"015_receipt_ocr_categories.sql"' in runner


def test_receipt_batch_serializes_idempotency_per_user():
    database = (ROOT / "database.py").read_text(encoding="utf-8")
    function = database[database.index("def add_expense_items_batch"):database.index(
        "def delete_expense_item",
        database.index("def add_expense_items_batch"),
    )]

    user_lock = function.index("SELECT id FROM users WHERE id = %s FOR UPDATE")
    idempotency_lookup = function.index("SELECT budget_id, day FROM receipt_imports")
    assert user_lock < idempotency_lookup
