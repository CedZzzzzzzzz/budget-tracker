ALTER TABLE user_categories
ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';

ALTER TABLE user_categories
ADD COLUMN IF NOT EXISTS keywords TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

CREATE TABLE IF NOT EXISTS receipt_imports (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL,
    budget_id INTEGER NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    item_count INTEGER NOT NULL CHECK (item_count > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, idempotency_key),
    CHECK (char_length(idempotency_key) BETWEEN 16 AND 80)
);

CREATE INDEX IF NOT EXISTS idx_receipt_imports_user_created
ON receipt_imports(user_id, created_at DESC);
