from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_support_migration_adds_session_email_and_security_contracts():
    migration = (ROOT / "migrations" / "014_admin_support_tools.sql").read_text(
        encoding="utf-8"
    ).lower()

    assert "add column if not exists session_version" in migration
    assert "add column if not exists sessions_revoked_at" in migration
    assert "create table if not exists auth_security_events" in migration
    assert "create table if not exists email_delivery_events" in migration
    assert "'resend_verification'" in migration
    assert "'send_password_reset'" in migration
    assert "'revoke_sessions'" in migration
    assert "idx_auth_security_events_user" in migration
    assert "idx_email_delivery_events_health" in migration


def test_admin_support_migration_runs_after_admin_dashboard():
    runner = (ROOT / "migrations" / "runner.py").read_text(encoding="utf-8")

    dashboard = runner.index('("014_admin_dashboard"')
    support = runner.index('("015_admin_support_tools"')
    assert dashboard < support
    assert '"014_admin_support_tools.sql"' in runner
