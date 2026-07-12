from pathlib import Path

import psycopg2

import database as db

MIGRATION_DIR = Path(__file__).resolve().parent
MONEY_TYPE = db.MONEY_TYPE


def execute_sql_file(cursor, filename):
    path = MIGRATION_DIR / filename
    statements = [s.strip() for s in path.read_text(encoding="utf-8").split(";") if s.strip()]
    for statement in statements:
        cursor.execute(statement)


def migrate_expense_categories(cursor):
    from api.categorize import CATEGORIES

    for category in CATEGORIES:
        cursor.execute(
            f'ALTER TABLE expenses ADD COLUMN IF NOT EXISTS "{category}" {MONEY_TYPE} DEFAULT 0'
        )
    allowed = ", ".join("'%s'" % category for category in CATEGORIES)
    cursor.execute("ALTER TABLE expense_items DROP CONSTRAINT IF EXISTS expense_items_category_check")
    cursor.execute(
        f"ALTER TABLE expense_items ADD CONSTRAINT expense_items_category_check "
        f"CHECK (category IN ({allowed}))"
    )


def migrate_money_columns(cursor):
    from api.categorize import CATEGORIES

    tables_columns = [
        ("budgets", ("allowance",)),
        ("expense_items", ("amount",)),
        ("expenses", ("fare", "food", "other", "total", *CATEGORIES)),
    ]
    for table, columns in tables_columns:
        for column in columns:
            cursor.execute(
                f'ALTER TABLE {table} ALTER COLUMN "{column}" '
                f"TYPE {MONEY_TYPE} USING \"{column}\"::{MONEY_TYPE}"
            )


def migrate_feature_constraints(cursor):
    from api.categorize import CATEGORIES

    allowed = ", ".join("'%s'" % category for category in CATEGORIES)
    for table in ("category_budget_limits", "recurring_expenses", "user_category_rules"):
        cursor.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_category_check"
        )
        cursor.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_category_check "
            f"CHECK (category IN ({allowed}))"
        )


MIGRATIONS = [
    ("001_initial", lambda cursor: execute_sql_file(cursor, "001_initial.sql")),
    ("002_expense_categories", migrate_expense_categories),
    ("003_indexes", lambda cursor: execute_sql_file(cursor, "003_indexes.sql")),
    ("004_password_reset", lambda cursor: execute_sql_file(cursor, "004_password_reset.sql")),
    ("005_money_numeric", migrate_money_columns),
    ("006_features", lambda cursor: execute_sql_file(cursor, "005_features.sql")),
    ("006_features_constraints", migrate_feature_constraints),
    ("007_savings_goals", lambda cursor: execute_sql_file(cursor, "006_savings_goals.sql")),
    ("008_expense_notes_tags", lambda cursor: execute_sql_file(cursor, "007_expense_notes_tags.sql")),
    ("009_onboarding", lambda cursor: execute_sql_file(cursor, "008_onboarding.sql")),
]


def run_migrations():
    with db.db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row["version"] for row in cursor.fetchall()}

        for version, apply in MIGRATIONS:
            if version in applied:
                continue
            try:
                apply(cursor)
            except psycopg2.Error as error:
                if version == "005_money_numeric":
                    pass
                else:
                    raise error
            cursor.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
