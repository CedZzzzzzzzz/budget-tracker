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
MAX_ITEM_NOTES_LEN = 500
MAX_TAG_LEN = 30
MAX_TAGS_PER_ITEM = 8
MAX_CUSTOM_CATEGORIES = 20
MAX_CATEGORY_LABEL_LEN = 40
MAX_CATEGORY_SLUG_LEN = 32

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


def normalize_item_notes(notes):
    text = (notes or "").strip()
    if len(text) > MAX_ITEM_NOTES_LEN:
        raise ValueError(f"Notes must be at most {MAX_ITEM_NOTES_LEN} characters.")
    return text


def normalize_item_tags(tags):
    if tags is None:
        raw = []
    elif isinstance(tags, str):
        raw = tags.replace(";", ",").split(",")
    elif isinstance(tags, (list, tuple)):
        raw = tags
    else:
        raise ValueError("Tags must be a list or comma-separated string.")

    cleaned = []
    seen = set()
    for tag in raw:
        value = str(tag or "").strip().lower()
        if not value:
            continue
        if len(value) > MAX_TAG_LEN:
            raise ValueError(f"Each tag must be at most {MAX_TAG_LEN} characters.")
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
        if len(cleaned) > MAX_TAGS_PER_ITEM:
            raise ValueError(f"At most {MAX_TAGS_PER_ITEM} tags allowed.")
    return cleaned


def expense_item_dict(item):
    tags = item.get("tags")
    if tags is None:
        tags = []
    elif not isinstance(tags, (list, tuple)):
        tags = list(tags) if tags else []
    return {
        "id": item["id"],
        "name": item["name"],
        "amount": as_float(item["amount"]),
        "category": item["category"],
        "notes": item.get("notes") or "",
        "tags": list(tags),
    }


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


def user_exists(user_id):
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM users WHERE id = %s AND email_verified_at IS NOT NULL",
            (user_id,),
        )
        return cursor.fetchone() is not None


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


def is_onboarding_completed(user_id):
    user = get_user_by_id(user_id)
    return bool(user and user.get("onboarding_completed_at"))


def complete_onboarding(user_id):
    with db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            "UPDATE users SET onboarding_completed_at = CURRENT_TIMESTAMP "
            "WHERE id = %s AND onboarding_completed_at IS NULL "
            "RETURNING onboarding_completed_at",
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return row["onboarding_completed_at"]
        cursor.execute(
            "SELECT onboarding_completed_at FROM users WHERE id = %s",
            (user_id,),
        )
        existing = cursor.fetchone()
        return existing["onboarding_completed_at"] if existing else None


def verify_password(user, password):
    return check_password_hash(user["password_hash"], password)


def delete_user_account(user_id, password):
    conn = db_connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "SELECT id, password_hash FROM users WHERE id = %s FOR UPDATE",
            (user_id,),
        )
        user = cursor.fetchone()
        if not user:
            conn.rollback()
            return "not_found"
        if not check_password_hash(user["password_hash"], password):
            conn.rollback()
            return "invalid_password"

        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        if cursor.rowcount != 1:
            conn.rollback()
            return "not_found"

        conn.commit()
        return "deleted"
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        release_connection(conn)


def hash_reset_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


def hash_email_verification_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_email_verification_token(user_id):
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_email_verification_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    with db_transaction() as cursor:
        cursor.execute(
            "UPDATE email_verification_tokens SET used_at = CURRENT_TIMESTAMP "
            "WHERE user_id = %s AND used_at IS NULL",
            (user_id,),
        )
        cursor.execute(
            "INSERT INTO email_verification_tokens (user_id, token_hash, expires_at) "
            "VALUES (%s, %s, %s)",
            (user_id, token_hash, expires_at),
        )
    return raw_token


def consume_email_verification_token(raw_token):
    token_hash = hash_email_verification_token(raw_token)
    with db_transaction(dict_cursor=True) as cursor:
        cursor.execute(
            "SELECT tokens.id, tokens.user_id, tokens.used_at, "
            "tokens.expires_at > CURRENT_TIMESTAMP AS active, users.email_verified_at "
            "FROM email_verification_tokens AS tokens "
            "JOIN users ON users.id = tokens.user_id "
            "WHERE tokens.token_hash = %s FOR UPDATE OF tokens, users",
            (token_hash,),
        )
        token = cursor.fetchone()
        if not token:
            return "invalid"
        if token["email_verified_at"]:
            return "verified"
        if token["used_at"] or not token["active"]:
            return "invalid"

        cursor.execute(
            "UPDATE users SET email_verified_at = CURRENT_TIMESTAMP WHERE id = %s",
            (token["user_id"],),
        )
        cursor.execute(
            "UPDATE email_verification_tokens SET used_at = CURRENT_TIMESTAMP "
            "WHERE user_id = %s AND used_at IS NULL",
            (token["user_id"],),
        )
        return "verified"


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


def update_user_profile(user_id, username=None, email=None, reset_email_verification=False):
    updates = []
    params = []
    if username is not None:
        updates.append("username = %s")
        params.append(username)
    if email is not None:
        updates.append("email = %s")
        params.append(normalize_email(email))
    if reset_email_verification:
        updates.append("email_verified_at = NULL")
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


def serialize_user_category(row):
    return {
        "id": row["id"],
        "slug": row["slug"],
        "label": row["label"],
        "color": row["color"],
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
    }


def get_user_categories(user_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            "SELECT id, slug, label, color, created_at FROM user_categories "
            "WHERE user_id = %s ORDER BY label ASC, id ASC",
            (user_id,),
        )
        return [serialize_user_category(dict(row)) for row in cursor.fetchall()]


def get_user_category(category_id, user_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            "SELECT id, slug, label, color, created_at FROM user_categories "
            "WHERE id = %s AND user_id = %s",
            (category_id, user_id),
        )
        row = cursor.fetchone()
        return serialize_user_category(dict(row)) if row else None


def allowed_category_slugs(user_id):
    from api.categorize import CATEGORIES
    slugs = list(CATEGORIES)
    if user_id is None:
        return slugs
    for category in get_user_categories(user_id):
        if category["slug"] not in slugs:
            slugs.append(category["slug"])
    return slugs


def category_labels_for_user(user_id):
    from api.categorize import CATEGORY_LABELS
    labels = dict(CATEGORY_LABELS)
    for category in get_user_categories(user_id):
        labels[category["slug"]] = category["label"]
    return labels


def slugify_category_label(label):
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", (label or "").lower().strip())
    slug = slug.strip("_")[:MAX_CATEGORY_SLUG_LEN]
    return slug or "custom"


def normalize_category_color(color):
    import re
    value = (color or "").strip()
    if not value:
        return "#94a3b8"
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("Color must be a hex value like #94a3b8.")
    return value.lower()


def create_user_category(user_id, label, color=None, slug=None):
    from api.categorize import CATEGORIES

    label = (label or "").strip()
    if not label:
        raise ValueError("Category name is required.")
    if len(label) > MAX_CATEGORY_LABEL_LEN:
        raise ValueError(f"Category name must be at most {MAX_CATEGORY_LABEL_LEN} characters.")

    color = normalize_category_color(color)
    base_slug = slugify_category_label(slug or label)
    if base_slug in CATEGORIES:
        raise ValueError("That name matches a built-in category. Choose a different name.")

    existing = get_user_categories(user_id)
    if len(existing) >= MAX_CUSTOM_CATEGORIES:
        raise ValueError(f"You can create at most {MAX_CUSTOM_CATEGORIES} custom categories.")

    used = {c["slug"] for c in existing} | set(CATEGORIES)
    candidate = base_slug
    suffix = 2
    while candidate in used:
        trimmed = base_slug[: max(1, MAX_CATEGORY_SLUG_LEN - len(str(suffix)) - 1)]
        candidate = f"{trimmed}_{suffix}"
        suffix += 1

    with db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            "INSERT INTO user_categories (user_id, slug, label, color) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, slug, label, color, created_at",
            (user_id, candidate, label, color),
        )
        return serialize_user_category(dict(cursor.fetchone()))


def update_user_category(category_id, user_id, label=None, color=None):
    existing = get_user_category(category_id, user_id)
    if not existing:
        return None

    fields = []
    params = []
    if label is not None:
        label = label.strip()
        if not label:
            raise ValueError("Category name is required.")
        if len(label) > MAX_CATEGORY_LABEL_LEN:
            raise ValueError(f"Category name must be at most {MAX_CATEGORY_LABEL_LEN} characters.")
        fields.append("label = %s")
        params.append(label)
    if color is not None:
        fields.append("color = %s")
        params.append(normalize_category_color(color))
    if not fields:
        return existing

    params.extend([category_id, user_id])
    with db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            f"UPDATE user_categories SET {', '.join(fields)} "
            f"WHERE id = %s AND user_id = %s "
            f"RETURNING id, slug, label, color, created_at",
            params,
        )
        row = cursor.fetchone()
        return serialize_user_category(dict(row)) if row else None


def delete_user_category(category_id, user_id):
    existing = get_user_category(category_id, user_id)
    if not existing:
        return False
    slug = existing["slug"]
    with db_transaction(dict_cursor=True) as cursor:
        cursor.execute(
            "UPDATE expense_items ei SET category = 'other' "
            "FROM expenses e JOIN budgets b ON e.budget_id = b.id "
            "WHERE ei.expense_id = e.id AND b.user_id = %s AND ei.category = %s",
            (user_id, slug),
        )
        cursor.execute(
            "DELETE FROM category_budget_limits WHERE user_id = %s AND category = %s",
            (user_id, slug),
        )
        cursor.execute(
            "UPDATE recurring_expenses SET category = 'other' "
            "WHERE user_id = %s AND category = %s",
            (user_id, slug),
        )
        cursor.execute(
            "UPDATE user_category_rules SET category = 'other' "
            "WHERE user_id = %s AND category = %s",
            (user_id, slug),
        )
        cursor.execute(
            "DELETE FROM user_categories WHERE id = %s AND user_id = %s",
            (category_id, user_id),
        )
        return cursor.rowcount > 0


def empty_category_breakdown(categories=None):
    from api.categorize import CATEGORIES
    cats = categories if categories is not None else CATEGORIES
    return {c: 0.0 for c in cats}


def breakdown_from_items(items, categories=None):
    breakdown = empty_category_breakdown(categories)
    for item in items:
        category = item.get("category", "other")
        amount = as_float(item.get("amount", 0))
        if category in breakdown:
            breakdown[category] += amount
        else:
            breakdown[category] = breakdown.get(category, 0.0) + amount
    return breakdown


def breakdown_from_row(row, items, categories=None):
    from api.categorize import CATEGORIES
    cats = categories if categories is not None else CATEGORIES
    if items:
        return breakdown_from_items(items, cats)
    return {c: as_float(row.get(c, 0)) for c in cats}


def category_sum_select_sql(item_alias="ei", categories=None):
    from api.categorize import CATEGORIES
    cats = categories if categories is not None else CATEGORIES
    return ", ".join(
        f"COALESCE(SUM(CASE WHEN {item_alias}.category = '{c}' "
        f"THEN {item_alias}.amount ELSE 0 END), 0) AS \"{c}\""
        for c in cats
    )


def legacy_category_sum_select_sql(expense_alias="e"):
    from api.categorize import CATEGORIES
    return ", ".join(
        f'COALESCE(SUM({expense_alias}."{c}"), 0) AS "{c}"' for c in CATEGORIES
    )


def merge_breakdown_rows(primary, legacy, categories=None):
    from api.categorize import CATEGORIES
    cats = list(categories) if categories is not None else list(CATEGORIES)
    for source in (primary, legacy):
        for key in source.keys() if hasattr(source, "keys") else []:
            if key not in cats and key not in ("spent", "days_logged", "allowance", "remaining"):
                cats.append(key)
    merged = empty_category_breakdown(cats)
    for category in cats:
        merged[category] = as_float(primary.get(category, 0)) + as_float(legacy.get(category, 0))
    return merged


def query_budget_category_breakdown(cursor, budget_id, categories=None):
    from api.categorize import CATEGORIES

    cats = list(categories) if categories is not None else None
    if cats is None:
        cursor.execute("SELECT user_id FROM budgets WHERE id = %s", (budget_id,))
        owner = cursor.fetchone()
        user_id = owner["user_id"] if owner and isinstance(owner, dict) else (
            owner[0] if owner else None
        )
        cats = list(allowed_category_slugs(user_id)) if user_id else list(CATEGORIES)

    cursor.execute(
        "SELECT ei.category AS category, COALESCE(SUM(ei.amount), 0) AS total "
        "FROM expense_items ei JOIN expenses e ON ei.expense_id = e.id "
        "WHERE e.budget_id = %s GROUP BY ei.category",
        (budget_id,),
    )
    item_row = {
        row["category"]: as_float(row["total"])
        for row in cursor.fetchall()
        if row.get("category")
    }
    cursor.execute(
        f'SELECT {legacy_category_sum_select_sql()} FROM expenses e '
        f'WHERE e.budget_id = %s '
        f'AND NOT EXISTS (SELECT 1 FROM expense_items ei WHERE ei.expense_id = e.id)',
        (budget_id,),
    )
    legacy_row = cursor.fetchone() or {}
    return merge_breakdown_rows(item_row, legacy_row, cats)


def query_user_category_breakdown(cursor, user_id, start_date, end_date, categories=None):
    cats = list(categories) if categories is not None else list(allowed_category_slugs(user_id))
    cursor.execute(
        "SELECT ei.category AS category, COALESCE(SUM(ei.amount), 0) AS total "
        "FROM expense_items ei "
        "JOIN expenses e ON ei.expense_id = e.id "
        "JOIN budgets b ON e.budget_id = b.id "
        "WHERE b.user_id = %s AND e.expense_date >= %s AND e.expense_date < %s "
        "GROUP BY ei.category",
        (user_id, start_date, end_date),
    )
    item_row = {
        row["category"]: as_float(row["total"])
        for row in cursor.fetchall()
        if row.get("category")
    }
    cursor.execute(
        f'SELECT {legacy_category_sum_select_sql()} FROM expenses e '
        f'JOIN budgets b ON e.budget_id = b.id '
        f'WHERE b.user_id = %s AND e.expense_date >= %s AND e.expense_date < %s '
        f'AND NOT EXISTS (SELECT 1 FROM expense_items ei WHERE ei.expense_id = e.id)',
        (user_id, start_date, end_date),
    )
    legacy_row = cursor.fetchone() or {}
    return merge_breakdown_rows(item_row, legacy_row, cats)


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
            'SELECT id, expense_id, name, amount, category, notes, tags, created_at '
            'FROM expense_items WHERE expense_id = %s ORDER BY created_at',
            (expense_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_items_by_budget(budget_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute('''
            SELECT ei.id, ei.expense_id, ei.name, ei.amount, ei.category, ei.notes, ei.tags, e.day
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
        public = expense_item_dict(item)
        grouped.setdefault(expense_id, []).append(public)
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


def build_period_report(user_id, start_date, end_date, label=None):
    weeks, breakdown = get_monthly_summary(user_id, start_date, end_date)
    snapshot = build_savings_snapshot(weeks, finalized_only=False)
    categories = allowed_category_slugs(user_id)
    cat_totals = {c: as_float(breakdown.get(c, 0)) for c in categories}
    for key, value in breakdown.items():
        if key not in cat_totals:
            cat_totals[key] = as_float(value)
    weekly_data = [
        {
            "week_start": str(w["week_start_date"]),
            "week_end": str(w["week_end_date"]),
            "allowance": as_float(w["allowance"]),
            "spent": as_float(w["total_spent"]),
            "saved": as_float(w["allowance"]) - as_float(w["total_spent"]),
        }
        for w in weeks
    ]
    return {
        "start_date": str(start_date),
        "end_date": str(end_date - timedelta(days=1)),
        "label": label or f"{start_date} to {end_date - timedelta(days=1)}",
        "total_allowance": snapshot["total_allowance"],
        "total_spent": snapshot["total_spent"],
        "total_saved": snapshot["total_allowance"] - snapshot["total_spent"],
        "breakdown": cat_totals,
        "custom_categories": get_user_categories(user_id),
        "weeks": weekly_data,
        "num_weeks": len(weekly_data),
        "raw_weeks": weeks,
    }


def get_yearly_summary(user_id, year):
    start_date = datetime(year, 1, 1).date()
    end_date = datetime(year + 1, 1, 1).date()
    weeks, breakdown = get_monthly_summary(user_id, start_date, end_date)
    snapshot = build_savings_snapshot(weeks, finalized_only=False)

    months = []
    for month in range(1, 13):
        month_start = datetime(year, month, 1).date()
        month_end = (
            datetime(year + 1, 1, 1).date() if month == 12
            else datetime(year, month + 1, 1).date()
        )
        month_weeks = [
            w for w in weeks
            if month_start <= w["week_start_date"] < month_end
        ]
        if not month_weeks:
            continue
        allowance = sum(as_float(w["allowance"]) for w in month_weeks)
        spent = sum(as_float(w["total_spent"]) for w in month_weeks)
        months.append({
            "month": month,
            "label": datetime(year, month, 1).strftime("%b"),
            "month_name": datetime(year, month, 1).strftime("%B %Y"),
            "week_start_date": month_start,
            "allowance": allowance,
            "total_spent": spent,
            "spent": spent,
            "saved": allowance - spent,
            "num_weeks": len(month_weeks),
        })

    categories = allowed_category_slugs(user_id)
    cat_totals = {c: as_float(breakdown.get(c, 0)) for c in categories}
    for key, value in breakdown.items():
        if key not in cat_totals:
            cat_totals[key] = as_float(value)
    return {
        "year": year,
        "label": str(year),
        "start_date": str(start_date),
        "end_date": str(end_date - timedelta(days=1)),
        "total_allowance": snapshot["total_allowance"],
        "total_spent": snapshot["total_spent"],
        "total_saved": snapshot["total_allowance"] - snapshot["total_spent"],
        "breakdown": cat_totals,
        "custom_categories": get_user_categories(user_id),
        "months": months,
        "num_months": len(months),
        "num_weeks": len(weeks),
        "raw_weeks": weeks,
        "month_rows": months,
    }


def build_savings_snapshot(weeks, as_of=None, finalized_only=True):
    from datetime import date as date_cls

    as_of = as_of or date_cls.today()
    total_allowance = 0.0
    total_spent = 0.0
    total_saved = 0.0
    total_overspent = 0.0
    weeks_under = 0
    weeks_over = 0
    weeks_even = 0
    weeks_closed = 0
    weeks_open = 0

    for week in weeks:
        allowance = as_float(week["allowance"])
        spent = as_float(week.get("total_spent", week.get("spent", 0)))
        week_end = week["week_end_date"]
        if hasattr(week_end, "isoformat"):
            closed = week_end < as_of
        else:
            closed = str(week_end) < str(as_of)

        if not closed:
            weeks_open += 1
            if finalized_only:
                continue

        weeks_closed += 1 if closed else 0
        total_allowance += allowance
        total_spent += spent
        diff = allowance - spent
        if diff > 0:
            total_saved += diff
            weeks_under += 1
        elif diff < 0:
            total_overspent += -diff
            weeks_over += 1
        else:
            weeks_even += 1

    if not finalized_only:
        weeks_closed = len(weeks) - weeks_open

    return {
        "total_allowance": total_allowance,
        "total_spent": total_spent,
        "total_saved": total_saved,
        "lifetime_saved": total_saved,
        "total_overspent": total_overspent,
        "net_balance": total_saved - total_overspent,
        "weeks_tracked": len(weeks),
        "weeks_closed": weeks_closed,
        "weeks_open": weeks_open,
        "weeks_under": weeks_under,
        "weeks_over": weeks_over,
        "weeks_even": weeks_even,
    }


def build_savings_ledger(weeks, as_of=None):
    from datetime import date as date_cls

    as_of = as_of or date_cls.today()
    snapshot = build_savings_snapshot(weeks, as_of=as_of)
    entries = []
    running_balance = 0.0
    running_saved = 0.0
    running_overspent = 0.0
    running_spent = 0.0
    running_allowance = 0.0
    open_week = None

    for week in weeks:
        allowance = as_float(week["allowance"])
        spent = as_float(week.get("total_spent", week.get("spent", 0)))
        remaining = allowance - spent
        week_start = week["week_start_date"]
        week_end = week["week_end_date"]

        if hasattr(week_end, "isoformat"):
            closed = week_end < as_of
        else:
            closed = str(week_end) < str(as_of)

        if hasattr(week_start, "strftime") and hasattr(week_end, "strftime"):
            label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
        else:
            label = f"{week_start} – {week_end}"

        if closed:
            net = remaining
            saved = max(net, 0.0)
            overspent = max(-net, 0.0)
            running_allowance += allowance
            running_spent += spent
            running_saved += saved
            running_overspent += overspent
            running_balance += net
            entries.append({
                "week_start": str(week_start),
                "week_end": str(week_end),
                "label": label,
                "status": "closed",
                "allowance": allowance,
                "spent": spent,
                "remaining": remaining,
                "saved": saved,
                "overspent": overspent,
                "net": net,
                "running_allowance": running_allowance,
                "running_spent": running_spent,
                "running_saved": running_saved,
                "running_overspent": running_overspent,
                "running_balance": running_balance,
            })
        else:
            open_week = {
                "week_start": str(week_start),
                "week_end": str(week_end),
                "label": label,
                "status": "in_progress",
                "allowance": allowance,
                "spent": spent,
                "remaining": remaining,
                "saved": 0.0,
                "overspent": 0.0,
                "net": 0.0,
                "on_track": remaining >= 0,
                "running_balance": running_balance,
            }
            entries.append({
                **open_week,
                "running_allowance": running_allowance,
                "running_spent": running_spent,
                "running_saved": running_saved,
                "running_overspent": running_overspent,
            })

    return {
        **snapshot,
        "running_balance": running_balance,
        "open_week": open_week,
        "entries": entries,
    }


def get_savings_snapshot(user_id, start_date, end_date):
    weeks, _ = get_monthly_summary(user_id, start_date, end_date)
    return build_savings_snapshot(weeks), weeks


def get_savings_ledger(user_id, start_date, end_date):
    weeks, _ = get_monthly_summary(user_id, start_date, end_date)
    return build_savings_ledger(weeks), weeks


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


def day_expense_payload(cursor, expense_id, categories=None):
    cols = expense_select_columns_legacy()
    cursor.execute(f'SELECT {cols} FROM expenses WHERE id = %s', (expense_id,))
    row = cursor.fetchone()
    if not row:
        return None
    if categories is None:
        cursor.execute(
            'SELECT b.user_id FROM expenses e JOIN budgets b ON e.budget_id = b.id '
            'WHERE e.id = %s',
            (expense_id,),
        )
        owner = cursor.fetchone()
        user_id = owner["user_id"] if owner else None
        categories = allowed_category_slugs(user_id) if user_id else None
    cursor.execute(
        'SELECT id, name, amount, category, notes, tags FROM expense_items '
        'WHERE expense_id = %s ORDER BY created_at',
        (expense_id,),
    )
    items = [expense_item_dict(item) for item in cursor.fetchall()]
    breakdown = breakdown_from_row(row, items, categories)
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


def add_expense_item(budget_id, day, expense_date, name, amount, category, notes="", tags=None):
    notes = normalize_item_notes(notes)
    tags = normalize_item_tags(tags)
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
            INSERT INTO expense_items (expense_id, name, amount, category, notes, tags)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
        ''', (expense_id, name, amount, category, notes, tags))
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
            SELECT ei.id, ei.expense_id, ei.name, ei.amount, ei.category, ei.notes, ei.tags, e.day, e.budget_id
            FROM expense_items ei
            JOIN expenses e ON ei.expense_id = e.id
            WHERE ei.id = %s
        ''', (item_id,))
        row = cursor.fetchone()
        if not row:
            return False, None, None, None, None

        deleted_item = expense_item_dict(row)
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
            SELECT e.expense_date, e.day, ei.name, ei.category, ei.amount, ei.notes, ei.tags
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
                'notes': row.get('notes') or '',
                'tags': list(row['tags'] or []),
            }
            for row in cursor.fetchall()
        ]


def get_account_export_snapshot(user_id):
    with db_transaction(dict_cursor=True) as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute(
            "SELECT username, email, created_at, onboarding_completed_at "
            "FROM users WHERE id = %s",
            (user_id,),
        )
        profile_row = cursor.fetchone()
        profile = dict(profile_row) if profile_row else {}
        if profile:
            profile["onboarding_completed"] = bool(profile.pop("onboarding_completed_at", None))

        cursor.execute(
            "SELECT week_start_date, week_end_date, allowance, created_at "
            "FROM budgets WHERE user_id = %s ORDER BY week_start_date",
            (user_id,),
        )
        budgets = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT e.expense_date, e.day, ei.name, ei.category, ei.amount, "
            "ei.notes, ei.tags, ei.created_at "
            "FROM expense_items ei "
            "JOIN expenses e ON e.id = ei.expense_id "
            "JOIN budgets b ON b.id = e.budget_id "
            "WHERE b.user_id = %s ORDER BY e.expense_date, ei.created_at, ei.id",
            (user_id,),
        )
        expense_items = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT slug, label, color, created_at FROM user_categories "
            "WHERE user_id = %s ORDER BY label, slug",
            (user_id,),
        )
        custom_categories = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT category, weekly_limit FROM category_budget_limits "
            "WHERE user_id = %s ORDER BY category",
            (user_id,),
        )
        category_limits = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT name, amount, category, frequency, apply_day, apply_day_of_month, "
            "active, created_at FROM recurring_expenses "
            "WHERE user_id = %s ORDER BY created_at, name",
            (user_id,),
        )
        recurring_expenses = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT r.name AS recurring_name, a.period_key, a.applied_at, "
            "ei.name AS expense_item_name, e.expense_date "
            "FROM recurring_expense_applications a "
            "JOIN recurring_expenses r ON r.id = a.recurring_id "
            "LEFT JOIN expense_items ei ON ei.id = a.expense_item_id "
            "LEFT JOIN expenses e ON e.id = ei.expense_id "
            "WHERE r.user_id = %s ORDER BY a.applied_at, a.period_key",
            (user_id,),
        )
        recurring_applications = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT name, target_amount, current_amount, deadline, status, created_at, updated_at "
            "FROM savings_goals WHERE user_id = %s ORDER BY created_at, name",
            (user_id,),
        )
        savings_goals = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT label, amount, active, sort_order, created_at, updated_at "
            "FROM user_income_sources WHERE user_id = %s ORDER BY sort_order, label",
            (user_id,),
        )
        income_sources = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT pattern, category, hit_count, updated_at FROM user_category_rules "
            "WHERE user_id = %s ORDER BY pattern, category",
            (user_id,),
        )
        category_rules = [dict(row) for row in cursor.fetchall()]

        return {
            "profile": profile,
            "budgets": budgets,
            "expense_items": expense_items,
            "custom_categories": custom_categories,
            "category_limits": category_limits,
            "recurring_expenses": recurring_expenses,
            "recurring_applications": recurring_applications,
            "savings_goals": savings_goals,
            "income_sources": income_sources,
            "category_rules": category_rules,
        }


def update_expense_item(item_id, user_id, name, amount, category, notes="", tags=None):
    notes = normalize_item_notes(notes)
    tags = normalize_item_tags(tags)
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
            SET name = %s, amount = %s, category = %s, notes = %s, tags = %s
            WHERE id = %s
            RETURNING *
        ''', (name, amount, category, notes, tags, item_id))
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


def get_spending_anomaly_candidates(user_id, start_date, end_date, history_start):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute('''
            SELECT
                ei.id AS item_id,
                ei.name,
                ei.amount,
                ei.category,
                e.expense_date,
                (e.expense_date >= %s AND e.expense_date <= %s) AS is_current
            FROM expense_items ei
            JOIN expenses e ON e.id = ei.expense_id
            JOIN budgets b ON b.id = e.budget_id
            WHERE b.user_id = %s
              AND e.expense_date >= %s
              AND e.expense_date <= %s
            ORDER BY e.expense_date, ei.id
        ''', (start_date, end_date, user_id, history_start, end_date))
        return [dict(row) for row in cursor.fetchall()]


def learn_category_correction(user_id, name, category):
    from api.categorize import categorize_item, extract_learn_patterns

    allowed = set(allowed_category_slugs(user_id))
    if category not in allowed:
        return
    user_rules = get_user_category_rules(user_id)
    suggested = categorize_item(name, user_rules, allowed_categories=allowed)
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
    categories = allowed_category_slugs(user_id)
    limits = {category: None for category in categories}
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
    allowed = set(allowed_category_slugs(user_id))

    with db_cursor(commit=True) as cursor:
        for category, limit in limits.items():
            if category not in allowed:
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


def build_category_status(totals, limits, categories=None):
    from api.categorize import CATEGORIES

    cats = categories if categories is not None else CATEGORIES
    if categories is None and limits:
        cats = list(dict.fromkeys([*CATEGORIES, *limits.keys()]))

    status = {}
    for category in cats:
        spent = as_float(totals.get(category, 0))
        limit = limits.get(category) if limits else None
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
            "warning": pct is not None and pct >= 80 and spent <= limit,
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


def serialize_savings_goal(row):
    target = as_float(row["target_amount"])
    current = as_float(row["current_amount"])
    progress = min((current / target) * 100, 100.0) if target > 0 else 0.0
    remaining = max(target - current, 0.0)
    deadline = row.get("deadline")
    return {
        "id": row["id"],
        "name": row["name"],
        "target_amount": target,
        "current_amount": current,
        "deadline": str(deadline) if deadline else None,
        "status": row["status"],
        "progress_pct": round(progress, 1),
        "remaining": remaining,
        "is_complete": current >= target or row["status"] == "completed",
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
        "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
    }


def get_savings_goals(user_id, include_archived=False):
    with db_cursor(dict_cursor=True) as cursor:
        if include_archived:
            cursor.execute(
                "SELECT id, name, target_amount, current_amount, deadline, status, "
                "created_at, updated_at FROM savings_goals "
                "WHERE user_id = %s ORDER BY "
                "CASE status WHEN 'active' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END, "
                "created_at DESC",
                (user_id,),
            )
        else:
            cursor.execute(
                "SELECT id, name, target_amount, current_amount, deadline, status, "
                "created_at, updated_at FROM savings_goals "
                "WHERE user_id = %s AND status != 'archived' ORDER BY "
                "CASE status WHEN 'active' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END, "
                "created_at DESC",
                (user_id,),
            )
        return [serialize_savings_goal(dict(row)) for row in cursor.fetchall()]


def get_savings_goal(goal_id, user_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            "SELECT id, name, target_amount, current_amount, deadline, status, "
            "created_at, updated_at FROM savings_goals "
            "WHERE id = %s AND user_id = %s",
            (goal_id, user_id),
        )
        row = cursor.fetchone()
        return serialize_savings_goal(dict(row)) if row else None


def create_savings_goal(user_id, name, target_amount, current_amount=0, deadline=None):
    current_amount = max(as_float(current_amount), 0.0)
    target_amount = as_float(target_amount)
    status = "completed" if current_amount >= target_amount else "active"
    with db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            "INSERT INTO savings_goals "
            "(user_id, name, target_amount, current_amount, deadline, status) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, name, target_amount, current_amount, deadline, status),
        )
        return cursor.fetchone()["id"]


def update_savings_goal(goal_id, user_id, **fields):
    allowed = {"name", "target_amount", "current_amount", "deadline", "status"}
    updates = []
    params = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "deadline" and value == "":
            value = None
        updates.append(f"{key} = %s")
        params.append(value)
    if not updates:
        return False
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([goal_id, user_id])
    with db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            f"UPDATE savings_goals SET {', '.join(updates)} "
            f"WHERE id = %s AND user_id = %s "
            f"RETURNING id, name, target_amount, current_amount, deadline, status, "
            f"created_at, updated_at",
            params,
        )
        row = cursor.fetchone()
        if not row:
            return None
        goal = dict(row)
        if goal["status"] != "archived":
            current = as_float(goal["current_amount"])
            target = as_float(goal["target_amount"])
            new_status = "completed" if current >= target else "active"
            if new_status != goal["status"]:
                cursor.execute(
                    "UPDATE savings_goals SET status = %s, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = %s AND user_id = %s "
                    "RETURNING id, name, target_amount, current_amount, deadline, status, "
                    "created_at, updated_at",
                    (new_status, goal_id, user_id),
                )
                goal = dict(cursor.fetchone())
        return serialize_savings_goal(goal)


def contribute_to_savings_goal(goal_id, user_id, amount):
    amount = as_float(amount)
    if amount <= 0:
        return None
    with db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            "SELECT id, name, target_amount, current_amount, deadline, status, "
            "created_at, updated_at FROM savings_goals "
            "WHERE id = %s AND user_id = %s AND status != 'archived' FOR UPDATE",
            (goal_id, user_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        goal = dict(row)
        new_current = as_float(goal["current_amount"]) + amount
        target = as_float(goal["target_amount"])
        new_status = "completed" if new_current >= target else "active"
        cursor.execute(
            "UPDATE savings_goals SET current_amount = %s, status = %s, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE id = %s AND user_id = %s "
            "RETURNING id, name, target_amount, current_amount, deadline, status, "
            "created_at, updated_at",
            (new_current, new_status, goal_id, user_id),
        )
        return serialize_savings_goal(dict(cursor.fetchone()))


def delete_savings_goal(goal_id, user_id):
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "DELETE FROM savings_goals WHERE id = %s AND user_id = %s",
            (goal_id, user_id),
        )
        return cursor.rowcount > 0


MAX_INCOME_SOURCE_LABEL = 40
MAX_INCOME_SOURCES = 12


def serialize_income_source(row):
    return {
        "id": row["id"],
        "label": row["label"],
        "amount": as_float(row["amount"]),
        "active": bool(row["active"]),
        "sort_order": int(row["sort_order"] or 0),
    }


def get_user_income_sources(user_id):
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(
            "SELECT id, label, amount, active, sort_order "
            "FROM user_income_sources WHERE user_id = %s "
            "ORDER BY sort_order ASC, id ASC",
            (user_id,),
        )
        return [serialize_income_source(dict(row)) for row in cursor.fetchall()]


def income_sources_total(sources=None, user_id=None, active_only=True):
    items = sources if sources is not None else get_user_income_sources(user_id)
    total = 0.0
    for item in items:
        if active_only and not item.get("active"):
            continue
        total += as_float(item.get("amount"))
    return round(total, 2)


def create_user_income_source(user_id, label, amount):
    label = (label or "").strip()
    if not label:
        raise ValueError("Name is required.")
    if len(label) > MAX_INCOME_SOURCE_LABEL:
        raise ValueError(f"Name must be at most {MAX_INCOME_SOURCE_LABEL} characters.")
    amount = as_float(amount)
    if amount <= 0:
        raise ValueError("Amount must be greater than 0.")

    with db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS count FROM user_income_sources WHERE user_id = %s",
            (user_id,),
        )
        count = int(cursor.fetchone()["count"])
        if count >= MAX_INCOME_SOURCES:
            raise ValueError(f"You can add at most {MAX_INCOME_SOURCES} income sources.")

        cursor.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order "
            "FROM user_income_sources WHERE user_id = %s",
            (user_id,),
        )
        sort_order = int(cursor.fetchone()["next_order"])
        cursor.execute(
            "INSERT INTO user_income_sources (user_id, label, amount, sort_order) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, label, amount, active, sort_order",
            (user_id, label, amount, sort_order),
        )
        return serialize_income_source(dict(cursor.fetchone()))


def update_user_income_source(source_id, user_id, **fields):
    updates = []
    params = []
    if "label" in fields:
        label = (fields["label"] or "").strip()
        if not label:
            raise ValueError("Name is required.")
        if len(label) > MAX_INCOME_SOURCE_LABEL:
            raise ValueError(f"Name must be at most {MAX_INCOME_SOURCE_LABEL} characters.")
        updates.append("label = %s")
        params.append(label)
    if "amount" in fields:
        amount = as_float(fields["amount"])
        if amount <= 0:
            raise ValueError("Amount must be greater than 0.")
        updates.append("amount = %s")
        params.append(amount)
    if "active" in fields:
        updates.append("active = %s")
        params.append(bool(fields["active"]))
    if "sort_order" in fields and fields["sort_order"] is not None:
        updates.append("sort_order = %s")
        params.append(int(fields["sort_order"]))

    if not updates:
        return None
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([source_id, user_id])
    with db_cursor(commit=True, dict_cursor=True) as cursor:
        cursor.execute(
            f"UPDATE user_income_sources SET {', '.join(updates)} "
            f"WHERE id = %s AND user_id = %s "
            f"RETURNING id, label, amount, active, sort_order",
            params,
        )
        row = cursor.fetchone()
        return serialize_income_source(dict(row)) if row else None


def delete_user_income_source(source_id, user_id):
    with db_cursor(commit=True) as cursor:
        cursor.execute(
            "DELETE FROM user_income_sources WHERE id = %s AND user_id = %s",
            (source_id, user_id),
        )
        return cursor.rowcount > 0
