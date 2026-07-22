ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP NULL;

UPDATE users
SET email_verified_at = COALESCE(created_at, CURRENT_TIMESTAMP)
WHERE email_verified_at IS NULL;

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_email_verification_tokens_user
    ON email_verification_tokens(user_id);
