import calendar
import hashlib
import os
import secrets
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

MONEY_TYPE = "NUMERIC(12,2)"
MAX_USERNAME_LEN = 50
MAX_EMAIL_LEN = 255
MAX_ITEM_NAME_LEN = 200

GMAIL_DOMAINS = frozenset({"gmail.com", "googlemail.com"})
db_pool = None
CONNECT_TIMEOUT = int(os.environ.get("DATABASE_CONNECT_TIMEOUT", "30"))
CONNECT_RETRIES = int(os.environ.get("DATABASE_CONNECT_RETRIES", "5"))
CONNECT_RETRY_DELAY = float(os.environ.get("DATABASE_CONNECT_RETRY_DELAY", "2"))


def normalize_database_url(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params.pop("channel_binding", None)
    if "sslmode" not in params:
        params["sslmode"] = ["require"]
    query = urlencode({key: values[0] for key, values in params.items()})
    return urlunparse(parsed._replace(query=query))


def as_float(value):
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def ensure_pooler_host(url):
    if "-pooler" in url or ".neon.tech" not in url:
        return url
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host.endswith(".neon.tech") and "-pooler" not in host:
        pooler_host = f"{host}-pooler"
        netloc = parsed.netloc.replace(host, pooler_host, 1)
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def get_database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")
    if os.environ.get("DATABASE_USE_POOLER", "true").strip().lower() in ("1", "true", "yes", "on"):
        url = ensure_pooler_host(url)
    return normalize_database_url(url)


def get_connection_pool():
    global db_pool
    if db_pool is None:
        db_pool = pool.ThreadedConnectionPool(
            minconn=0,
            maxconn=int(os.environ.get("DATABASE_POOL_MAX", "10")),
            dsn=get_database_url(),
            connect_timeout=CONNECT_TIMEOUT,
        )
    return db_pool


def db_connect():
    last_error = None
    for attempt in range(CONNECT_RETRIES):
        try:
            return get_connection_pool().getconn()
        except psycopg2.OperationalError as error:
            last_error = error
            if attempt < CONNECT_RETRIES - 1:
                time.sleep(CONNECT_RETRY_DELAY * (attempt + 1))
    raise last_error


def release_connection(conn):
    get_connection_pool().putconn(conn)


@contextmanager
def db_cursor(*, dict_cursor=False, commit=False):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        cursor.close()
        release_connection(conn)


@contextmanager
def db_transaction(*, dict_cursor=False):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        release_connection(conn)


def get_db():
    return db_connect()


def clean_email(email):
    return email.strip().lower().strip("\t\n\r")


def normalize_email(email):
    email = clean_email(email)
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if domain in GMAIL_DOMAINS:
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def init_db():
    from migrations.runner import run_migrations

    run_migrations()
    print("Database Initialized.")
    warmup_pool()


def warmup_pool():
    try:
        with db_cursor() as cursor:
            cursor.execute("SELECT 1")
    except psycopg2.Error:
        pass


def create_user(username, email, password):
    try:
        with db_cursor(commit=True) as cursor:
            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (username, normalize_email(email), password_hash),
            )
            return cursor.fetchone()[0]
    except psycopg2.IntegrityError:
        return None


def get_user_by_id(user_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None


def get_user_by_username(username):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        return dict(user) if user else None


def get_user_by_email(email):
    email = clean_email(email)
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            "SELECT * FROM users WHERE LOWER(btrim(email, E' \\t\\n\\r')) = LOWER(btrim(%s, E' \\t\\n\\r'))",
            (email,),
        )
        user = cursor.fetchone()
        if user:
            return dict(user)

        _, _, domain = email.partition("@")
        if domain in GMAIL_DOMAINS:
            needle = normalize_email(email)
            cursor.execute(
                "SELECT * FROM users WHERE LOWER(split_part(btrim(email, E' \\t\\n\\r'), '@', 2)) "
                "IN ('gmail.com', 'googlemail.com')"
            )
            for row in cursor.fetchall():
                if normalize_email(row["email"]) == needle:
                    return dict(row)
    return None


def verify_password(user, password):
    return check_password_hash(user["password_hash"], password)


def hash_reset_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


def invalidate_password_reset_tokens(user_id):
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            'UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP '
            'WHERE user_id = %s AND used_at IS NULL',
            (user_id,),
        )


def create_password_reset_token(user_id):
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    invalidate_password_reset_tokens(user_id)
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            'INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) '
            'VALUES (%s, %s, %s)',
            (user_id, token_hash, expires_at),
        )
    return raw_token


def consume_password_reset_token(raw_token):
    token_hash = hash_reset_token(raw_token)
    with db_transaction(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT id, user_id FROM password_reset_tokens '
            'WHERE token_hash = %s AND used_at IS NULL AND expires_at > CURRENT_TIMESTAMP',
            (token_hash,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        cursor.execute(
            'UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP WHERE id = %s',
            (row['id'],),
        )
        return row['user_id']


def update_user_password(user_id, password):
    with db_cursor(commit=True) as cursor:
        password_hash = generate_password_hash(password)
        cursor.execute(
            'UPDATE users SET password_hash = %s WHERE id = %s',
            (password_hash, user_id),
        )
        return cursor.rowcount > 0


def update_user_profile(user_id, username=None, email=None):
    updates = []
    params = []
    if username is not None:
        updates.append("username = %s")
        params.append(username)
    if email is not None:
        updates.append("email = %s")
        params.append(normalize_email(email))
    if not updates:
        return True
    params.append(user_id)
    try:
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = %s",
                params,
            )
            return cursor.rowcount > 0
    except psycopg2.IntegrityError:
        return False


def create_budget(user_id, week_start, week_end, allowance):
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "INSERT INTO budgets (user_id, week_start_date, week_end_date, allowance) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, week_start, week_end, allowance),
        )
        return cursor.fetchone()[0]


def update_budget(budget_id, user_id, allowance):
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            'UPDATE budgets SET allowance = %s WHERE id = %s AND user_id = %s',
            (allowance, budget_id, user_id),
        )
        return cursor.rowcount > 0


def get_budget_by_week(user_id, week_start, week_end):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute('''
            SELECT id, user_id, week_start_date, week_end_date, allowance, created_at
            FROM budgets
            WHERE user_id = %s AND week_start_date = %s AND week_end_date = %s
        ''', (user_id, week_start, week_end))
        budget = cursor.fetchone()
        return dict(budget) if budget else None


def empty_category_breakdown():
    from api.categorize import CATEGORIES
    return {c: 0.0 for c in CATEGORIES}


def breakdown_from_items(items):
    from api.categorize import CATEGORIES
    breakdown = empty_category_breakdown()
    for item in items:
        category = item.get("category", "other")
        if category in breakdown:
            breakdown[category] += as_float(item.get("amount", 0))
    return breakdown


def breakdown_from_row(row, items):
    from api.categorize import CATEGORIES
    if items:
        return breakdown_from_items(items)
    return {c: as_float(row.get(c, 0)) for c in CATEGORIES}


def category_sum_select_sql(item_alias="ei"):
    from api.categorize import CATEGORIES
    return ", ".join(
        f"COALESCE(SUM(CASE WHEN {item_alias}.category = '{c}' "
        f"THEN {item_alias}.amount ELSE 0 END), 0) AS \"{c}\""
        for c in CATEGORIES
    )


def legacy_category_sum_select_sql(expense_alias="e"):
    from api.categorize import CATEGORIES
    return ", ".join(
        f'COALESCE(SUM({expense_alias}."{c}"), 0) AS "{c}"' for c in CATEGORIES
    )


def merge_breakdown_rows(primary, legacy):
    from api.categorize import CATEGORIES
    merged = empty_category_breakdown()
    for category in CATEGORIES:
        merged[category] = as_float(primary.get(category, 0)) + as_float(legacy.get(category, 0))
    return merged


def query_budget_category_breakdown(cursor, budget_id):
    from api.categorize import CATEGORIES

    cursor.execute(
        f'SELECT {category_sum_select_sql()} '
        f'FROM expense_items ei JOIN expenses e ON ei.expense_id = e.id '
        f'WHERE e.budget_id = %s',
        (budget_id,),
    )
    item_row = cursor.fetchone() or {}
    cursor.execute(
        f'SELECT {legacy_category_sum_select_sql()} FROM expenses e '
        f'WHERE e.budget_id = %s '
        f'AND NOT EXISTS (SELECT 1 FROM expense_items ei WHERE ei.expense_id = e.id)',
        (budget_id,),
    )
    legacy_row = cursor.fetchone() or {}
    return merge_breakdown_rows(item_row, legacy_row)


def query_user_category_breakdown(cursor, user_id, start_date, end_date):
    cursor.execute(
        f'SELECT {category_sum_select_sql()} '
        f'FROM expense_items ei '
        f'JOIN expenses e ON ei.expense_id = e.id '
        f'JOIN budgets b ON e.budget_id = b.id '
        f'WHERE b.user_id = %s AND e.expense_date >= %s AND e.expense_date < %s',
        (user_id, start_date, end_date),
    )
    item_row = cursor.fetchone() or {}
    cursor.execute(
        f'SELECT {legacy_category_sum_select_sql()} FROM expenses e '
        f'JOIN budgets b ON e.budget_id = b.id '
        f'WHERE b.user_id = %s AND e.expense_date >= %s AND e.expense_date < %s '
        f'AND NOT EXISTS (SELECT 1 FROM expense_items ei WHERE ei.expense_id = e.id)',
        (user_id, start_date, end_date),
    )
    legacy_row = cursor.fetchone() or {}
    return merge_breakdown_rows(item_row, legacy_row)


def expense_select_columns_legacy():
    from api.categorize import CATEGORIES
    cols = ["id", "budget_id", "day", "expense_date", "total", *CATEGORIES]
    return ", ".join(
        c if c in ("id", "budget_id", "day", "expense_date", "total") else f'"{c}"'
        for c in cols
    )


def get_expenses_by_budget(budget_id):
    cols = expense_select_columns_legacy()
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(f'''
            SELECT {cols}
            FROM expenses
            WHERE budget_id = %s
            ORDER BY CASE day
                WHEN 'Sunday' THEN 1
                WHEN 'Monday' THEN 2
                WHEN 'Tuesday' THEN 3
                WHEN 'Wednesday' THEN 4
                WHEN 'Thursday' THEN 5
                WHEN 'Friday' THEN 6
                WHEN 'Saturday' THEN 7
            END
        ''', (budget_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_expense_by_day(budget_id, day):
    cols = expense_select_columns_legacy()
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            f'SELECT {cols} FROM expenses WHERE budget_id = %s AND day = %s',
            (budget_id, day),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_items_by_expense(expense_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT id, expense_id, name, amount, category, created_at '
            'FROM expense_items WHERE expense_id = %s ORDER BY created_at',
            (expense_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_items_by_budget(budget_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute('''
            SELECT ei.id, ei.expense_id, ei.name, ei.amount, ei.category, e.day
            FROM expense_items ei
            JOIN expenses e ON ei.expense_id = e.id
            WHERE e.budget_id = %s
            ORDER BY ei.created_at
        ''', (budget_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_items_grouped_by_expense_id(budget_id):
    grouped = {}
    for item in get_items_by_budget(budget_id):
        expense_id = item['expense_id']
        grouped.setdefault(expense_id, []).append({
            'id': item['id'],
            'name': item['name'],
            'amount': as_float(item['amount']),
            'category': item['category'],
        })
    return grouped


def fetch_week_budget(user_id, week_start, week_end):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute('''
            SELECT id, allowance
            FROM budgets
            WHERE user_id = %s AND week_start_date = %s AND week_end_date = %s
        ''', (user_id, week_start, week_end))
        budget = cursor.fetchone()
        if not budget:
            return None, [], {}

        rows, grouped = query_week_expenses(cursor, budget['id'])
        return dict(budget), rows, grouped


EXPENSE_DAY_ORDER = '''
    ORDER BY CASE day
        WHEN 'Sunday' THEN 1
        WHEN 'Monday' THEN 2
        WHEN 'Tuesday' THEN 3
        WHEN 'Wednesday' THEN 4
        WHEN 'Thursday' THEN 5
        WHEN 'Friday' THEN 6
        WHEN 'Saturday' THEN 7
    END
'''


def query_week_expenses(cursor, budget_id):
    cursor.execute(f'''
        SELECT id, day, total
        FROM expenses
        WHERE budget_id = %s
        {EXPENSE_DAY_ORDER}
    ''', (budget_id,))
    rows = [dict(row) for row in cursor.fetchall()]

    cursor.execute('''
        SELECT ei.id, ei.expense_id, ei.name, ei.amount, ei.category
        FROM expense_items ei
        JOIN expenses e ON ei.expense_id = e.id
        WHERE e.budget_id = %s
        ORDER BY ei.created_at
    ''', (budget_id,))
    grouped = {}
    for item in cursor.fetchall():
        grouped.setdefault(item['expense_id'], []).append({
            'id': item['id'],
            'name': item['name'],
            'amount': as_float(item['amount']),
            'category': item['category'],
        })
    return rows, grouped


def week_snapshot_from_budget_rows(budget, rows, items_by_expense, week_start, week_end):
    from api.categorize import CATEGORIES

    empty_row = {"spent": 0, "days_logged": 0, **{c: 0 for c in CATEGORIES}}
    if not budget:
        return week_snapshot_from_row(None, empty_row, week_start, week_end)

    cat_totals = empty_category_breakdown()
    days_logged = 0
    for row in rows:
        items = items_by_expense.get(row['id'], [])
        breakdown = breakdown_from_row(row, items)
        if as_float(row['total']) > 0:
            days_logged += 1
        for category in cat_totals:
            cat_totals[category] += breakdown[category]
    spent = sum(cat_totals.values())
    summary_row = {"spent": spent, "days_logged": days_logged, **cat_totals}
    return week_snapshot_from_row(budget, summary_row, week_start, week_end)


def week_snapshot_with_cursor(cursor, user_id, week_start, week_end):
    from api.categorize import CATEGORIES

    cursor.execute('''
        SELECT id, allowance FROM budgets
        WHERE user_id = %s AND week_start_date = %s AND week_end_date = %s
    ''', (user_id, week_start, week_end))
    budget = cursor.fetchone()
    empty_row = {"spent": 0, "days_logged": 0, **{c: 0 for c in CATEGORIES}}
    if not budget:
        return week_snapshot_from_row(None, empty_row, week_start, week_end)

    cursor.execute(
        'SELECT COALESCE(SUM(total), 0) AS spent, '
        'COUNT(*) FILTER (WHERE total > 0) AS days_logged '
        'FROM expenses WHERE budget_id = %s',
        (budget['id'],),
    )
    summary = cursor.fetchone()
    breakdown = query_budget_category_breakdown(cursor, budget['id'])
    row = {**summary, **breakdown}
    return week_snapshot_from_row(dict(budget), row, week_start, week_end)


def build_week_comparison(current, previous):
    spent_delta = current["spent"] - previous["spent"]
    allowance_delta = current["allowance"] - previous["allowance"]
    pct_change = None
    if previous["has_budget"] and previous["spent"] > 0:
        pct_change = round((spent_delta / previous["spent"]) * 100, 1)
    return {
        "current": current,
        "previous": previous,
        "delta": {
            "spent": spent_delta,
            "allowance": allowance_delta,
            "spent_pct_change": pct_change,
        },
    }


def fetch_dashboard(user_id, week_start, week_end):
    prev_start = week_start - timedelta(days=7)
    prev_end = week_end - timedelta(days=7)
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute('''
            SELECT id, allowance
            FROM budgets
            WHERE user_id = %s AND week_start_date = %s AND week_end_date = %s
        ''', (user_id, week_start, week_end))
        budget = cursor.fetchone()
        if not budget:
            previous = week_snapshot_with_cursor(cursor, user_id, prev_start, prev_end)
            current = week_snapshot_from_budget_rows(None, [], {}, week_start, week_end)
            return None, [], {}, build_week_comparison(current, previous)

        budget = dict(budget)
        rows, grouped = query_week_expenses(cursor, budget['id'])
        current = week_snapshot_from_budget_rows(budget, rows, grouped, week_start, week_end)
        previous = week_snapshot_with_cursor(cursor, user_id, prev_start, prev_end)
        return budget, rows, grouped, build_week_comparison(current, previous)


def get_monthly_summary(user_id, start_date, end_date):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute('''
            SELECT b.id, b.week_start_date, b.week_end_date, b.allowance,
                COALESCE(SUM(e.total), 0) AS total_spent
            FROM budgets b
            LEFT JOIN expenses e ON b.id = e.budget_id
            WHERE b.user_id = %s AND b.week_start_date >= %s AND b.week_start_date < %s
            GROUP BY b.id
            ORDER BY b.week_start_date
        ''', (user_id, start_date, end_date))
        weeks = [dict(row) for row in cursor.fetchall()]
        breakdown = query_user_category_breakdown(cursor, user_id, start_date, end_date)

    return weeks, breakdown


def get_budgets_by_month(user_id, start_date, end_date):
    weeks, _ = get_monthly_summary(user_id, start_date, end_date)
    return weeks


def get_monthly_expense_breakdown(user_id, start_date, end_date):
    _, breakdown = get_monthly_summary(user_id, start_date, end_date)
    return breakdown


def delete_expense_by_day(budget_id, day):
    with db_transaction(dict_cursor=True) as cursor:
        cursor.execute('DELETE FROM expenses WHERE budget_id = %s AND day = %s RETURNING id', (budget_id, day))
        deleted = cursor.fetchone() is not None
        budget_totals = compute_budget_totals(cursor, budget_id) if deleted else None
        return deleted, budget_totals


def expense_item_belongs_to_user(item_id, user_id):
    with db_cursor() as cursor:
        cursor.execute('''
            SELECT 1
            FROM expense_items ei
            JOIN expenses e ON ei.expense_id = e.id
            JOIN budgets b ON e.budget_id = b.id
            WHERE ei.id = %s AND b.user_id = %s
        ''', (item_id, user_id))
        return cursor.fetchone() is not None


def update_expense_total(cursor, expense_id):
    cursor.execute(
        'SELECT COALESCE(SUM(amount), 0) AS total FROM expense_items WHERE expense_id = %s',
        (expense_id,),
    )
    row = cursor.fetchone()
    total = as_float(row['total'] if isinstance(row, dict) else row[0])
    cursor.execute('UPDATE expenses SET total = %s WHERE id = %s', (total, expense_id))
    return total


def day_expense_payload(cursor, expense_id):
    cols = expense_select_columns_legacy()
    cursor.execute(f'SELECT {cols} FROM expenses WHERE id = %s', (expense_id,))
    row = cursor.fetchone()
    if not row:
        return None
    cursor.execute(
        'SELECT id, name, amount, category FROM expense_items '
        'WHERE expense_id = %s ORDER BY created_at',
        (expense_id,),
    )
    items = [{
        "id": item["id"],
        "name": item["name"],
        "amount": as_float(item["amount"]),
        "category": item["category"],
    } for item in cursor.fetchall()]
    breakdown = breakdown_from_row(row, items)
    return {
        **breakdown,
        "total": as_float(row["total"]),
        "items": items,
    }


def compute_budget_totals(cursor, budget_id):
    breakdown = query_budget_category_breakdown(cursor, budget_id)
    cursor.execute(
        'SELECT COALESCE(SUM(total), 0) AS spent FROM expenses WHERE budget_id = %s',
        (budget_id,),
    )
    spent_row = cursor.fetchone()
    spent = as_float(spent_row['spent'] if isinstance(spent_row, dict) else spent_row[0])
    cursor.execute('SELECT allowance FROM budgets WHERE id = %s', (budget_id,))
    allowance_row = cursor.fetchone()
    allowance = as_float(
        allowance_row['allowance'] if isinstance(allowance_row, dict) else allowance_row[0]
    )
    return {**breakdown, "spent": spent, "remaining": allowance - spent}


def add_expense_item(budget_id, day, expense_date, name, amount, category):
    with db_transaction(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT id FROM expenses WHERE budget_id = %s AND day = %s',
            (budget_id, day),
        )
        row = cursor.fetchone()
        if row:
            expense_id = row['id']
        else:
            cursor.execute('''
                INSERT INTO expenses (budget_id, day, expense_date, fare, food, other, total)
                VALUES (%s, %s, %s, 0, 0, 0, 0)
                RETURNING id
            ''', (budget_id, day, expense_date))
            expense_id = cursor.fetchone()['id']

        cursor.execute('''
            INSERT INTO expense_items (expense_id, name, amount, category)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        ''', (expense_id, name, amount, category))
        item = dict(cursor.fetchone())
        update_expense_total(cursor, expense_id)
        day_expense = day_expense_payload(cursor, expense_id)
        budget_totals = compute_budget_totals(cursor, budget_id)
        return item, day, day_expense, budget_totals


def delete_expense_item(item_id, user_id):
    if not expense_item_belongs_to_user(item_id, user_id):
        return False, None, None, None, None

    with db_transaction(dict_cursor=True) as cursor:
        cursor.execute('''
            SELECT ei.expense_id, ei.name, ei.amount, ei.category, e.day, e.budget_id
            FROM expense_items ei
            JOIN expenses e ON ei.expense_id = e.id
            WHERE ei.id = %s
        ''', (item_id,))
        row = cursor.fetchone()
        if not row:
            return False, None, None, None, None

        deleted_item = {
            'name': row['name'],
            'amount': as_float(row['amount']),
            'category': row['category'],
        }
        expense_id = row['expense_id']
        day = row['day']
        budget_id = row['budget_id']
        cursor.execute('DELETE FROM expense_items WHERE id = %s', (item_id,))
        cursor.execute('SELECT COUNT(*) AS count FROM expense_items WHERE expense_id = %s', (expense_id,))
        remaining = cursor.fetchone()['count']

        if remaining == 0:
            cursor.execute('DELETE FROM expenses WHERE id = %s', (expense_id,))
            budget_totals = compute_budget_totals(cursor, budget_id)
            return True, day, None, budget_totals, deleted_item

        update_expense_total(cursor, expense_id)
        day_expense = day_expense_payload(cursor, expense_id)
        budget_totals = compute_budget_totals(cursor, budget_id)
        return True, day, day_expense, budget_totals, deleted_item


def fetch_export_rows(user_id, start_date, end_date):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute('''
            SELECT e.expense_date, e.day, ei.name, ei.category, ei.amount
            FROM expense_items ei
            JOIN expenses e ON ei.expense_id = e.id
            JOIN budgets b ON e.budget_id = b.id
            WHERE b.user_id = %s AND e.expense_date >= %s AND e.expense_date < %s
            ORDER BY e.expense_date, ei.created_at
        ''', (user_id, start_date, end_date))
        return [
            {
                'expense_date': row['expense_date'],
                'day': row['day'],
                'name': row['name'],
                'category': row['category'],
                'amount': as_float(row['amount']),
            }
            for row in cursor.fetchall()
        ]


def update_expense_item(item_id, user_id, name, amount, category):
    if not expense_item_belongs_to_user(item_id, user_id):
        return None, None, None, None

    with db_transaction(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT ei.expense_id, e.day, e.budget_id '
            'FROM expense_items ei JOIN expenses e ON ei.expense_id = e.id '
            'WHERE ei.id = %s',
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None, None, None, None

        expense_id = row['expense_id']
        day = row['day']
        budget_id = row['budget_id']
        cursor.execute('''
            UPDATE expense_items
            SET name = %s, amount = %s, category = %s
            WHERE id = %s
            RETURNING *
        ''', (name, amount, category, item_id))
        item = dict(cursor.fetchone())
        update_expense_total(cursor, expense_id)
        day_expense = day_expense_payload(cursor, expense_id)
        budget_totals = compute_budget_totals(cursor, budget_id)
        return item, day, day_expense, budget_totals


def week_snapshot_from_row(budget, row, week_start, week_end):
    from api.categorize import CATEGORIES

    if not budget:
        return {
            "week_start": str(week_start),
            "week_end": str(week_end),
            "allowance": 0.0,
            "spent": 0.0,
            "remaining": 0.0,
            "days_logged": 0,
            "breakdown": {c: 0.0 for c in CATEGORIES},
            "has_budget": False,
        }

    spent = as_float(row["spent"])
    allowance = as_float(budget["allowance"])
    return {
        "week_start": str(week_start),
        "week_end": str(week_end),
        "allowance": allowance,
        "spent": spent,
        "remaining": allowance - spent,
        "days_logged": int(row["days_logged"]),
        "breakdown": {c: as_float(row[c]) for c in CATEGORIES},
        "has_budget": True,
    }


def get_week_snapshot(user_id, week_start, week_end):
    from api.categorize import CATEGORIES

    budget = get_budget_by_week(user_id, week_start, week_end)
    empty_row = {"spent": 0, "days_logged": 0, **{c: 0 for c in CATEGORIES}}
    if not budget:
        return week_snapshot_from_row(None, empty_row, week_start, week_end)

    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT COALESCE(SUM(total), 0) AS spent, '
            'COUNT(*) FILTER (WHERE total > 0) AS days_logged '
            'FROM expenses WHERE budget_id = %s',
            (budget["id"],),
        )
        summary = cursor.fetchone()
        breakdown = query_budget_category_breakdown(cursor, budget["id"])
        row = {**summary, **breakdown}
    return week_snapshot_from_row(budget, row, week_start, week_end)


def get_week_comparison(user_id, week_start, week_end):
    prev_start = week_start - timedelta(days=7)
    prev_end = week_end - timedelta(days=7)
    with db_cursor(dict_cursor=True) as cursor:
        current = week_snapshot_with_cursor(cursor, user_id, week_start, week_end)
        previous = week_snapshot_with_cursor(cursor, user_id, prev_start, prev_end)
    return build_week_comparison(current, previous)


DAY_NAME_TO_OFFSET = {
    "Sunday": 0, "Monday": 1, "Tuesday": 2, "Wednesday": 3,
    "Thursday": 4, "Friday": 5, "Saturday": 6,
}


def week_range_for_date(d):
    week_start = d - timedelta(days=(d.weekday() + 1) % 7)
    return week_start, week_start + timedelta(days=6)


def get_budget_id_for_week(cursor, user_id, week_start, week_end):
    cursor.execute(
        'SELECT id FROM budgets '
        'WHERE user_id = %s AND week_start_date = %s AND week_end_date = %s',
        (user_id, week_start, week_end),
    )
    row = cursor.fetchone()
    return row['id'] if row else None


def get_user_category_rules(user_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT pattern, category, hit_count FROM user_category_rules '
            'WHERE user_id = %s ORDER BY hit_count DESC, updated_at DESC',
            (user_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def learn_category_correction(user_id, name, category):
    from api.categorize import CATEGORIES, categorize_item, extract_learn_patterns

    if category not in CATEGORIES:
        return
    user_rules = get_user_category_rules(user_id)
    suggested = categorize_item(name, user_rules)
    if suggested == category:
        return

    patterns = extract_learn_patterns(name)
    if not patterns:
        return

    with db_cursor(commit=True) as cursor:
        for pattern in patterns:
            cursor.execute(
                'INSERT INTO user_category_rules (user_id, pattern, category) '
                'VALUES (%s, %s, %s) '
                'ON CONFLICT (user_id, pattern) DO UPDATE SET '
                'category = EXCLUDED.category, '
                'hit_count = user_category_rules.hit_count + 1, '
                'updated_at = CURRENT_TIMESTAMP',
                (user_id, pattern, category),
            )


def get_category_limits(user_id):
    from api.categorize import CATEGORIES

    limits = {category: None for category in CATEGORIES}
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT category, weekly_limit FROM category_budget_limits WHERE user_id = %s',
            (user_id,),
        )
        for row in cursor.fetchall():
            if row['category'] in limits:
                limits[row['category']] = as_float(row['weekly_limit'])
    return limits


def set_category_limits(user_id, limits):
    from api.categorize import CATEGORIES

    with db_cursor(commit=True) as cursor:
        for category, limit in limits.items():
            if category not in CATEGORIES:
                continue
            if limit is None or limit <= 0:
                cursor.execute(
                    'DELETE FROM category_budget_limits WHERE user_id = %s AND category = %s',
                    (user_id, category),
                )
            else:
                cursor.execute(
                    'INSERT INTO category_budget_limits (user_id, category, weekly_limit) '
                    'VALUES (%s, %s, %s) '
                    'ON CONFLICT (user_id, category) DO UPDATE SET weekly_limit = EXCLUDED.weekly_limit',
                    (user_id, category, limit),
                )


def build_category_status(totals, limits):
    from api.categorize import CATEGORIES

    status = {}
    for category in CATEGORIES:
        spent = as_float(totals.get(category, 0))
        limit = limits.get(category)
        if limit is None or limit <= 0:
            status[category] = {
                "spent": spent,
                "limit": None,
                "pct": None,
                "over": False,
                "warning": False,
            }
            continue
        pct = round((spent / limit) * 100, 1) if limit else None
        status[category] = {
            "spent": spent,
            "limit": limit,
            "pct": pct,
            "over": spent > limit,
            "warning": spent >= limit * 0.8 and spent <= limit,
        }
    return status


def get_recurring_expenses(user_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT id, name, amount, category, frequency, apply_day, apply_day_of_month, active '
            'FROM recurring_expenses WHERE user_id = %s ORDER BY created_at',
            (user_id,),
        )
        return [{
            **dict(row),
            "amount": as_float(row["amount"]),
            "active": bool(row["active"]),
        } for row in cursor.fetchall()]


def get_recurring_expense(recurring_id, user_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT id, name, amount, category, frequency, apply_day, apply_day_of_month, active '
            'FROM recurring_expenses WHERE id = %s AND user_id = %s',
            (recurring_id, user_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            **dict(row),
            "amount": as_float(row["amount"]),
            "active": bool(row["active"]),
        }


def create_recurring_expense(user_id, name, amount, category, frequency, apply_day=None, apply_day_of_month=None):
    with db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            'INSERT INTO recurring_expenses '
            '(user_id, name, amount, category, frequency, apply_day, apply_day_of_month) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id',
            (user_id, name, amount, category, frequency, apply_day, apply_day_of_month),
        )
        return cursor.fetchone()['id']


def update_recurring_expense(recurring_id, user_id, **fields):
    allowed = {'name', 'amount', 'category', 'frequency', 'apply_day', 'apply_day_of_month', 'active'}
    updates = []
    params = []
    for key, value in fields.items():
        if key in allowed and value is not None:
            updates.append(f'{key} = %s')
            params.append(value)
    if not updates:
        return False
    params.extend([recurring_id, user_id])
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            f'UPDATE recurring_expenses SET {", ".join(updates)} '
            f'WHERE id = %s AND user_id = %s',
            params,
        )
        return cursor.rowcount > 0


def delete_recurring_expense(recurring_id, user_id):
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            'DELETE FROM recurring_expenses WHERE id = %s AND user_id = %s',
            (recurring_id, user_id),
        )
        return cursor.rowcount > 0


def recurring_day_name(expense_date, week_start):
    offset = (expense_date - week_start).days
    for day, day_offset in DAY_NAME_TO_OFFSET.items():
        if day_offset == offset:
            return day
    return "Sunday"


def add_expense_item_with_cursor(cursor, budget_id, day, expense_date, name, amount, category):
    cursor.execute(
        'SELECT id FROM expenses WHERE budget_id = %s AND day = %s',
        (budget_id, day),
    )
    row = cursor.fetchone()
    if row:
        expense_id = row['id']
    else:
        cursor.execute(
            'INSERT INTO expenses (budget_id, day, expense_date, fare, food, other, total) '
            'VALUES (%s, %s, %s, 0, 0, 0, 0) RETURNING id',
            (budget_id, day, expense_date),
        )
        expense_id = cursor.fetchone()['id']

    cursor.execute(
        'INSERT INTO expense_items (expense_id, name, amount, category) '
        'VALUES (%s, %s, %s, %s) RETURNING id',
        (expense_id, name, amount, category),
    )
    item_id = cursor.fetchone()['id']
    update_expense_total(cursor, expense_id)
    return item_id


def recurring_already_applied(cursor, recurring_id, period_key):
    cursor.execute(
        'SELECT 1 FROM recurring_expense_applications '
        'WHERE recurring_id = %s AND period_key = %s',
        (recurring_id, period_key),
    )
    return cursor.fetchone() is not None


def log_recurring_application(cursor, recurring_id, period_key, expense_item_id):
    cursor.execute(
        'INSERT INTO recurring_expense_applications (recurring_id, period_key, expense_item_id) '
        'VALUES (%s, %s, %s)',
        (recurring_id, period_key, expense_item_id),
    )


def process_recurring_expenses(user_id, week_start, week_end):
    today = date.today()
    changed = False
    with db_transaction(dict_cursor=True) as cursor:
        cursor.execute(
            'SELECT id, name, amount, category, frequency, apply_day, apply_day_of_month '
            'FROM recurring_expenses WHERE user_id = %s AND active = TRUE',
            (user_id,),
        )
        recurring_items = cursor.fetchall()

        for rec in recurring_items:
            if rec['frequency'] == 'weekly':
                period_key = str(week_start)
                day = rec['apply_day'] or 'Sunday'
                day_offset = DAY_NAME_TO_OFFSET.get(day, 0)
                expense_date = week_start + timedelta(days=day_offset)
                if today < expense_date:
                    continue
                if recurring_already_applied(cursor, rec['id'], period_key):
                    continue
                budget_id = get_budget_id_for_week(cursor, user_id, week_start, week_end)
                if not budget_id:
                    continue
                item_id = add_expense_item_with_cursor(
                    cursor,
                    budget_id,
                    day,
                    expense_date,
                    rec['name'],
                    rec['amount'],
                    rec['category'],
                )
                log_recurring_application(cursor, rec['id'], period_key, item_id)
                changed = True
            elif rec['frequency'] == 'monthly':
                period_key = f'{today.year}-{today.month:02d}'
                dom = rec['apply_day_of_month'] or 1
                last_day = calendar.monthrange(today.year, today.month)[1]
                dom = min(dom, last_day)
                expense_date = date(today.year, today.month, dom)
                if today < expense_date:
                    continue
                if recurring_already_applied(cursor, rec['id'], period_key):
                    continue
                billing_week_start, billing_week_end = week_range_for_date(expense_date)
                budget_id = get_budget_id_for_week(
                    cursor, user_id, billing_week_start, billing_week_end,
                )
                if not budget_id:
                    continue
                day = recurring_day_name(expense_date, billing_week_start)
                item_id = add_expense_item_with_cursor(
                    cursor,
                    budget_id,
                    day,
                    expense_date,
                    rec['name'],
                    rec['amount'],
                    rec['category'],
                )
                log_recurring_application(cursor, rec['id'], period_key, item_id)
                changed = True

    return changed
