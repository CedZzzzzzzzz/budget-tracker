from flask import Blueprint, request, jsonify, session, make_response
from datetime import datetime, timedelta
import database as db
import os
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from functools import wraps

api = Blueprint("api", __name__, url_prefix = "/api")

#Password validation
def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(char.isupper() for char in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one digit"
    
    special_chars = "!@#$%^&*(),.?\":{}|<>"
    if not any(char in special_chars for char in password):
        return False, "Password must contain at least one special character"
    
    return True, "Valid password"
    

#Authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error" : "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_user_id():
    return session["user_id"]

#Helper Functions
def get_week_range():
    today = datetime.now().date()
    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - timedelta(days = days_since_sunday)
    week_end  = week_start + timedelta(days = 6)
    return week_start, week_end

def get_current_day():
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[datetime.now().weekday()]

#Authenticated Routes
@api.route("/register", methods = ["POST"])
def register():
    try:
        data = request.getjson()
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()

        if not username or len(username) < 8:
            return jsonify({"error" : "Username must be at least 8 characters long."}), 400
        if not email or "@" not in email:
            return jsonify({"error" : "Inavlid email address."}), 400
        
        #Password verification
        is_valid, message = validate_password(password)
        if not is_valid:
            return jsonify({"error" : message}), 400
        
        #Check if username or email already exists
        if db.get_user_by_username(username):
            return jsonify({"error" : "Username already exists"}), 400
        if db.get_user_by_email(email):
            return jsonify({"error" : "An account is already registed with this email"}), 400
        
        #Create user
        user_id = db.create_user(username, email, password)
        if user_id:
            session ["user_id"] = user_id
            session ["username"] = username
            return jsonify({"succes" : True, "username" : username})
        return jsonify({"error" : "Registration failed"}), 500
    
    except Exception as e:
        return jsonify({"error" : str(e)}), 500
@api.route("/login", methods = ["POST"])
def login():
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"error" : "Username and password are required"}), 400
        
        #Get user from database
        user = db.get_user_by_username(username)
        if not user:
            return jsonify({"error" : "Invalid username"}), 401
        #Password verification
        if not db.verify_password(user["id"], password):
            return jsonify({"error" : "Invalid password"}), 401
        
        #Set session
        session ["user_id"] = user["id"]
        session["username"] = user["username"]

        return jsonify({"success" : True, "username" : user["username"]})
    
    except Exception as e:
        return jsonify({"error" : str(e)}),500
@api.route("/logout", methods = ["GET"])
def check_auth():
    if "user_id" in session:
        return jsonify({"authenticated" : True, "username" : session.get("username")})
    return jsonify({"authenticated" : False})


#Budget routes
@api.route("/current-week-info", methods = ["GET"])
@login_required
def current_week_info():
    week_start, week_end = get_week_range()
    today = datetime.now().date()
    days_remaining = (week_end - today).days
    return jsonify({
        "week_start" : str(week_start),
        "week_end" : str(week_end),
        "current_day" : get_current_day(),
        'days_remaining': max(0, days_remaining),
        "week_start_formatted" : week_start.strftime("%B %d, %Y"),
        "week_end_formatted" : week_end.strftime("%B %d, %Y"),
    })

@api.route("/set-allowance", methods = ["POST"])
@login_required
def set_allowance():
    try:
        data = request.get_json()
        allowance = float(data.get("allowance", 0))

        if allowance <= 0:
            return jsonify({"error" : "Allowance must be greater than 0"}), 400
        
        user_id = get_user_id()
        week_start, week_end = get_week_range()
        existing = db.get_budget_by_week(user_id, week_start, week_end)

        if existing:
            db.update_budget(existing["id"], allowance)
            budget_id = existing["id"]
        else:
            budget_id = db.create_budget(user_id, week_start, week_end, allowance)

        return jsonify({"success" : True, "allowance" : allowance, "budget_id" : budget_id})
    except Exception as e:
        return jsonify({"error" : str(e)}, 500)
    
@api.route("/add-expense", methods = ["POST"])
@login_required
def add_expense():
    try:
        data = request.get_json()
        user_id = get_user_id()
        week_start, week_end = get_week_range()

        day = data.get("day")
        fare = float(data.get("fare", 0))
        food = float(data.get("food", 0))
        other = float(data.get("other", 0))
        total = fare + food + other

        days_map = {"Sunday" : 0, "Monday" : 1, "Tuesday" : 2, "Wednesday" : 3, "Thursday" : 4, "Friday" : 5, "Saturday" : 6}
        expense_date = week_start + timedelta(days = days_map.get(day, 0))
        
        budget = db.get_budget_by_week(user_id, week_start, week_end)
        if not budget:
            return jsonify({"error" : "Please set allowance first."}), 404
        
        if db.add_expense(budget["id"], day, expense_date, fare, food, other, total):
            return jsonify({"success" : True, "day" : day, "expense" : {"fare" : fare, "food" : food, "other" : other, "total" : total}})
        return jsonify({"error" : f"Expenses for {day} already exist"})
    except Exception as e:
        return jsonify({"error" : str(e)}), 500
    
@api.route("/delete-expense/<day>", methods = ["DELETE"])
@login_required
def delete_expense(day):
    try:
        user_id = get_user_id()
        week_start, week_end = get_week_range()
        budget = db.get_budget_by_week(user_id, week_start, week_end)

        if not budget:
            return jsonify({"error" : "Budget not found."}), 404
        if db.delete_expense_by_day(budget ["id"], day):
            return jsonify({"success" : True})
        return jsonify({"error" : f"No expenses for {day}"}), 404
    except Exception as e:
        return jsonify({"error" : str(e)}), 500
    
@api.route("/get-budget", methods = ["GET"])
@login_required
def get_budget():
    try:
        user_id = get_user_id()
        week_start, week_end = get_week_range()
        budget = db.get_budget_by_week(user_id, week_start, week_end)

        if not budget:
            return jsonify({
                "allowance" : 0,
                "expenses" : {},
                "totals" : {"fare" : 0, "food" : 0, "other" : 0, "spent": 0, "remaining" : 0},
                "days_logged" : 0
            })
        
        expenses_rows = db.get_expenses_by_budget(budget["id"])
        expenses = {}
        total_fare = total_food= total_other = 0

        for row in expenses_rows:
            expenses[row["day"]] = {"fare" : row["fare"], "food" : row["food"], "other" : row["other"], "total" : row["total"]}
            total_fare += row["fare"]
            total_food += row["food"]
            total_other += row["other"]

        total_spent = total_fare + total_food + total_other
        return jsonify({
            "allowance" : budget["allowance"],
            "expenses" : expenses,
            "totals" : {"fare" : total_fare, "food" : total_food, "other" : total_other, "spent" : total_spent, "remaining" : budget["allowance"] - total_spent},
            "days_logged" : len(expenses)
        })
    except Exception as e:
        return jsonify({"error" : str(e)}), 500
    
@api.route("/monthly-summary", methods = ["GET"])
@login_required
def monthly_summary():
    try:
        user_id = get_user_id()
        month = request.args.get("month", datetime.now().month, type = int)
        year = request.args.get("year",  datetime.now().year, type = int)

        start_date = datetime(year, month, 1).date()
        end_date = datetime(year + 1, 1, 1).date() if month == 12 else datetime (year, month + 1, 1).date()

        weeks = db.get_budgets_by_month(user_id, start_date, end_date)
        breakdown = db.get_monthly_expense_breakdown(user_id, start_date, end_date)

        total_allowance = sum(w["allowance"] for w in weeks)
        total_spent = sum(w["total_spent"] for w in weeks)

        weekly_data = [{"week_start" : w["week_start_date"], "allowance" : w["allowance"], "spent" : w["total_spent"], "saved" : w["allowance"] - w["total_spent"]} for w in weeks]
        return jsonify({
            "month" : month, "year" : year,
            "month_name" : datetime(year, month, 1).strftime("%B %Y"),
            "total_allowance" : total_allowance,
            "total_spent" : total_spent,
            "total_saved" : total_allowance - total_spent,
            "breakdown" : {"fare" : breakdown["total_fare"], "food" : breakdown["total_food"], "other" : breakdown["total_other"]},
            "weeks" : weekly_data,
            "num_weeks" : len(weekly_data)
        })
    except Exception as e:
        return jsonify({"error" : str(e)}), 500

#PDF Export Routes
@api.route("/export-pdf", methods = ["GET"])
@login_required
def export_pdf():
    try:
        user_id = get_user_id()
        week_start, week_end = get_week_range()
        budget = db.get_budget_by_week(user_id, week_start, week_end)

        if not budget:
            return jsonify({"error" : "Budget not found."}), 404
        
        expenses_rows = db.get_expenses_by_budget(budget["id"])
        total_fare = sum(r["fare"] for r in expenses_rows)
        total_food = sum(r["food"] for r in expenses_rows)
        total_other = sum(r["other"] for r in expenses_rows)
        total_spent = total_fare + total_food + total_other

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, page_size = letter, topMargin = 0.5 * inch)
        elements = []
        styles = getSampleStyleSheet()

        elements.append (Paragraph("Budget Tracker - Weekly Report", styles["Heading1"]))
        elements.append (Paragraph(f"Week: {week_start} to {week_end}", styles["Normal"]))
        elements.append (Paragraph(Spacer(1, 20)))

        summary_data = [['Allowance', f'₱{budget["allowance"]:.2f}'], ['Total Spent', f'₱{total_spent:.2f}'], ['Remaining', f'₱{budget["allowance"] - total_spent:.2f}']]
        summary_table = Table(summary_data, colWidths=[2 * inch, 2 * inch])
        summary_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor('#f8fafc')), ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')), ('PADDING', (0, 0), (-1, -1), 12)]))
        elements.append(summary_table)
        elements.append(Spacer (1, 20))

        expense_data = [['Day', 'Fare', 'Food', 'Other', 'Total']]
        for row in expenses_rows:
            expense_data.append([row['day'], f'₱{row["fare"]:.2f}', f'₱{row["food"]:.2f}', f'₱{row["other"]:.2f}', f'₱{row["total"]:.2f}'])
        
        expense_table = Table(expense_data, colWidths=[1.2*inch, 1*inch, 1*inch, 1*inch, 1*inch])
        expense_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')), ('PADDING', (0, 0), (-1, -1), 8)]))
        elements.append(expense_table)
        
        doc.build(elements)
        buffer.seek(0)
        
        response = make_response(buffer.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=budget_{week_start}.pdf'
        return response
    except Exception as e:
        return jsonify({"error" : str(e)}, 500)
    
@api.route('/export-monthly-pdf', methods=['GET'])
@login_required
def export_monthly_pdf():
    try:
        user_id = get_user_id()
        month = request.args.get('month', datetime.now().month, type=int)
        year = request.args.get('year', datetime.now().year, type=int)
        
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year + 1, 1, 1).date() if month == 12 else datetime(year, month + 1, 1).date()
        
        weeks = db.get_budgets_by_month(user_id, start_date, end_date)
        breakdown = db.get_monthly_expense_breakdown(user_id, start_date, end_date)
        
        total_allowance = sum(w['allowance'] for w in weeks)
        total_spent = sum(w['total_spent'] for w in weeks)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph(f'Budget Report - {datetime(year, month, 1).strftime("%B %Y")}', styles['Heading1']))
        elements.append(Spacer(1, 20))
        
        summary_data = [['Total Allowance', f'₱{total_allowance:.2f}'], ['Total Spent', f'₱{total_spent:.2f}'], ['Total Saved', f'₱{total_allowance - total_spent:.2f}']]
        summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
        summary_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')), ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')), ('PADDING', (0, 0), (-1, -1), 12)]))
        elements.append(summary_table)
        
        doc.build(elements)
        buffer.seek(0)
        
        response = make_response(buffer.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=monthly_{year}_{month}.pdf'
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500