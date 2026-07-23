from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_dashboard_migration_adds_roles_status_and_audit_contract():
    migration = (ROOT / "migrations" / "013_admin_dashboard.sql").read_text(encoding="utf-8").lower()

    assert "add column if not exists role" in migration
    assert "add column if not exists account_status" in migration
    assert "add column if not exists last_login_at" in migration
    assert "check (role in ('user', 'admin'))" in migration
    assert "check (account_status in ('active', 'suspended'))" in migration
    assert "create table if not exists admin_audit_events" in migration
    assert "actor_user_id integer references users(id) on delete set null" in migration
    assert "target_user_id integer references users(id) on delete set null" in migration
    assert "idx_users_admin_status" in migration
    assert "idx_admin_audit_events_created" in migration


def test_admin_dashboard_migration_is_registered_after_email_verification():
    runner = (ROOT / "migrations" / "runner.py").read_text(encoding="utf-8")

    verification = runner.index('("013_email_verification"')
    admin = runner.index('("014_admin_dashboard"')
    assert verification < admin
    assert '"013_admin_dashboard.sql"' in runner
