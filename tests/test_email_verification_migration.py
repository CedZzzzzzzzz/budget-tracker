from pathlib import Path


def test_email_verification_migration_backfills_and_indexes_tokens():
    migration = Path("migrations/012_email_verification.sql").read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS email_verified_at" in migration
    assert "SET email_verified_at = COALESCE(created_at, CURRENT_TIMESTAMP)" in migration
    assert "CREATE TABLE IF NOT EXISTS email_verification_tokens" in migration
    assert "token_hash TEXT NOT NULL UNIQUE" in migration
    assert "REFERENCES users(id) ON DELETE CASCADE" in migration
    assert "idx_email_verification_tokens_user" in migration
