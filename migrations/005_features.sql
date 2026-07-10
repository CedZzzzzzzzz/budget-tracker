CREATE TABLE IF NOT EXISTS category_budget_limits (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    weekly_limit NUMERIC(12,2) NOT NULL CHECK (weekly_limit > 0),
    PRIMARY KEY (user_id, category)
);

CREATE TABLE IF NOT EXISTS recurring_expenses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    category TEXT NOT NULL,
    frequency TEXT NOT NULL CHECK (frequency IN ('weekly', 'monthly')),
    apply_day TEXT,
    apply_day_of_month INTEGER CHECK (apply_day_of_month BETWEEN 1 AND 31),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recurring_expense_applications (
    id SERIAL PRIMARY KEY,
    recurring_id INTEGER NOT NULL REFERENCES recurring_expenses(id) ON DELETE CASCADE,
    period_key TEXT NOT NULL,
    expense_item_id INTEGER REFERENCES expense_items(id) ON DELETE SET NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (recurring_id, period_key)
);

CREATE TABLE IF NOT EXISTS user_category_rules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pattern TEXT NOT NULL,
    category TEXT NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, pattern)
);

CREATE INDEX IF NOT EXISTS idx_recurring_expenses_user ON recurring_expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_user_category_rules_user ON user_category_rules(user_id);
