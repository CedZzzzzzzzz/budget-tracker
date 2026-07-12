ALTER TABLE users
    ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMP NULL;

UPDATE users
SET onboarding_completed_at = COALESCE(created_at, CURRENT_TIMESTAMP)
WHERE onboarding_completed_at IS NULL;
