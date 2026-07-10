from flask import Blueprint, request, jsonify, session, Response
from datetime import datetime, timedelta
import csv
import database as db
from io import StringIO
from functools import wraps
import google.generativeai as genai
import logging
import os
import secrets
from api.categorize import categorize_item, CATEGORY_LABELS, CATEGORIES
from api.security import issue_csrf_token, verify_request_origin
from api.email_service import (
    mail_configured,
    send_password_reset_email,
    send_password_reset_email_background,
)
from api.errors import GEMINI_ERRORS, handle_api_errors, internal_error
from api.pdf_report import build_monthly_pdf, pdf_response
from extensions import limiter

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__, url_prefix="/api")

CSRF_EXEMPT_ENDPOINTS = frozenset({
    "api.forgot_password",
    "api.reset_password",
})


@api.before_request
def enforce_api_security():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None

    endpoint = request.endpoint or ""
    if endpoint in CSRF_EXEMPT_ENDPOINTS:
        if not verify_request_origin():
            return jsonify({"error": "Invalid request origin"}), 403
        return None

    if not verify_request_origin():
        return jsonify({"error": "Invalid request origin"}), 403

    sent = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token")
    if not expected or not sent or not secrets.compare_digest(sent, expected):
        return jsonify({"error": "Invalid or missing CSRF token"}), 403
    return None

MAX_USERNAME_LEN = db.MAX_USERNAME_LEN
MAX_EMAIL_LEN = db.MAX_EMAIL_LEN
MAX_ITEM_NAME_LEN = db.MAX_ITEM_NAME_LEN
MAX_PASSWORD_LEN = 128

prompt = (
    "You are a financial assistant that provides insights and recommendations based on the user's budget weekly data.\n"
    "Give exactly 3 lines, a short paragraph/analysis.\n"
    "Provide actionable advice for the user to improve their spending habits and manage their budget effectively.\n"
    "Maximum of 80 characters.\n"
    "Return only the 3 lines, no bullet points, no numbering, only follow the instruction stated above.\n"
    "Mention the username.\n"
    "Always use'&#8369;' when mentioning amounts.\n"
    "You may use this as reference for the data structure:\n"
    "- Username : {username}\n"
    "- Allowance : &#8369;{allowance:.2f}\n"
    "- Spending by category :\n"
    "{category_lines}\n"
    "- Total Spent : &#8369;{spent:.2f}\n"
    "- Remaining : &#8369;{remaining:.2f}"
)


def generate_budget_insights(allowance, totals, period="week"):
    try:
        category_lines = "\n".join(
            f"            - {CATEGORY_LABELS[c]} : &#8369;{totals.get(c, 0):.2f}"
            for c in CATEGORIES
            if totals.get(c, 0) > 0
        ) or "            - No category spending yet"
        notes = prompt.format(
            username=session.get("username"),
            allowance = allowance,
            category_lines = category_lines,
            spent = totals['spent'],
            remaining = totals['remaining'],
        )
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        response = model.generate_content(notes)
        lines = [line.strip().replace("₱", "&#8369;") for line in response.text.strip().split("\n") if line.strip()]
        return lines[:3]
    except GEMINI_ERRORS as exc:
        logger.warning("Gemini insight generation failed: %s", exc)
        return [
            "Review your spending habits to identify areas for improvement.",
            "Consider setting aside a portion of your remaining budget for savings.",
            "Track your expenses daily to stay within your allowance and avoid overspending.",
        ]

DAYS_MAP = {
    "Sunday": 0, "Monday": 1, "Tuesday": 2, "Wednesday": 3,
    "Thursday": 4, "Friday": 5, "Saturday": 6,
}


def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    if not any(c in "!@#$%^&*(),.?\":{}|<>" for c in password):
        return False, "Password must contain at least one special character"
    return True, "Valid password"


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def get_user_id():
    return session.get("user_id")


def build_expenses_payload(rows, items_by_expense):
    expenses = {}
    cat_totals = {c: 0 for c in CATEGORIES}
    for r in rows:
        items = items_by_expense.get(r["id"], [])
        breakdown = db.breakdown_from_row(r, items)
        expenses[r["day"]] = {
            **breakdown,
            "total": db.as_float(r["total"]),
            "items": items,
        }
        for c in CATEGORIES:
            cat_totals[c] += breakdown[c]
    return expenses, cat_totals


def serialize_expenses(expenses):
    result = {}
    for day, exp in expenses.items():
        result[day] = {
            **{c: db.as_float(exp[c]) for c in CATEGORIES},
            "total": db.as_float(exp["total"]),
            "items": [{
                "id": item["id"],
                "name": item["name"],
                "amount": db.as_float(item["amount"]),
                "category": item["category"],
            } for item in exp.get("items", [])],
        }
    return result


def json_budget_payload(budget, rows, items_by_expense, user_id=None):
    expenses, cat_totals = build_expenses_payload(rows, items_by_expense)
    allowance = db.as_float(budget["allowance"])
    spent = sum(cat_totals.values())
    totals = {
        **{c: cat_totals[c] for c in CATEGORIES},
        "spent": spent,
        "remaining": allowance - spent,
    }
    payload = {
        "allowance": allowance,
        "expenses": serialize_expenses(expenses),
        "totals": totals,
        "days_logged": len(expenses),
    }
    if user_id is not None:
        limits = db.get_category_limits(user_id)
        payload["category_limits"] = limits
        payload["category_status"] = db.build_category_status(totals, limits)
    return payload


def empty_budget_payload():
    return {
        "allowance": 0,
        "expenses": {},
        "totals": {**{c: 0 for c in CATEGORIES}, "spent": 0, "remaining": 0},
        "days_logged": 0,
    }


def week_info_payload():
    week_start, week_end = get_week_range()
    today = datetime.now().date()
    days_remaining = (week_end - today).days + 1
    return {
        "week_start": str(week_start),
        "week_end": str(week_end),
        "current_day": get_current_day(),
        "days_remaining": max(1, days_remaining),
        "week_start_formatted": week_start.strftime("%B %d, %Y"),
        "week_end_formatted": week_end.strftime("%B %d, %Y"),
    }


def mutation_payload(day, day_expense, budget_totals, user_id=None):
    payload = {
        "success": True,
        "day": day,
        "expense": day_expense,
        "totals": budget_totals,
    }
    if user_id is not None:
        limits = db.get_category_limits(user_id)
        payload["category_limits"] = limits
        payload["category_status"] = db.build_category_status(budget_totals, limits)
        payload["category_rules"] = db.get_user_category_rules(user_id)
    return payload


def get_week_range():
    today      = datetime.now().date()
    week_start = today - timedelta(days=(today.weekday() + 1) % 7)
    return week_start, week_start + timedelta(days=6)


def get_current_day():
    return ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"][datetime.now().weekday()]


RESET_SENT_MESSAGE = (
    "If an account exists for that email, reset instructions have been sent."
)

FORGOT_PASSWORD_LIMIT = (
    "20 per hour" if os.environ.get("FLASK_ENV", "development") != "production" else "5 per hour"
)
RESET_PASSWORD_LIMIT = (
    "30 per hour" if os.environ.get("FLASK_ENV", "development") != "production" else "10 per hour"
)
CHANGE_PASSWORD_LIMIT = (
    "30 per hour" if os.environ.get("FLASK_ENV", "development") != "production" else "10 per hour"
)


def app_base_url():
    return os.environ.get("APP_BASE_URL", "http://localhost:5173").rstrip("/")


@api.route("/csrf-token", methods=["GET"])
def csrf_token():
    return jsonify({"csrf_token": issue_csrf_token()})


@api.route("/forgot-password", methods=["POST"])
@limiter.limit(FORGOT_PASSWORD_LIMIT)
@handle_api_errors
def forgot_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Invalid email address."}), 400
    if len(email) > MAX_EMAIL_LEN:
        return jsonify({"error": "Invalid email address."}), 400

    user = db.get_user_by_email(email)
    if user:
        raw_token = db.create_password_reset_token(user["id"])
        reset_url = f"{app_base_url()}/reset-password?token={raw_token}"
        if mail_configured():
            send_password_reset_email_background(email, reset_url)
        else:
            send_password_reset_email(email, reset_url)

    return jsonify({"success": True, "message": RESET_SENT_MESSAGE})


@api.route("/reset-password", methods=["POST"])
@limiter.limit(RESET_PASSWORD_LIMIT)
@handle_api_errors
def reset_password():
    data = request.get_json() or {}
    raw_token = (data.get("token") or "").strip()
    password = (data.get("password") or "").strip()

    if not raw_token:
        return jsonify({"error": "Reset token is required."}), 400
    is_valid, msg = validate_password(password)
    if not is_valid:
        return jsonify({"error": msg}), 400
    if len(password) > MAX_PASSWORD_LEN:
        return jsonify({"error": "Password is too long."}), 400

    user_id = db.consume_password_reset_token(raw_token)
    if not user_id:
        return jsonify({"error": "Invalid or expired reset link."}), 400

    if not db.update_user_password(user_id, password):
        return jsonify({"error": "Unable to reset password."}), 500

    return jsonify({"success": True, "message": "Password updated. You can sign in now."})


@api.route("/register", methods=["POST"])
@limiter.limit("5 per hour")
@handle_api_errors
def register():
    data     = request.get_json()
    username = data.get("username", "").strip()
    email    = data.get("email",    "").strip().lower()
    password = data.get("password", "").strip()

    if not username or len(username) < 5:
        return jsonify({"error": "Username must be at least 5 characters long."}), 400
    if len(username) > MAX_USERNAME_LEN:
        return jsonify({"error": f"Username must be at most {MAX_USERNAME_LEN} characters."}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Invalid email address."}), 400
    if len(email) > MAX_EMAIL_LEN:
        return jsonify({"error": f"Email must be at most {MAX_EMAIL_LEN} characters."}), 400
    if len(password) > MAX_PASSWORD_LEN:
        return jsonify({"error": "Password is too long."}), 400
    is_valid, msg = validate_password(password)
    if not is_valid:
        return jsonify({"error": msg}), 400
    if db.get_user_by_username(username):
        return jsonify({"error": "Username already exists"}), 400
    if db.get_user_by_email(email):
        return jsonify({"error": "An account is already registered with this email"}), 400

    user_id = db.create_user(username, email, password)
    if user_id:
        if not db.get_user_by_email(email):
            logger.error(
                "register: user_id=%s was returned but email %s not found in database",
                user_id,
                email,
            )
            return jsonify({"error": "Registration failed"}), 500
        session["user_id"]  = user_id
        session["username"] = username
        return jsonify({"success": True, "username": username})
    return jsonify({"error": "Registration failed"}), 500


@api.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
@handle_api_errors
def login():
    data     = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) > MAX_USERNAME_LEN or len(password) > MAX_PASSWORD_LEN:
        return jsonify({"error": "Invalid credentials"}), 400
    user = db.get_user_by_username(username)
    if not user:
        return jsonify({"error": "Username does not exist"}), 401
    if not db.verify_password(user, password):
        return jsonify({"error": "Incorrect password"}), 401

    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    return jsonify({"success": True, "username": user["username"]})


@api.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@api.route("/check-auth", methods=["GET"])
def check_auth():
    if "user_id" in session:
        return jsonify({"authenticated": True, "username": session.get("username")})
    return jsonify({"authenticated": False})


@api.route("/profile", methods=["GET"])
@login_required
@handle_api_errors
def get_profile():
    user = db.get_user_by_id(get_user_id())
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"username": user["username"], "email": user["email"]})


@api.route("/profile", methods=["PUT"])
@login_required
@handle_api_errors
def update_profile():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()

    user_id = get_user_id()
    user = db.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not username and not email:
        return jsonify({"error": "Nothing to update."}), 400

    if username:
        if len(username) < 5:
            return jsonify({"error": "Username must be at least 5 characters long."}), 400
        if len(username) > MAX_USERNAME_LEN:
            return jsonify({"error": f"Username must be at most {MAX_USERNAME_LEN} characters."}), 400
        if username != user["username"] and db.get_user_by_username(username):
            return jsonify({"error": "Username already exists"}), 400
    else:
        username = user["username"]

    if email:
        if "@" not in email:
            return jsonify({"error": "Invalid email address."}), 400
        if len(email) > MAX_EMAIL_LEN:
            return jsonify({"error": f"Email must be at most {MAX_EMAIL_LEN} characters."}), 400
        normalized = db.normalize_email(email)
        if normalized != db.normalize_email(user["email"]) and db.get_user_by_email(email):
            return jsonify({"error": "An account is already registered with this email"}), 400
    else:
        email = user["email"]

    if username == user["username"] and db.normalize_email(email) == db.normalize_email(user["email"]):
        return jsonify({"success": True, "username": username, "email": email})

    if not db.update_user_profile(user_id, username=username, email=email):
        return jsonify({"error": "Username or email is already in use."}), 400

    session["username"] = username
    return jsonify({"success": True, "username": username, "email": email})


@api.route("/change-password", methods=["POST"])
@login_required
@limiter.limit(CHANGE_PASSWORD_LIMIT)
@handle_api_errors
def change_password():
    data = request.get_json() or {}
    current_password = data.get("current_password") or ""
    new_password = (data.get("new_password") or "").strip()

    if not current_password or not new_password:
        return jsonify({"error": "Current and new password are required."}), 400
    if len(new_password) > MAX_PASSWORD_LEN:
        return jsonify({"error": "Password is too long."}), 400

    user_id = get_user_id()
    user = db.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if not db.verify_password(user, current_password):
        return jsonify({"error": "Current password is incorrect."}), 401

    is_valid, msg = validate_password(new_password)
    if not is_valid:
        return jsonify({"error": msg}), 400
    if db.verify_password(user, new_password):
        return jsonify({"error": "New password must be different from your current password."}), 400

    if not db.update_user_password(user_id, new_password):
        return jsonify({"error": "Unable to update password."}), 500

    db.invalidate_password_reset_tokens(user_id)
    return jsonify({"success": True, "message": "Password updated."})


@api.route("/current-week-info", methods=["GET"])
@login_required
def current_week_info():
    return jsonify(week_info_payload())


@api.route("/dashboard", methods=["GET"])
@login_required
@handle_api_errors
def dashboard():
        user_id = get_user_id()
        week_start, week_end = get_week_range()
        db.process_recurring_expenses(user_id, week_start, week_end)
        budget, rows, items_by_expense, comparison = db.fetch_dashboard(
            user_id, week_start, week_end,
        )
        budget_data = (
            json_budget_payload(budget, rows, items_by_expense, user_id=user_id)
            if budget else empty_budget_payload()
        )
        return jsonify({
            "username": session.get("username"),
            "week_info": week_info_payload(),
            "budget": budget_data,
            "comparison": comparison,
            "category_rules": db.get_user_category_rules(user_id),
        })


@api.route("/set-allowance", methods=["POST"])
@login_required
@handle_api_errors
def set_allowance():
    data      = request.get_json()
    allowance = float(data.get("allowance", 0))
    if allowance <= 0:
        return jsonify({"error": "Allowance must be greater than 0"}), 400

    user_id = get_user_id()
    week_start, week_end = get_week_range()
    existing = db.get_budget_by_week(user_id, week_start, week_end)
    if existing:
        if not db.update_budget(existing["id"], user_id, allowance):
            return jsonify({"error": "Budget not found."}), 404
        budget_id = existing["id"]
    else:
        budget_id = db.create_budget(user_id, week_start, week_end, allowance)

    with db.db_cursor(dict_cursor=True) as cursor:
        totals = db.compute_budget_totals(cursor, budget_id)
    return jsonify({
        "success": True,
        "allowance": allowance,
        "budget_id": budget_id,
        "totals": totals,
    })


@api.route("/categorize-item", methods=["POST"])
@login_required
@handle_api_errors
def categorize_item_route():
        data = request.get_json()
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Item name is required"}), 400
        if len(name) > MAX_ITEM_NAME_LEN:
            return jsonify({"error": f"Item name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
        user_rules = db.get_user_category_rules(get_user_id())
        category = categorize_item(name, user_rules)
        return jsonify({
            "category": category,
            "label": CATEGORY_LABELS[category],
        })


@api.route("/add-expense-item", methods=["POST"])
@login_required
@handle_api_errors
def add_expense_item_route():
    data = request.get_json()
    user_id = get_user_id()
    week_start, week_end = get_week_range()

    day = data.get("day")
    name = (data.get("name") or "").strip()
    amount = float(data.get("amount", 0))
    category = (data.get("category") or "").strip().lower()

    if not day:
        return jsonify({"error": "Day is required"}), 400
    if not name:
        return jsonify({"error": "Item name is required"}), 400
    if len(name) > MAX_ITEM_NAME_LEN:
        return jsonify({"error": f"Item name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400

    if category not in CATEGORIES:
        user_rules = db.get_user_category_rules(user_id)
        category = categorize_item(name, user_rules)

    expense_date = week_start + timedelta(days=DAYS_MAP.get(day, 0))
    budget = db.get_budget_by_week(user_id, week_start, week_end)
    if not budget:
        return jsonify({"error": "Please set allowance first."}), 404

    item, day, day_expense, budget_totals = db.add_expense_item(
        budget["id"], day, expense_date, name, amount, category,
    )
    db.learn_category_correction(user_id, name, category)
    return jsonify({
        **mutation_payload(day, day_expense, budget_totals, user_id),
        "item": {
            "id": item["id"],
            "name": item["name"],
            "amount": db.as_float(item["amount"]),
            "category": item["category"],
        },
    })


@api.route("/edit-expense-item/<int:item_id>", methods=["PUT"])
@login_required
@handle_api_errors
def edit_expense_item_route(item_id):
    data = request.get_json()
    user_id = get_user_id()
    name = (data.get("name") or "").strip()
    amount = float(data.get("amount", 0))
    category = (data.get("category") or "").strip().lower()

    if not name:
        return jsonify({"error": "Item name is required"}), 400
    if len(name) > MAX_ITEM_NAME_LEN:
        return jsonify({"error": f"Item name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400
    if category not in CATEGORIES:
        user_rules = db.get_user_category_rules(user_id)
        category = categorize_item(name, user_rules)

    item, day, day_expense, budget_totals = db.update_expense_item(item_id, user_id, name, amount, category)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    db.learn_category_correction(user_id, name, category)

    week_start, week_end = get_week_range()
    return jsonify({
        **mutation_payload(day, day_expense, budget_totals, user_id),
        "item": {
            "id": item["id"],
            "name": item["name"],
            "amount": db.as_float(item["amount"]),
            "category": item["category"],
        },
    })


@api.route("/delete-expense-item/<int:item_id>", methods=["DELETE"])
@login_required
@handle_api_errors
def delete_expense_item_route(item_id):
    user_id = get_user_id()
    week_start, week_end = get_week_range()
    deleted, day, day_expense, budget_totals, deleted_item = db.delete_expense_item(item_id, user_id)
    if deleted:
        return jsonify({
            **mutation_payload(day, day_expense, budget_totals, user_id),
            "deleted_item": deleted_item,
        })
    return jsonify({"error": "Item not found"}), 404




@api.route("/delete-expense/<day>", methods=["DELETE"])
@login_required
def delete_expense(day):
        user_id = get_user_id()
        week_start, week_end = get_week_range()
        budget = db.get_budget_by_week(user_id, week_start, week_end)
        if not budget:
            return jsonify({"error": "Budget not found."}), 404
        deleted, budget_totals = db.delete_expense_by_day(budget["id"], day)
        if deleted:
            week_start, week_end = get_week_range()
            return jsonify(mutation_payload(day, None, budget_totals, user_id))
        return jsonify({"error": f"No expenses for {day}"}), 404


@api.route("/get-budget", methods=["GET"])
@login_required
@handle_api_errors
def get_budget():
    user_id = get_user_id()
    week_start, week_end = get_week_range()
    budget, rows, items_by_expense = db.fetch_week_budget(user_id, week_start, week_end)

    if not budget:
        return jsonify(empty_budget_payload())

    return jsonify(json_budget_payload(budget, rows, items_by_expense))


@api.route("/budget-settings", methods=["GET"])
@login_required
@handle_api_errors
def get_budget_settings():
    user_id = get_user_id()
    return jsonify({
        "category_limits": db.get_category_limits(user_id),
        "recurring_expenses": db.get_recurring_expenses(user_id),
        "category_rules": db.get_user_category_rules(user_id),
    })


@api.route("/category-limits", methods=["PUT"])
@login_required
@handle_api_errors
def update_category_limits():
    data = request.get_json() or {}
    limits_in = data.get("limits") or {}
    if not isinstance(limits_in, dict):
        return jsonify({"error": "limits must be an object."}), 400

    parsed = {}
    for category, value in limits_in.items():
        if category not in CATEGORIES:
            continue
        if value is None or value == "":
            parsed[category] = None
        else:
            amount = float(value)
            if amount <= 0:
                parsed[category] = None
            else:
                parsed[category] = amount

    user_id = get_user_id()
    db.set_category_limits(user_id, parsed)
    limits = db.get_category_limits(user_id)
    week_start, week_end = get_week_range()
    budget = db.get_budget_by_week(user_id, week_start, week_end)
    totals = {**{c: 0 for c in CATEGORIES}, "spent": 0, "remaining": 0}
    if budget:
        with db.db_cursor(dict_cursor=True) as cursor:
            totals = db.compute_budget_totals(cursor, budget["id"])
    return jsonify({
        "success": True,
        "category_limits": limits,
        "category_status": db.build_category_status(totals, limits),
    })


@api.route("/recurring-expenses", methods=["GET"])
@login_required
@handle_api_errors
def list_recurring_expenses():
    return jsonify({"recurring_expenses": db.get_recurring_expenses(get_user_id())})


@api.route("/recurring-expenses", methods=["POST"])
@login_required
@handle_api_errors
def create_recurring_expense_route():
    data = request.get_json() or {}
    user_id = get_user_id()
    name = (data.get("name") or "").strip()
    amount = float(data.get("amount", 0))
    category = (data.get("category") or "").strip().lower()
    frequency = (data.get("frequency") or "").strip().lower()

    if not name:
        return jsonify({"error": "Name is required."}), 400
    if len(name) > MAX_ITEM_NAME_LEN:
        return jsonify({"error": f"Name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0."}), 400
    if frequency not in ("weekly", "monthly"):
        return jsonify({"error": "Frequency must be weekly or monthly."}), 400
    if category not in CATEGORIES:
        category = categorize_item(name, db.get_user_category_rules(user_id))

    apply_day = None
    apply_day_of_month = None
    if frequency == "weekly":
        apply_day = (data.get("apply_day") or "Sunday").strip()
        if apply_day not in DAYS_MAP:
            return jsonify({"error": "Invalid apply_day."}), 400
    else:
        apply_day_of_month = int(data.get("apply_day_of_month") or 1)
        if apply_day_of_month < 1 or apply_day_of_month > 31:
            return jsonify({"error": "Day of month must be between 1 and 31."}), 400

    recurring_id = db.create_recurring_expense(
        user_id, name, amount, category, frequency, apply_day, apply_day_of_month,
    )
    return jsonify({
        "success": True,
        "id": recurring_id,
        "recurring_expenses": db.get_recurring_expenses(user_id),
    })


@api.route("/recurring-expenses/<int:recurring_id>", methods=["PUT"])
@login_required
@handle_api_errors
def update_recurring_expense_route(recurring_id):
    data = request.get_json() or {}
    user_id = get_user_id()
    existing = db.get_recurring_expense(recurring_id, user_id)
    if not existing:
        return jsonify({"error": "Recurring expense not found."}), 404

    fields = {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name is required."}), 400
        if len(name) > MAX_ITEM_NAME_LEN:
            return jsonify({"error": f"Name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
        fields["name"] = name
    if "amount" in data:
        amount = float(data.get("amount", 0))
        if amount <= 0:
            return jsonify({"error": "Amount must be greater than 0."}), 400
        fields["amount"] = amount
    if "category" in data:
        category = (data.get("category") or "").strip().lower()
        if category not in CATEGORIES:
            return jsonify({"error": "Invalid category."}), 400
        fields["category"] = category
    if "frequency" in data:
        frequency = (data.get("frequency") or "").strip().lower()
        if frequency not in ("weekly", "monthly"):
            return jsonify({"error": "Frequency must be weekly or monthly."}), 400
        fields["frequency"] = frequency
    if "apply_day" in data:
        apply_day = (data.get("apply_day") or "").strip()
        if apply_day not in DAYS_MAP:
            return jsonify({"error": "Invalid apply_day."}), 400
        fields["apply_day"] = apply_day
    if "apply_day_of_month" in data:
        apply_day_of_month = int(data.get("apply_day_of_month") or 1)
        if apply_day_of_month < 1 or apply_day_of_month > 31:
            return jsonify({"error": "Day of month must be between 1 and 31."}), 400
        fields["apply_day_of_month"] = apply_day_of_month
    if "active" in data:
        fields["active"] = bool(data.get("active"))

    if not db.update_recurring_expense(recurring_id, user_id, **fields):
        return jsonify({"error": "Recurring expense not found."}), 404
    return jsonify({
        "success": True,
        "recurring_expenses": db.get_recurring_expenses(user_id),
    })


@api.route("/recurring-expenses/<int:recurring_id>", methods=["DELETE"])
@login_required
@handle_api_errors
def delete_recurring_expense_route(recurring_id):
    user_id = get_user_id()
    if not db.delete_recurring_expense(recurring_id, user_id):
        return jsonify({"error": "Recurring expense not found."}), 404
    return jsonify({
        "success": True,
        "recurring_expenses": db.get_recurring_expenses(user_id),
    })


@api.route("/monthly-summary", methods=["GET"])
@login_required
@handle_api_errors
def monthly_summary():
    user_id = get_user_id()
    month   = request.args.get("month", datetime.now().month, type=int)
    year    = request.args.get("year",  datetime.now().year,  type=int)

    start_date = datetime(year, month, 1).date()
    end_date   = (datetime(year + 1, 1, 1).date() if month == 12
                  else datetime(year, month + 1, 1).date())

    weeks, breakdown = db.get_monthly_summary(user_id, start_date, end_date)

    total_allowance = sum(db.as_float(w["allowance"]) for w in weeks)
    total_spent = sum(db.as_float(w["total_spent"]) for w in weeks)
    weekly_data = [
        {
            "week_start": str(w["week_start_date"]),
            "allowance": db.as_float(w["allowance"]),
            "spent": db.as_float(w["total_spent"]),
            "saved": db.as_float(w["allowance"]) - db.as_float(w["total_spent"]),
        }
        for w in weeks
    ]
    return jsonify({
        "month": month, "year": year,
        "month_name": datetime(year, month, 1).strftime("%B %Y"),
        "total_allowance": total_allowance,
        "total_spent": total_spent,
        "total_saved": total_allowance - total_spent,
        "breakdown": {c: breakdown.get(c, 0) for c in CATEGORIES},
        "weeks": weekly_data,
        "num_weeks": len(weekly_data),
    })


@api.route("/export-csv", methods=["GET"])
@login_required
@handle_api_errors
def export_csv():
    user_id = get_user_id()
    scope = request.args.get("scope", "week")
    if scope == "month":
        month = request.args.get("month", datetime.now().month, type=int)
        year = request.args.get("year", datetime.now().year, type=int)
        start_date = datetime(year, month, 1).date()
        end_date = (
            datetime(year + 1, 1, 1).date() if month == 12
            else datetime(year, month + 1, 1).date()
        )
        filename = f"budget-{year}-{month:02d}.csv"
    else:
        week_start, week_end = get_week_range()
        start_date = week_start
        end_date = week_end + timedelta(days=1)
        filename = f"budget-week-{week_start}.csv"

    rows = db.fetch_export_rows(user_id, start_date, end_date)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Day", "Item", "Category", "Amount"])
    for row in rows:
        writer.writerow([
            row["expense_date"],
            row["day"],
            row["name"],
            CATEGORY_LABELS.get(row["category"], row["category"]),
            f'{row["amount"]:.2f}',
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.route("/week-detail", methods=["GET"])
@login_required
@handle_api_errors
def week_detail():
    user_id = get_user_id()
    week_start_str = request.args.get("week_start")
    if not week_start_str:
        return jsonify({"error": "week_start is required"}), 400

    try:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid week_start format"}), 400

    week_end = week_start + timedelta(days=6)
    budget, rows, items_by_expense = db.fetch_week_budget(user_id, week_start, week_end)
    if not budget:
        return jsonify({"error": "Week not found"}), 404

    payload = json_budget_payload(budget, rows, items_by_expense)
    return jsonify({
        "week_start": str(week_start),
        "week_end": str(week_end),
        "week_start_formatted": week_start.strftime("%B %d, %Y"),
        "week_end_formatted": week_end.strftime("%B %d, %Y"),
        **payload,
    })


@api.route("/week-comparison", methods=["GET"])
@login_required
@handle_api_errors
def week_comparison():
        user_id = get_user_id()
        week_start, week_end = get_week_range()
        return jsonify(db.get_week_comparison(user_id, week_start, week_end))


@api.route("/export-monthly-pdf", methods=["GET"])
@login_required
@handle_api_errors
def export_monthly_pdf():
    user_id = get_user_id()
    month = request.args.get("month", datetime.now().month, type=int)
    year = request.args.get("year", datetime.now().year, type=int)

    start_date = datetime(year, month, 1).date()
    end_date = (
        datetime(year + 1, 1, 1).date() if month == 12
        else datetime(year, month + 1, 1).date()
    )

    weeks, breakdown = db.get_monthly_summary(user_id, start_date, end_date)
    cat_totals = {category: db.as_float(breakdown.get(category, 0)) for category in CATEGORIES}
    total_allowance = sum(db.as_float(week["allowance"]) for week in weeks)
    total_spent = sum(db.as_float(week["total_spent"]) for week in weeks)
    insights = generate_budget_insights(
        total_allowance,
        {**cat_totals, "spent": total_spent, "remaining": total_allowance - total_spent},
        period="month",
    )
    buffer = build_monthly_pdf(year, month, weeks, cat_totals, insights)
    return pdf_response(buffer, f"{year}_{month}.pdf")


