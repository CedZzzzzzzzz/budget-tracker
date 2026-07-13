CREATE TABLE IF NOT EXISTS user_categories (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    label TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#94a3b8',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_user_categories_user ON user_categories(user_id);

ALTER TABLE expense_items DROP CONSTRAINT IF EXISTS expense_items_category_check;
ALTER TABLE category_budget_limits DROP CONSTRAINT IF EXISTS category_budget_limits_category_check;
ALTER TABLE recurring_expenses DROP CONSTRAINT IF EXISTS recurring_expenses_category_check;
ALTER TABLE user_category_rules DROP CONSTRAINT IF EXISTS user_category_rules_category_check;
