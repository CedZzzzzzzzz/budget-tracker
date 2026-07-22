from pathlib import Path


def test_account_deletion_migration_uses_cascades_and_indexes():
    migration = Path("migrations/011_account_deletion.sql").read_text(encoding="utf-8")

    assert "CONSTRAINT budgets_user_id_fkey" in migration
    assert "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE" in migration
    assert "CONSTRAINT expenses_budget_id_fkey" in migration
    assert "FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE" in migration
    assert "idx_password_reset_tokens_user" in migration
    assert "idx_recurring_applications_expense_item" in migration
