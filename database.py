import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

def get_database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")
    return url


def db_connect():
    return psycopg2.connect(get_database_url(), connect_timeout=10)


DATABASE_URL = os.environ.get("DATABASE_URL")

MAX_USERNAME_LEN = 50
MAX_EMAIL_LEN = 255
MAX_ITEM_NAME_LEN = 200

_GMAIL_DOMAINS = frozenset({"gmail.com", "googlemail.com"})


def clean_email(email):
    return email.strip().lower().strip("\t\n\r")


def normalize_email(email):
    email = clean_email(email)
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if domain in _GMAIL_DOMAINS:
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def get_db():
    conn = db_connect()
    return conn

def init_db():
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            week_start_date DATE NOT NULL,
            week_end_date DATE NOT NULL,
            allowance REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, week_start_date, week_end_date)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            budget_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            expense_date DATE NOT NULL,
            fare REAL DEFAULT 0,
            food REAL DEFAULT 0,
            other REAL DEFAULT 0,
            total REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (budget_id) REFERENCES budgets(id),
            UNIQUE(budget_id, day)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expense_items (
            id SERIAL PRIMARY KEY,
            expense_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
        )
    ''')

    from api.categorize import CATEGORIES

    for cat in CATEGORIES:
        cursor.execute(
            f'ALTER TABLE expenses ADD COLUMN IF NOT EXISTS "{cat}" REAL DEFAULT 0'
        )

    allowed = ", ".join("'%s'" % c for c in CATEGORIES)
    cursor.execute('ALTER TABLE expense_items DROP CONSTRAINT IF EXISTS expense_items_category_check')
    cursor.execute(
        f'ALTER TABLE expense_items ADD CONSTRAINT expense_items_category_check '
        f'CHECK (category IN ({allowed}))'
    )

    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_budgets_user_id ON budgets(user_id)'
    )
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_expenses_budget_id ON expenses(budget_id)'
    )
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_expense_items_expense_id ON expense_items(expense_id)'
    )

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_password_reset_token_hash '
        'ON password_reset_tokens(token_hash)'
    )

    conn.commit()
    conn.close()
    print("Database Initialized.")

def create_user(username, email, password):
    try:
        conn = db_connect()
        cursor = conn.cursor()
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (username, normalize_email(email), password_hash)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return user_id
    except psycopg2.IntegrityError:
        return None

def get_user_by_username(username):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_email(email):
    email = clean_email(email)
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        "SELECT * FROM users WHERE LOWER(btrim(email, E' \\t\\n\\r')) = LOWER(btrim(%s, E' \\t\\n\\r'))",
        (email,),
    )
    user = cursor.fetchone()
    if user:
        conn.close()
        return dict(user)

    _, _, domain = email.partition("@")
    if domain in _GMAIL_DOMAINS:
        needle = normalize_email(email)
        cursor.execute(
            "SELECT * FROM users WHERE LOWER(split_part(btrim(email, E' \\t\\n\\r'), '@', 2)) "
            "IN ('gmail.com', 'googlemail.com')"
        )
        for row in cursor.fetchall():
            if normalize_email(row["email"]) == needle:
                conn.close()
                return dict(row)

    conn.close()
    return None

def verify_password(user, password):
    return check_password_hash(user["password_hash"], password)


def hash_reset_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


def invalidate_password_reset_tokens(user_id):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP '
        'WHERE user_id = %s AND used_at IS NULL',
        (user_id,),
    )
    conn.commit()
    conn.close()


def create_password_reset_token(user_id):
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    invalidate_password_reset_tokens(user_id)
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) '
        'VALUES (%s, %s, %s)',
        (user_id, token_hash, expires_at),
    )
    conn.commit()
    conn.close()
    return raw_token


def consume_password_reset_token(raw_token):
    token_hash = hash_reset_token(raw_token)
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        'SELECT id, user_id FROM password_reset_tokens '
        'WHERE token_hash = %s AND used_at IS NULL AND expires_at > CURRENT_TIMESTAMP',
        (token_hash,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    cursor.execute(
        'UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP WHERE id = %s',
        (row['id'],),
    )
    conn.commit()
    conn.close()
    return row['user_id']


def update_user_password(user_id, password):
    conn = db_connect()
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)
    cursor.execute(
        'UPDATE users SET password_hash = %s WHERE id = %s',
        (password_hash, user_id),
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def create_budget(user_id, week_start, week_end, allowance):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO budgets (user_id, week_start_date, week_end_date, allowance) VALUES (%s, %s, %s, %s) RETURNING id",
        (user_id, week_start, week_end, allowance)
    )
    budget_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return budget_id

def update_budget(budget_id, user_id, allowance):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE budgets SET allowance = %s WHERE id = %s AND user_id = %s',
        (allowance, budget_id, user_id),
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_budget_by_week(user_id, week_start, week_end):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT * FROM budgets
        WHERE user_id = %s AND week_start_date = %s AND week_end_date = %s
    ''', (user_id, week_start, week_end))
    budget = cursor.fetchone()
    conn.close()
    return dict(budget) if budget else None

def get_budgets_by_month(user_id, start_date, end_date):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT b.id, b.week_start_date, b.week_end_date, b.allowance,
            COALESCE(SUM(e.total), 0) AS total_spent
        FROM budgets b
        LEFT JOIN expenses e ON b.id = e.budget_id
        WHERE b.user_id = %s AND b.week_start_date >= %s AND b.week_start_date < %s
        GROUP BY b.id
        ORDER BY b.week_start_date
    ''', (user_id, start_date, end_date))
    budgets = cursor.fetchall()
    conn.close()
    return [dict(row) for row in budgets]

def get_monthly_expense_breakdown(user_id, start_date, end_date):
    from api.categorize import CATEGORIES

    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    selects = ", ".join(f'COALESCE(SUM(e."{c}"), 0) AS "{c}"' for c in CATEGORIES)
    cursor.execute(f'''
        SELECT {selects}
        FROM expenses e
        JOIN budgets b ON e.budget_id = b.id
        WHERE b.user_id = %s AND e.expense_date >= %s AND e.expense_date < %s
    ''', (user_id, start_date, end_date))
    breakdown = cursor.fetchone()
    conn.close()
    if breakdown:
        return {c: breakdown[c] for c in CATEGORIES}
    return {c: 0 for c in CATEGORIES}

def add_expense(budget_id, day, expense_date, fare, food, other, total):
    try:
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO expenses (budget_id, day, expense_date, fare, food, other, total)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (budget_id, day, expense_date, fare, food, other, total))
        conn.commit()
        conn.close()
        return True
    except psycopg2.IntegrityError:
        return False

def delete_expense_by_day(budget_id, day):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses WHERE budget_id = %s AND day = %s', (budget_id, day))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_expenses_by_budget(budget_id):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT * FROM expenses
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
    expenses = cursor.fetchall()
    conn.close()
    return [dict(row) for row in expenses]


def get_expense_by_day(budget_id, day):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        'SELECT * FROM expenses WHERE budget_id = %s AND day = %s',
        (budget_id, day),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_items_by_expense(expense_id):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        'SELECT * FROM expense_items WHERE expense_id = %s ORDER BY created_at',
        (expense_id,),
    )
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]


def get_items_by_budget(budget_id):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT ei.*, e.day, e.id AS expense_id
        FROM expense_items ei
        JOIN expenses e ON ei.expense_id = e.id
        WHERE e.budget_id = %s
        ORDER BY ei.created_at
    ''', (budget_id,))
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]


def get_items_grouped_by_expense_id(budget_id):
    grouped = {}
    for item in get_items_by_budget(budget_id):
        expense_id = item['expense_id']
        grouped.setdefault(expense_id, []).append({
            'id': item['id'],
            'name': item['name'],
            'amount': item['amount'],
            'category': item['category'],
        })
    return grouped


def expense_item_belongs_to_user(item_id, user_id):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 1
        FROM expense_items ei
        JOIN expenses e ON ei.expense_id = e.id
        JOIN budgets b ON e.budget_id = b.id
        WHERE ei.id = %s AND b.user_id = %s
    ''', (item_id, user_id))
    owned = cursor.fetchone() is not None
    conn.close()
    return owned


def recalculate_expense_totals(cursor, expense_id):
    from api.categorize import CATEGORIES

    selects = ", ".join(
        f"COALESCE(SUM(CASE WHEN category = '{c}' THEN amount ELSE 0 END), 0) AS \"{c}\""
        for c in CATEGORIES
    )
    cursor.execute(
        f'SELECT {selects} FROM expense_items WHERE expense_id = %s', (expense_id,)
    )
    row = cursor.fetchone()
    if isinstance(row, dict):
        breakdown = {c: row[c] for c in CATEGORIES}
    else:
        breakdown = {c: row[i] for i, c in enumerate(CATEGORIES)}

    total = sum(breakdown.values())
    set_clause = ", ".join(f'"{c}" = %s' for c in CATEGORIES) + ", total = %s"
    cursor.execute(
        f'UPDATE expenses SET {set_clause} WHERE id = %s',
        (*[breakdown[c] for c in CATEGORIES], total, expense_id),
    )
    return breakdown, total


def get_or_create_expense(budget_id, day, expense_date):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        'SELECT * FROM expenses WHERE budget_id = %s AND day = %s',
        (budget_id, day),
    )
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)

    cursor.execute('''
        INSERT INTO expenses (budget_id, day, expense_date, fare, food, other, total)
        VALUES (%s, %s, %s, 0, 0, 0, 0)
        RETURNING *
    ''', (budget_id, day, expense_date))
    expense = dict(cursor.fetchone())
    conn.commit()
    conn.close()
    return expense


def add_expense_item(budget_id, day, expense_date, name, amount, category):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
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
    breakdown, total = recalculate_expense_totals(cursor, expense_id)
    conn.commit()
    conn.close()
    return item, {**breakdown, 'total': total}


def delete_expense_item(item_id, user_id):
    if not expense_item_belongs_to_user(item_id, user_id):
        return False, None

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT expense_id FROM expense_items WHERE id = %s', (item_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, None

    expense_id = row[0]
    cursor.execute('DELETE FROM expense_items WHERE id = %s', (item_id,))
    cursor.execute('SELECT COUNT(*) FROM expense_items WHERE expense_id = %s', (expense_id,))
    remaining = cursor.fetchone()[0]

    if remaining == 0:
        cursor.execute('DELETE FROM expenses WHERE id = %s', (expense_id,))
        totals = None
    else:
        breakdown, total = recalculate_expense_totals(cursor, expense_id)
        totals = {**breakdown, 'total': total}

    conn.commit()
    conn.close()
    return True, totals


def update_expense_item(item_id, user_id, name, amount, category):
    if not expense_item_belongs_to_user(item_id, user_id):
        return None, None

    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        'SELECT expense_id FROM expense_items WHERE id = %s', (item_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None, None

    expense_id = row['expense_id']
    cursor.execute('''
        UPDATE expense_items
        SET name = %s, amount = %s, category = %s
        WHERE id = %s
        RETURNING *
    ''', (name, amount, category, item_id))
    item = dict(cursor.fetchone())
    breakdown, total = recalculate_expense_totals(cursor, expense_id)
    conn.commit()
    conn.close()
    return item, {**breakdown, 'total': total}
