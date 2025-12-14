import sqlite3

DATABASE = "budget_tracker.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            week_start_date DATE NOT NULL,
            week_end_date DATE NOT NULL,
            allowance REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, week_start_date, week_end_date)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            expense_date DATE NOT NULL,
            fare REAL DEFAULT 0,
            food REAL DEFAULT 0,
            other REAL DEFAULT 0,
            total REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(budget_id) REFERENCES budgets(id) ON DELETE CASCADE,
            UNIQUE(budget_id, day)
        )
    ''')

    conn.commit()
    conn.close()
    print("Database Initialized.")

def create_budget(user_id, week_start, week_end, allowance):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO budgets (user_id, week_start_date, week_end_date, allowance)
            VALUES (?, ?, ?, ?)
        ''', (user_id, week_start, week_end, allowance))
        budget_id = cursor.lastrowid
        conn.commit()
        return budget_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def update_budget(budget_id, allowance):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE budgets SET allowance = ? WHERE id = ?', (allowance, budget_id))
    conn.commit()
    conn.close()

def get_budget_by_week(user_id, week_start, week_end):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM budgets
        WHERE user_id = ? AND week_start_date = ? AND week_end_date = ?
    ''', (user_id, week_start, week_end))
    budget = cursor.fetchone()
    conn.close()
    return budget
def get_budgets_by_month(user_id, start_date, end_date):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT b.id, b.week_start_date, b.week_end_date, b.allowance,
            COALESCE(SUM(e.total), 0) AS total_spent
        FROM budgets b
        LEFT JOIN expenses e ON b.id = e.budget_id
        WHERE b.user_id = ? AND b.week_start_date >= ? AND b.week_start_date < ?
        GROUP BY b.id
        ORDER BY b.week_start_date                 
    ''', (user_id, start_date, end_date))
    budgets = cursor.fetchall()
    conn.close()
    return budgets

def add_expense(budget_id, day, expense_date, fare, food, other, total):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO expenses (budget_id, day, expense_date, fare, food, other, total)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (budget_id, day, expense_date, fare, food, other, total))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_expense_by_day(budget_id, day):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses WHERE budget_id = ? AND day = ?', (budget_id, day))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_expenses_by_budget(budget_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT day, expense_date, fare, food, other, total FROM expenses
        WHERE budget_id = ?
        ORDER BY CASE day
            WHEN 'Sunday' THEN 1
            WHEN 'Monday' THEN 2
            WHEN 'Tuesday' THEN 3
            WHEN 'Wednesday' THEN 4
            WHEN 'Thursday' THEN 5
            WHEN 'Friday' THEN 6
            WHEN 'Saturday' THEN 7
            END
    ''', (budget_id, ))
    expenses = cursor.fetchall()
    conn.close()
    return expenses

def get_monthly_expense_breakdown(user_id, start_date, end_date):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COALESCE(SUM(e.fare), 0) AS total_fare,
               COALESCE(SUM(e.food), 0) AS total_food,
               COALESCE(SUM(e.other), 0) AS total_other
        FROM budgets b
        LEFT JOIN expenses e ON b.id = e.budget_id
        WHERE b.user_id = ? AND b.week_start_date >= ? AND b.week_start_date < ?
    ''', (user_id, start_date, end_date))
    breakdown = cursor.fetchone()
    conn.close()
    return breakdown

