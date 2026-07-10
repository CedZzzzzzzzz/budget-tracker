CREATE INDEX IF NOT EXISTS idx_budgets_user_id ON budgets(user_id);

CREATE INDEX IF NOT EXISTS idx_budgets_user_week ON budgets(user_id, week_start_date);

CREATE INDEX IF NOT EXISTS idx_expenses_budget_id ON expenses(budget_id);

CREATE INDEX IF NOT EXISTS idx_expenses_budget_date ON expenses(budget_id, expense_date);

CREATE INDEX IF NOT EXISTS idx_expense_items_expense_id ON expense_items(expense_id);
