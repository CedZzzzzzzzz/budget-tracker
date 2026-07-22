ALTER TABLE budgets
    DROP CONSTRAINT IF EXISTS budgets_user_id_fkey;

ALTER TABLE budgets
    ADD CONSTRAINT budgets_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE expenses
    DROP CONSTRAINT IF EXISTS expenses_budget_id_fkey;

ALTER TABLE expenses
    ADD CONSTRAINT expenses_budget_id_fkey
    FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user
    ON password_reset_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_recurring_applications_expense_item
    ON recurring_expense_applications(expense_item_id);
