import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Get database URL from environment variable (Railway provides this automatically)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP       
        )
    ''')
    
    # Budgets Table
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
    
    # Expenses Table
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

    conn.commit()
    conn.close()
    print("Database Initialized.")

# User Functions -----
def create_user(username, email, password):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (username, email, password_hash)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return user_id
    except psycopg2.IntegrityError:
        return None
    
def get_user_by_username(username):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_email(email):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def verify_password(user, password):
    return check_password_hash(user["password_hash"], password)

# Budget Functions -----
def create_budget(user_id, week_start, week_end, allowance):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO budgets (user_id, week_start_date, week_end_date, allowance) VALUES (%s, %s, %s, %s) RETURNING id",
        (user_id, week_start, week_end, allowance)
    )
    budget_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return budget_id

def update_budget(budget_id, allowance):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('UPDATE budgets SET allowance = %s WHERE id = %s', (allowance, budget_id))
    conn.commit()
    conn.close()
    return True

def get_budget_by_week(user_id, week_start, week_end):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT * FROM budgets
        WHERE user_id = %s AND week_start_date = %s AND week_end_date = %s
    ''', (user_id, week_start, week_end))
    budget = cursor.fetchone()
    conn.close()
    return dict(budget) if budget else None

def get_budgets_by_month(user_id, start_date, end_date):
    conn = psycopg2.connect(DATABASE_URL)
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
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT COALESCE(SUM(e.fare), 0) AS total_fare,
               COALESCE(SUM(e.food), 0) AS total_food,
               COALESCE(SUM(e.other), 0) AS total_other
        FROM expenses e
        JOIN budgets b ON e.budget_id = b.id
        WHERE b.user_id = %s AND e.expense_date >= %s AND e.expense_date < %s
    ''', (user_id, start_date, end_date))
    breakdown = cursor.fetchone()
    conn.close()
    return dict(breakdown) if breakdown else {"total_fare": 0, "total_food": 0, "total_other": 0}

def add_expense(budget_id, day, expense_date, fare, food, other, total):
    try:
        conn = psycopg2.connect(DATABASE_URL)
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
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses WHERE budget_id = %s AND day = %s', (budget_id, day))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_expenses_by_budget(budget_id):
    conn = psycopg2.connect(DATABASE_URL)
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