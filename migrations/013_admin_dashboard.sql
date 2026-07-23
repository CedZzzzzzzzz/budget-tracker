ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS account_status TEXT NOT NULL DEFAULT 'active';

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP NULL;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMP NULL;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users
    ADD CONSTRAINT users_role_check CHECK (role IN ('user', 'admin'));

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_account_status_check;
ALTER TABLE users
    ADD CONSTRAINT users_account_status_check
    CHECK (account_status IN ('active', 'suspended'));

CREATE TABLE IF NOT EXISTS admin_audit_events (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    target_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (
        action IN ('grant_admin', 'revoke_admin', 'suspend_user', 'reactivate_user')
    ),
    outcome TEXT NOT NULL CHECK (outcome IN ('success', 'denied')),
    reason VARCHAR(250) NOT NULL DEFAULT '',
    source TEXT NOT NULL CHECK (source IN ('web', 'operator_cli')),
    request_id VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_admin_status
    ON users(role, account_status, id);

CREATE INDEX IF NOT EXISTS idx_users_created_at
    ON users(created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_users_last_login_at
    ON users(last_login_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_admin_audit_events_created
    ON admin_audit_events(created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_admin_audit_events_actor
    ON admin_audit_events(actor_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_audit_events_target
    ON admin_audit_events(target_user_id, created_at DESC);
