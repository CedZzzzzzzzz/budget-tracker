ALTER TABLE users
    ADD COLUMN IF NOT EXISTS session_version BIGINT NOT NULL DEFAULT 0;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS sessions_revoked_at TIMESTAMP NULL;

ALTER TABLE admin_audit_events
    DROP CONSTRAINT IF EXISTS admin_audit_events_action_check;

ALTER TABLE admin_audit_events
    ADD CONSTRAINT admin_audit_events_action_check CHECK (
        action IN (
            'grant_admin',
            'revoke_admin',
            'suspend_user',
            'reactivate_user',
            'resend_verification',
            'send_password_reset',
            'revoke_sessions'
        )
    );

CREATE TABLE IF NOT EXISTS auth_security_events (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'login_success',
            'login_failed',
            'password_reset_completed',
            'password_changed',
            'sessions_revoked'
        )
    ),
    outcome TEXT NOT NULL CHECK (outcome IN ('success', 'failed', 'denied')),
    source TEXT NOT NULL CHECK (source IN ('self_service', 'admin', 'system')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_delivery_events (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    email_type TEXT NOT NULL CHECK (
        email_type IN ('email_verification', 'password_reset')
    ),
    status TEXT NOT NULL CHECK (status IN ('queued', 'sent', 'failed')),
    source TEXT NOT NULL CHECK (source IN ('self_service', 'admin')),
    transport TEXT NOT NULL CHECK (
        transport IN ('api', 'smtp', 'development_log', 'unconfigured')
    ),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_security_events_user
    ON auth_security_events(user_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_auth_security_events_type
    ON auth_security_events(event_type, outcome, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_email_delivery_events_user
    ON email_delivery_events(user_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_email_delivery_events_health
    ON email_delivery_events(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_users_session_version
    ON users(id, session_version);
