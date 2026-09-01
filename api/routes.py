from flask import Blueprint, request, jsonify, session, Response, send_file, current_app, g
from datetime import datetime, timedelta, timezone
import csv
import database as db
from io import StringIO
from functools import wraps
import logging
import os
import secrets
import time
import uuid
from api.categorize import CATEGORIES
from api.category_service import build_category_context, classify_category
from api.security import issue_csrf_token, verify_request_origin
from api.email_service import (
    delivery_transport_name,
    mail_configured,
    send_email_verification,
    send_email_verification_background,
    send_password_reset_email,
    send_password_reset_email_background,
    send_saturday_reminder_email_background,
)
from api.errors import handle_api_errors, internal_error
from api.insights import build_insights, generate_budget_insights
from api.anomalies import HISTORY_WINDOW_DAYS, build_anomaly_report
from api.account_export import build_account_export
from api.pdf_report import build_monthly_pdf, build_yearly_pdf, build_range_pdf, pdf_response
from api.receipt_providers.base import ReceiptProviderError, ReceiptProviderUnavailable
from api.receipt_providers import GeminiReceiptProvider
from api.receipt_schema import MAX_RECEIPT_ITEMS, ReceiptSchemaError, money_value
from api.receipt_service import ReceiptBusyError, ReceiptUploadError, extract_receipt
from extensions import limiter

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__, url_prefix="/api")

CSRF_EXEMPT_ENDPOINTS = frozenset({
    "api.forgot_password",
    "api.resend_verification",
    "api.reset_password",
    "api.verify_email",
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
MAX_ITEM_NOTES_LEN = db.MAX_ITEM_NOTES_LEN
MAX_TAG_LEN = db.MAX_TAG_LEN
MAX_TAGS_PER_ITEM = db.MAX_TAGS_PER_ITEM
MAX_PASSWORD_LEN = 128
ACCOUNT_EXPORT_LIMIT = "3 per hour"
ACCOUNT_DELETION_LIMIT = "3 per day"
ADMIN_MUTATION_LIMIT = "10 per hour"
ADMIN_EMAIL_LIMIT = "6 per hour"
MAX_VERIFICATION_TOKEN_LEN = 256
MAX_ADMIN_SEARCH_LEN = 100
MAX_ADMIN_REASON_LEN = 250
ADMIN_PAGE_SIZE = 20
ADMIN_MAX_PAGE_SIZE = 50
RECEIPT_SCAN_LIMIT = (
    "30 per hour"
    if os.environ.get("FLASK_ENV", "development") != "production"
    else "10 per hour"
)
RECEIPT_BATCH_LIMIT = "20 per hour"


def parse_item_notes_tags(data):
    try:
        notes = db.normalize_item_notes(data.get("notes", ""))
        tags = db.normalize_item_tags(data.get("tags"))
    except ValueError as exc:
        return None, None, str(exc)
    return notes, tags, None


def receipt_ocr_available():
    return bool(
        current_app.config.get("RECEIPT_OCR_ENABLED", False)
        and GeminiReceiptProvider.configured_api_key()
    )


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
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        try:
            exists = db.user_exists(user_id, int(session.get("session_version") or 0))
        except Exception as error:
            logger.exception("Authentication lookup failed: %s", error)
            return internal_error()
        if not exists:
            session.clear()
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_app.config.get("ADMIN_DASHBOARD_ENABLED", True):
            return jsonify({"error": "Not found"}), 404
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        try:
            state = db.get_user_auth_state(user_id)
        except Exception as error:
            logger.exception("Admin authorization lookup failed: %s", error)
            return internal_error()
        if not state or state.get("account_status") != "active" or not state.get("email_verified_at"):
            session.clear()
            return jsonify({"error": "Authentication required"}), 401
        if int(state.get("session_version") or 0) != int(session.get("session_version") or 0):
            session.clear()
            return jsonify({"error": "Authentication required"}), 401
        if state.get("role") != "admin":
            return jsonify({"error": "Administrator access required"}), 403
        g.admin_user = state
        return f(*args, **kwargs)
    return decorated


def admin_rate_limit_key():
    return f"admin:{session.get('user_id') or request.remote_addr or 'anonymous'}"


@api.after_request
def protect_sensitive_responses(response):
    if (
        request.path.startswith("/api/admin")
        or request.path.startswith("/api/receipt-scans")
    ):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


def get_user_id():
    return session.get("user_id")


def iso_datetime(value):
    return value.isoformat() if value else None


def serialize_admin_user(user):
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "account_status": user["account_status"],
        "email_verified": bool(user.get("email_verified_at")),
        "created_at": iso_datetime(user.get("created_at")),
        "last_login_at": iso_datetime(user.get("last_login_at")),
        "status_changed_at": iso_datetime(user.get("status_changed_at")),
        "sessions_revoked_at": iso_datetime(user.get("sessions_revoked_at")),
    }


def positive_int(value, default, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 1:
        return None
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def parse_admin_date(value, end=False):
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return parsed + timedelta(days=1) if end else parsed


def admin_request_id():
    raw_request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
    return "".join(
        char for char in raw_request_id if char.isalnum() or char in "-_."
    )[:64] or secrets.token_hex(8)


def parse_admin_action_request():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "Current password and reason are required."}), 400)
    current_password = data.get("current_password") or ""
    raw_reason = data.get("reason") or ""
    if not isinstance(current_password, str) or not isinstance(raw_reason, str):
        return None, (jsonify({"error": "Current password and reason are required."}), 400)
    reason = " ".join(raw_reason.split())
    if not current_password or len(reason) < 5:
        return None, (
            jsonify({"error": "Enter your current password and a reason of at least 5 characters."}),
            400,
        )
    if len(current_password) > MAX_PASSWORD_LEN or len(reason) > MAX_ADMIN_REASON_LEN:
        return None, (jsonify({"error": "Invalid account-management details."}), 400)
    return {
        "current_password": current_password,
        "reason": reason,
        "request_id": admin_request_id(),
    }, None


def denied_admin_action(status, user_id, action, reason, request_id):
    audit_target = None if status in ("invalid_password", "not_found", "forbidden") else user_id
    try:
        db.record_admin_audit_event(
            get_user_id(),
            audit_target,
            action,
            "denied",
            reason=reason,
            request_id=request_id,
        )
    except Exception as error:
        logger.warning("Could not record denied admin action error=%s", type(error).__name__)
    errors = {
        "invalid_password": ("Current password is incorrect.", 401),
        "self_target": ("You cannot perform this action on your own account.", 400),
        "admin_target": ("Administrator accounts cannot be changed here.", 400),
        "inactive_target": ("Suspended accounts cannot receive support emails.", 400),
        "not_found": ("Account not found.", 404),
        "forbidden": ("Administrator access required.", 403),
    }
    message, code = errors.get(status, ("The administrative action could not be completed.", 400))
    return jsonify({"error": message}), code


def resolve_category(user_id, category, name=""):
    allowed = db.allowed_category_slugs(user_id)
    category = (category or "").strip().lower()
    if category in allowed:
        return category
    user_rules = db.get_user_category_rules(user_id)
    return classify_category(
        name,
        user_rules=user_rules,
        category_context=build_category_context(db.get_user_categories(user_id)),
    )["category"]


def build_expenses_payload(rows, items_by_expense, categories=None):
    cats = categories if categories is not None else CATEGORIES
    expenses = {}
    cat_totals = {c: 0 for c in cats}
    for r in rows:
        items = items_by_expense.get(r["id"], [])
        breakdown = db.breakdown_from_row(r, items, cats)
        expenses[r["day"]] = {
            **breakdown,
            "total": db.as_float(r["total"]),
            "items": items,
        }
        for c in breakdown:
            cat_totals[c] = cat_totals.get(c, 0) + breakdown[c]
    return expenses, cat_totals


def serialize_expenses(expenses, categories=None):
    cats = categories if categories is not None else CATEGORIES
    result = {}
    for day, exp in expenses.items():
        day_cats = list(dict.fromkeys([*cats, *[k for k in exp.keys() if k not in ("total", "items")]]))
        result[day] = {
            **{c: db.as_float(exp.get(c, 0)) for c in day_cats},
            "total": db.as_float(exp["total"]),
            "items": [{
                "id": item["id"],
                "name": item["name"],
                "amount": db.as_float(item["amount"]),
                "category": item["category"],
                "notes": item.get("notes") or "",
                "tags": list(item.get("tags") or []),
            } for item in exp.get("items", [])],
        }
    return result


def json_budget_payload(budget, rows, items_by_expense, user_id=None):
    categories = db.allowed_category_slugs(user_id) if user_id is not None else list(CATEGORIES)
    expenses, cat_totals = build_expenses_payload(rows, items_by_expense, categories)
    allowance = db.as_float(budget["allowance"])
    spent = sum(cat_totals.values())
    totals = {
        **{c: cat_totals.get(c, 0) for c in categories},
        "spent": spent,
        "remaining": allowance - spent,
    }
    for key, value in cat_totals.items():
        if key not in totals:
            totals[key] = value
    payload = {
        "allowance": allowance,
        "expenses": serialize_expenses(expenses, categories),
        "totals": totals,
        "days_logged": len(expenses),
    }
    if user_id is not None:
        limits = db.get_category_limits(user_id)
        payload["category_limits"] = limits
        payload["category_status"] = db.build_category_status(totals, limits, categories)
        payload["custom_categories"] = db.get_user_categories(user_id)
    return payload


def empty_budget_payload(user_id=None):
    categories = db.allowed_category_slugs(user_id) if user_id is not None else list(CATEGORIES)
    payload = {
        "allowance": 0,
        "expenses": {},
        "totals": {**{c: 0 for c in categories}, "spent": 0, "remaining": 0},
        "days_logged": 0,
    }
    if user_id is not None:
        payload["custom_categories"] = db.get_user_categories(user_id)
        payload["category_limits"] = db.get_category_limits(user_id)
        payload["category_status"] = db.build_category_status(
            payload["totals"], payload["category_limits"], categories,
        )
    return payload


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
        categories = db.allowed_category_slugs(user_id)
        limits = db.get_category_limits(user_id)
        payload["category_limits"] = limits
        payload["category_status"] = db.build_category_status(budget_totals, limits, categories)
        payload["category_rules"] = db.get_user_category_rules(user_id)
        payload["custom_categories"] = db.get_user_categories(user_id)
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
VERIFY_EMAIL_LIMIT = (
    "60 per hour" if os.environ.get("FLASK_ENV", "development") != "production" else "20 per hour"
)
RESEND_VERIFICATION_LIMIT = (
    "10 per hour" if os.environ.get("FLASK_ENV", "development") != "production" else "5 per hour"
)
VERIFICATION_SENT_MESSAGE = (
    "A verification link has been sent."
)


def app_base_url():
    return os.environ.get("APP_BASE_URL", "http://localhost:5173").rstrip("/")


def complete_delivery_event(event_id, success):
    try:
        db.complete_email_delivery_event(event_id, success)
    except Exception as error:
        logger.warning("Could not update email delivery event error=%s", type(error).__name__)


def record_security_event_safely(
    user_id,
    event_type,
    outcome,
    source="self_service",
    actor_user_id=None,
):
    try:
        db.record_security_event(
            user_id,
            event_type,
            outcome,
            source=source,
            actor_user_id=actor_user_id,
        )
    except Exception as error:
        logger.warning("Could not record security event error=%s", type(error).__name__)


def deliver_verification_email(
    user_id,
    email,
    source="self_service",
    actor_user_id=None,
):
    raw_token = db.create_email_verification_token(user_id)
    verification_url = f"{app_base_url()}/verify-email?token={raw_token}"
    event_id = db.create_email_delivery_event(
        user_id,
        "email_verification",
        source,
        delivery_transport_name(),
        actor_user_id=actor_user_id,
    )
    if mail_configured():
        send_email_verification_background(
            email,
            verification_url,
            on_complete=lambda success: complete_delivery_event(event_id, success),
        )
        return True
    success = send_email_verification(email, verification_url)
    complete_delivery_event(event_id, success)
    return success


def deliver_password_reset_email(
    user_id,
    email,
    source="self_service",
    actor_user_id=None,
):
    raw_token = db.create_password_reset_token(user_id)
    reset_url = f"{app_base_url()}/reset-password?token={raw_token}"
    event_id = db.create_email_delivery_event(
        user_id,
        "password_reset",
        source,
        delivery_transport_name(),
        actor_user_id=actor_user_id,
    )
    if mail_configured():
        send_password_reset_email_background(
            email,
            reset_url,
            on_complete=lambda success: complete_delivery_event(event_id, success),
        )
        return True
    success = send_password_reset_email(email, reset_url)
    complete_delivery_event(event_id, success)
    return success


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
        deliver_password_reset_email(user["id"], user["email"])

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

    if db.update_user_password(user_id, password) is None:
        return jsonify({"error": "Unable to reset password."}), 500

    record_security_event_safely(
        user_id,
        "password_reset_completed",
        "success",
    )
    return jsonify({"success": True, "message": "Password updated. You can sign in now."})


@api.route("/verify-email", methods=["POST"])
@limiter.limit(VERIFY_EMAIL_LIMIT)
@handle_api_errors
def verify_email():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Verification token is required."}), 400
    raw_token = data.get("token") or ""
    if not isinstance(raw_token, str) or not raw_token or len(raw_token) > MAX_VERIFICATION_TOKEN_LEN:
        return jsonify({"error": "Invalid or expired verification link."}), 400

    status = db.consume_email_verification_token(raw_token)
    if status != "verified":
        return jsonify({"error": "Invalid or expired verification link."}), 400
    return jsonify({"success": True, "message": "Email verified. You can sign in now."})


@api.route("/resend-verification", methods=["POST"])
@limiter.limit(RESEND_VERIFICATION_LIMIT)
@handle_api_errors
def resend_verification():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid email address."}), 400
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email or len(email) > MAX_EMAIL_LEN:
        return jsonify({"error": "Invalid email address."}), 400

    user = db.get_user_by_email(email)
    if user and not user.get("email_verified_at"):
        deliver_verification_email(user["id"], user["email"])
    return jsonify({"success": True, "message": VERIFICATION_SENT_MESSAGE})


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
        user = db.get_user_by_email(email)
        if not user:
            logger.error(
                "register: user_id=%s was returned but email %s not found in database",
                user_id,
                email,
            )
            return jsonify({"error": "Registration failed"}), 500
        session.clear()
        deliver_verification_email(user_id, user["email"])
        return jsonify({
            "success": True,
            "username": username,
            "email": user["email"],
            "verification_required": True,
            "message": "Check your email to verify your account.",
        })
    return jsonify({"error": "Registration failed"}), 500


@api.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
@handle_api_errors
def login():
    data     = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    remember = bool(data.get("remember_me") or data.get("remember"))

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) > MAX_USERNAME_LEN or len(password) > MAX_PASSWORD_LEN:
        return jsonify({"error": "Invalid credentials"}), 400
    user = db.get_user_by_username(username)
    if not user:
        record_security_event_safely(None, "login_failed", "failed")
        return jsonify({"error": "Username does not exist"}), 401
    if not db.verify_password(user, password):
        record_security_event_safely(user["id"], "login_failed", "failed")
        return jsonify({"error": "Incorrect password"}), 401
    if user.get("account_status", "active") != "active":
        record_security_event_safely(user["id"], "login_failed", "denied")
        session.clear()
        return jsonify({"error": "This account is currently unavailable."}), 403
    if not user.get("email_verified_at"):
        record_security_event_safely(user["id"], "login_failed", "denied")
        session.clear()
        return jsonify({
            "error": "Verify your email before signing in.",
            "verification_required": True,
            "email": user["email"],
        }), 403

    session.clear()
    session.permanent = remember
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["insights_served"] = False
    try:
        current_session_version = db.mark_user_login(user["id"])
        session["session_version"] = int(
            current_session_version
            if current_session_version is not None
            else user.get("session_version") or 0
        )
    except Exception as error:
        session["session_version"] = int(user.get("session_version") or 0)
        logger.warning("Could not update login timestamp user_id=%s error=%s", user["id"], type(error).__name__)
    return jsonify({
        "success": True,
        "username": user["username"],
        "remember_me": remember,
        "onboarding_completed": bool(user.get("onboarding_completed_at")),
        "is_admin": bool(
            user.get("role") == "admin"
            and current_app.config.get("ADMIN_DASHBOARD_ENABLED", True)
        ),
        "receipt_ocr_enabled": receipt_ocr_available(),
    })


@api.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@api.route("/check-auth", methods=["GET"])
def check_auth():
    if "user_id" not in session:
        return jsonify({"authenticated": False})
    user_id = session.get("user_id")
    state = db.get_user_auth_state(user_id)
    if (
        not state
        or state.get("account_status") != "active"
        or not state.get("email_verified_at")
        or int(state.get("session_version") or 0) != int(session.get("session_version") or 0)
    ):
        session.clear()
        return jsonify({"authenticated": False})
    return jsonify({
        "authenticated": True,
        "username": state.get("username") or session.get("username"),
        "remember_me": bool(session.permanent),
        "onboarding_completed": bool(state.get("onboarding_completed_at")),
        "is_admin": bool(
            state.get("role") == "admin"
            and current_app.config.get("ADMIN_DASHBOARD_ENABLED", True)
        ),
        "receipt_ocr_enabled": receipt_ocr_available(),
    })


@api.route("/admin/overview", methods=["GET"])
@admin_required
@handle_api_errors
def admin_overview():
    return jsonify({"metrics": db.get_admin_overview()})


@api.route("/admin/users", methods=["GET"])
@admin_required
@handle_api_errors
def admin_users():
    query = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip().lower()
    role = (request.args.get("role") or "").strip().lower()
    sort = (request.args.get("sort") or "created_at").strip().lower()
    direction = (request.args.get("direction") or "desc").strip().lower()
    page = positive_int(request.args.get("page", 1), 1)
    page_size = positive_int(
        request.args.get("page_size", ADMIN_PAGE_SIZE),
        ADMIN_PAGE_SIZE,
        ADMIN_MAX_PAGE_SIZE,
    )

    if page is None or page_size is None:
        return jsonify({"error": "Invalid pagination values."}), 400
    if len(query) > MAX_ADMIN_SEARCH_LEN:
        return jsonify({"error": "Search must be at most 100 characters."}), 400
    if status not in ("", "active", "suspended"):
        return jsonify({"error": "Invalid account status filter."}), 400
    if role not in ("", "user", "admin"):
        return jsonify({"error": "Invalid role filter."}), 400
    if sort not in db.ADMIN_USER_SORTS:
        return jsonify({"error": "Invalid sort field."}), 400
    if direction not in ("asc", "desc"):
        return jsonify({"error": "Invalid sort direction."}), 400

    users, total = db.list_admin_users(
        query=query,
        status=status,
        role=role,
        page=page,
        page_size=page_size,
        sort=sort,
        direction=direction,
    )
    pages = max(1, (total + page_size - 1) // page_size)
    return jsonify({
        "users": [serialize_admin_user(user) for user in users],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": pages,
        },
    })


@api.route("/admin/audit-events", methods=["GET"])
@admin_required
@handle_api_errors
def admin_audit_events():
    query = (request.args.get("q") or "").strip()
    action = (request.args.get("action") or "").strip().lower()
    outcome = (request.args.get("outcome") or "").strip().lower()
    source = (request.args.get("source") or "").strip().lower()
    date_from = parse_admin_date((request.args.get("date_from") or "").strip())
    date_to = parse_admin_date((request.args.get("date_to") or "").strip(), end=True)
    page = positive_int(request.args.get("page", 1), 1)
    page_size = positive_int(
        request.args.get("page_size", ADMIN_PAGE_SIZE),
        ADMIN_PAGE_SIZE,
        ADMIN_MAX_PAGE_SIZE,
    )
    if page is None or page_size is None:
        return jsonify({"error": "Invalid pagination values."}), 400
    if len(query) > MAX_ADMIN_SEARCH_LEN:
        return jsonify({"error": "Search must be at most 100 characters."}), 400
    if action and action not in db.ADMIN_AUDIT_ACTIONS:
        return jsonify({"error": "Invalid audit action filter."}), 400
    if outcome not in ("", "success", "denied"):
        return jsonify({"error": "Invalid audit outcome filter."}), 400
    if source not in ("", "web", "operator_cli"):
        return jsonify({"error": "Invalid audit source filter."}), 400
    if date_from is False or date_to is False:
        return jsonify({"error": "Dates must use YYYY-MM-DD format."}), 400
    events, total = db.list_admin_audit_events(
        query=query,
        action=action,
        outcome=outcome,
        source=source,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return jsonify({
        "events": [{
            "id": event["id"],
            "action": event["action"],
            "outcome": event["outcome"],
            "reason": event.get("reason") or "",
            "source": event["source"],
            "request_id": event.get("request_id"),
            "created_at": iso_datetime(event.get("created_at")),
            "actor_username": event.get("actor_username"),
            "target_username": event.get("target_username"),
        } for event in events],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
        },
    })


@api.route("/admin/users/<int:user_id>", methods=["GET"])
@admin_required
@handle_api_errors
def admin_user_detail(user_id):
    user = db.get_admin_user_detail(user_id)
    if not user:
        return jsonify({"error": "Account not found."}), 404
    history = db.list_user_security_history(user_id, limit=40)
    return jsonify({
        "user": serialize_admin_user(user),
        "security_events": [{
            "id": event["id"],
            "category": event["category"],
            "event_type": event["event_type"],
            "outcome": event["outcome"],
            "source": event["source"],
            "detail": event.get("detail") or "",
            "created_at": iso_datetime(event.get("created_at")),
            "actor_username": event.get("actor_username"),
        } for event in history],
    })


@api.route("/admin/system-health", methods=["GET"])
@admin_required
@handle_api_errors
def admin_system_health():
    raw_health = db.get_admin_system_health()
    health = {
        "authentication": raw_health.get("authentication", {}),
        "email": raw_health.get("email", {}),
    }
    health["email"].update({
        "configured": mail_configured(),
        "transport": delivery_transport_name(),
        "last_delivery_at": iso_datetime(health["email"].get("last_delivery_at")),
    })
    health["checked_at"] = datetime.now(timezone.utc).isoformat()
    return jsonify({"health": health})


def admin_email_support_action(user_id, action):
    payload, error_response = parse_admin_action_request()
    if error_response:
        return error_response
    authorization = db.authorize_admin_user_action(
        get_user_id(),
        user_id,
        payload["current_password"],
    )
    if authorization.get("status") != "authorized":
        return denied_admin_action(
            authorization.get("status"),
            user_id,
            action,
            payload["reason"],
            payload["request_id"],
        )
    target = authorization["user"]
    if target.get("account_status") != "active":
        return denied_admin_action(
            "inactive_target",
            user_id,
            action,
            payload["reason"],
            payload["request_id"],
        )
    if action == "resend_verification" and target.get("email_verified_at"):
        try:
            db.record_admin_audit_event(
                get_user_id(),
                user_id,
                action,
                "denied",
                reason=payload["reason"],
                request_id=payload["request_id"],
            )
        except Exception as error:
            logger.warning("Could not record denied admin action error=%s", type(error).__name__)
        return jsonify({"error": "This account is already verified."}), 400

    email_type = "email_verification" if action == "resend_verification" else "password_reset"
    if db.email_delivery_on_cooldown(user_id, email_type):
        db.record_admin_audit_event(
            get_user_id(),
            user_id,
            action,
            "denied",
            reason=payload["reason"],
            request_id=payload["request_id"],
        )
        return jsonify({"error": "Wait at least 5 minutes before sending another email of this type."}), 429

    if action == "resend_verification":
        delivered = deliver_verification_email(
            user_id,
            target["email"],
            source="admin",
            actor_user_id=get_user_id(),
        )
        message = "Verification email queued."
    else:
        delivered = deliver_password_reset_email(
            user_id,
            target["email"],
            source="admin",
            actor_user_id=get_user_id(),
        )
        message = "Password-reset email queued."

    db.record_admin_audit_event(
        get_user_id(),
        user_id,
        action,
        "success" if delivered else "denied",
        reason=payload["reason"],
        request_id=payload["request_id"],
    )
    if not delivered:
        return jsonify({"error": "Email delivery is not configured or could not be started."}), 503
    return jsonify({
        "success": True,
        "message": message,
        "delivery_status": "queued" if mail_configured() else "sent",
    })


@api.route("/admin/users/<int:user_id>/resend-verification", methods=["POST"])
@admin_required
@limiter.limit(ADMIN_EMAIL_LIMIT, key_func=admin_rate_limit_key)
@handle_api_errors
def admin_resend_verification(user_id):
    return admin_email_support_action(user_id, "resend_verification")


@api.route("/admin/users/<int:user_id>/send-password-reset", methods=["POST"])
@admin_required
@limiter.limit(ADMIN_EMAIL_LIMIT, key_func=admin_rate_limit_key)
@handle_api_errors
def admin_send_password_reset(user_id):
    return admin_email_support_action(user_id, "send_password_reset")


@api.route("/admin/users/<int:user_id>/revoke-sessions", methods=["POST"])
@admin_required
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=admin_rate_limit_key)
@handle_api_errors
def admin_revoke_sessions(user_id):
    payload, error_response = parse_admin_action_request()
    if error_response:
        return error_response
    result = db.revoke_user_sessions(
        get_user_id(),
        user_id,
        payload["current_password"],
        payload["reason"],
        request_id=payload["request_id"],
    )
    if result.get("status") != "updated":
        return denied_admin_action(
            result.get("status"),
            user_id,
            "revoke_sessions",
            payload["reason"],
            payload["request_id"],
        )
    return jsonify({
        "success": True,
        "message": "All active sessions were revoked.",
        "user": serialize_admin_user(result["user"]),
    })


def admin_status_mutation(user_id, new_status):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Current password and reason are required."}), 400
    current_password = data.get("current_password") or ""
    raw_reason = data.get("reason") or ""
    if not isinstance(current_password, str) or not isinstance(raw_reason, str):
        return jsonify({"error": "Current password and reason are required."}), 400
    reason = " ".join(raw_reason.split())
    if not current_password or len(reason) < 5:
        return jsonify({"error": "Enter your current password and a reason of at least 5 characters."}), 400
    if len(current_password) > MAX_PASSWORD_LEN or len(reason) > MAX_ADMIN_REASON_LEN:
        return jsonify({"error": "Invalid account-management details."}), 400

    raw_request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
    request_id = "".join(
        char for char in raw_request_id if char.isalnum() or char in "-_."
    )[:64] or secrets.token_hex(8)
    result = db.change_user_account_status(
        get_user_id(),
        user_id,
        current_password,
        new_status,
        reason,
        request_id=request_id,
    )
    status = result.get("status")
    if status == "updated":
        return jsonify({
            "success": True,
            "user": serialize_admin_user(result["user"]),
        })
    if status == "unchanged":
        return jsonify({
            "success": True,
            "unchanged": True,
            "user": serialize_admin_user(result["user"]),
        })

    action = "suspend_user" if new_status == "suspended" else "reactivate_user"
    audit_target = None if status in ("invalid_password", "not_found", "forbidden") else user_id
    try:
        db.record_admin_audit_event(
            get_user_id(),
            audit_target,
            action,
            "denied",
            reason=reason,
            request_id=request_id,
        )
    except Exception as error:
        logger.warning("Could not record denied admin action error=%s", type(error).__name__)

    errors = {
        "invalid_password": ("Current password is incorrect.", 401),
        "self_target": ("You cannot change your own account status.", 400),
        "admin_target": ("Administrator accounts cannot be changed here.", 400),
        "not_found": ("Account not found.", 404),
        "forbidden": ("Administrator access required.", 403),
    }
    message, code = errors.get(status, ("Account status could not be changed.", 400))
    return jsonify({"error": message}), code


@api.route("/admin/users/<int:user_id>/suspend", methods=["POST"])
@admin_required
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=admin_rate_limit_key)
@handle_api_errors
def admin_suspend_user(user_id):
    return admin_status_mutation(user_id, "suspended")


@api.route("/admin/users/<int:user_id>/reactivate", methods=["POST"])
@admin_required
@limiter.limit(ADMIN_MUTATION_LIMIT, key_func=admin_rate_limit_key)
@handle_api_errors
def admin_reactivate_user(user_id):
    return admin_status_mutation(user_id, "active")


@api.route("/onboarding/complete", methods=["POST"])
@login_required
@handle_api_errors
def complete_onboarding_route():
    user_id = get_user_id()
    data = request.get_json(silent=True) or {}
    allowance_raw = data.get("allowance")
    if allowance_raw is not None and allowance_raw != "":
        allowance = float(allowance_raw)
        if allowance <= 0:
            return jsonify({"error": "Allowance must be greater than 0"}), 400
        week_start, week_end = get_week_range()
        existing = db.get_budget_by_week(user_id, week_start, week_end)
        if existing:
            if not db.update_budget(existing["id"], user_id, allowance):
                return jsonify({"error": "Budget not found."}), 404
        else:
            db.create_budget(user_id, week_start, week_end, allowance)

    completed_at = db.complete_onboarding(user_id)
    return jsonify({
        "success": True,
        "onboarding_completed": True,
        "onboarding_completed_at": str(completed_at) if completed_at else None,
    })


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

    email_changed = db.normalize_email(email) != db.normalize_email(user["email"])

    if username == user["username"] and db.normalize_email(email) == db.normalize_email(user["email"]):
        return jsonify({"success": True, "username": username, "email": email})

    if not db.update_user_profile(
        user_id,
        username=username,
        email=email,
        reset_email_verification=email_changed,
    ):
        return jsonify({"error": "Username or email is already in use."}), 400

    if email_changed:
        session.clear()
        deliver_verification_email(user_id, email)
        return jsonify({
            "success": True,
            "username": username,
            "email": email,
            "verification_required": True,
            "message": "Verify your new email before signing in again.",
        })

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

    current_session_version = db.update_user_password(user_id, new_password)
    if current_session_version is None:
        return jsonify({"error": "Unable to update password."}), 500

    session["session_version"] = current_session_version
    db.invalidate_password_reset_tokens(user_id)
    record_security_event_safely(user_id, "password_changed", "success")
    return jsonify({"success": True, "message": "Password updated."})


@api.route("/account", methods=["DELETE"])
@login_required
@limiter.limit(ACCOUNT_DELETION_LIMIT)
@handle_api_errors
def delete_account():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Current password and confirmation are required."}), 400

    current_password = data.get("current_password") or ""
    confirmation = data.get("confirmation") or ""
    if not isinstance(current_password, str) or not isinstance(confirmation, str):
        return jsonify({"error": "Current password and confirmation are required."}), 400
    if not current_password or not confirmation:
        return jsonify({"error": "Current password and confirmation are required."}), 400
    if len(current_password) > MAX_PASSWORD_LEN or len(confirmation) > MAX_USERNAME_LEN + 7:
        return jsonify({"error": "Invalid account deletion details."}), 400

    expected_confirmation = f"DELETE {session.get('username', '')}"
    if confirmation.strip() != expected_confirmation:
        return jsonify({"error": "Confirmation text does not match."}), 400

    status = db.delete_user_account(get_user_id(), current_password)
    if status == "invalid_password":
        return jsonify({"error": "Current password is incorrect."}), 401
    if status != "deleted":
        session.clear()
        return jsonify({"error": "Authentication required"}), 401

    session.clear()
    return jsonify({"success": True, "message": "Account deleted."})


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
            if budget else empty_budget_payload(user_id)
        )
        return jsonify({
            "username": session.get("username"),
            "week_info": week_info_payload(),
            "budget": budget_data,
            "comparison": comparison,
            "category_rules": db.get_user_category_rules(user_id),
            "custom_categories": db.get_user_categories(user_id),
        })


@api.route("/insights", methods=["GET"])
@login_required
@handle_api_errors
def insights():
    if session.get("insights_served"):
        return jsonify({
            "insights": [],
            "source": "rules",
            "period": "week",
            "served": True,
        })

    user_id = get_user_id()
    week_start, week_end = get_week_range()
    budget, rows, items_by_expense, comparison = db.fetch_dashboard(
        user_id, week_start, week_end,
    )
    labels = db.category_labels_for_user(user_id)
    week = week_info_payload()
    days_remaining = week.get("days_remaining")

    if not budget:
        empty_totals = {
            **{c: 0 for c in db.allowed_category_slugs(user_id)},
            "spent": 0,
            "remaining": 0,
        }
        result = build_insights(
            0,
            empty_totals,
            period="week",
            labels=labels,
            username=session.get("username"),
            comparison=comparison,
            days_remaining=days_remaining,
            prefer_speed=True,
        )
    else:
        budget_data = json_budget_payload(budget, rows, items_by_expense, user_id=user_id)
        totals = budget_data["totals"]
        category_status = budget_data.get("category_status")
        result = build_insights(
            budget_data["allowance"],
            totals,
            period="week",
            labels=labels,
            username=session.get("username"),
            category_status=category_status,
            comparison=comparison,
            days_remaining=days_remaining,
            prefer_speed=True,
        )

    session["insights_served"] = True
    return jsonify({**result, "period": "week", "served": False})


@api.route("/spending-anomalies", methods=["GET"])
@login_required
@handle_api_errors
def spending_anomalies():
    started_at = time.perf_counter()
    user_id = get_user_id()
    week_start, week_end = get_week_range()
    history_start = week_start - timedelta(days=HISTORY_WINDOW_DAYS)
    rows = db.get_spending_anomaly_candidates(
        user_id,
        week_start,
        week_end,
        history_start,
    )
    report = build_anomaly_report(rows)
    logger.info(
        "Spending anomaly check completed history_samples=%s anomalies=%s elapsed_ms=%.1f",
        report["sample_size"],
        len(report["anomalies"]),
        (time.perf_counter() - started_at) * 1000,
    )
    return jsonify({**report, "window_days": HISTORY_WINDOW_DAYS})


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
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid item."}), 400
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Item name is required"}), 400
    if len(name) > MAX_ITEM_NAME_LEN:
        return jsonify({"error": f"Item name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
    user_id = get_user_id()
    user_rules = db.get_user_category_rules(user_id)
    context = build_category_context(db.get_user_categories(user_id))
    result = classify_category(
        name,
        user_rules=user_rules,
        category_context=context,
    )
    category = result["category"]
    labels = db.category_labels_for_user(user_id)
    return jsonify({
        "category": category,
        "label": labels.get(category, category),
        "confidence": result["confidence"],
        "needs_review": result["needs_review"],
        "source": result["source"],
    })


@api.route("/receipt-scans/extract", methods=["POST"])
@login_required
@limiter.limit(RECEIPT_SCAN_LIMIT)
@handle_api_errors
def extract_receipt_route():
    if not current_app.config.get("RECEIPT_OCR_ENABLED", False):
        return jsonify({"error": "Receipt scanning is not available."}), 503
    receipt_file = request.files.get("receipt")
    if receipt_file is None:
        return jsonify({"error": "Choose a receipt image to scan."}), 400

    user_id = get_user_id()
    categories = db.get_user_categories(user_id)
    context = build_category_context(categories)
    started_at = time.perf_counter()
    request_id = secrets.token_hex(8)
    try:
        receipt = extract_receipt(
            receipt_file,
            context,
            user_rules=db.get_user_category_rules(user_id),
        )
    except ReceiptUploadError as error:
        return jsonify({"error": str(error)}), 400
    except ReceiptSchemaError:
        return jsonify({
            "error": "The receipt could not be read reliably. Try a clearer photo.",
        }), 422
    except ReceiptProviderUnavailable:
        return jsonify({"error": "Receipt scanning is temporarily unavailable."}), 503
    except ReceiptBusyError:
        return jsonify({
            "error": "Receipt scanning is busy. Please try again in a moment.",
        }), 503
    except ReceiptProviderError as error:
        cause = error.__cause__ or error
        logger.warning(
            "Receipt extraction failed request_id=%s user_id=%s outcome=provider_error "
            "status=%s error_type=%s",
            request_id,
            user_id,
            getattr(cause, "status_code", getattr(cause, "code", "unknown")),
            type(cause).__name__,
        )
        return jsonify({"error": "Receipt scanning failed. Please try again."}), 502

    image_meta = receipt["image"]
    logger.info(
        "Receipt extraction completed request_id=%s user_id=%s input_bytes=%s "
        "width=%s height=%s elapsed_ms=%.1f item_count=%s reconciled=%s",
        request_id,
        user_id,
        image_meta["input_bytes"],
        image_meta["width"],
        image_meta["height"],
        (time.perf_counter() - started_at) * 1000,
        len(receipt["items"]),
        receipt["reconciled"],
    )
    response = jsonify({
        "receipt": {
            key: value
            for key, value in receipt.items()
            if key not in ("items", "warnings", "image")
        },
        "items": receipt["items"],
        "warnings": receipt["warnings"],
        "mode": receipt["mode"],
        "categories": [
            {"slug": row["slug"], "label": row["label"]}
            for row in context
        ],
    })
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@api.route("/expense-items/batch", methods=["POST"])
@login_required
@limiter.limit(RECEIPT_BATCH_LIMIT)
@handle_api_errors
def add_expense_items_batch_route():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid receipt items."}), 400
    idempotency_key = (request.headers.get("Idempotency-Key") or "").strip()
    try:
        parsed_key = str(uuid.UUID(idempotency_key))
    except (ValueError, AttributeError):
        return jsonify({"error": "A valid idempotency key is required."}), 400

    day = data.get("day")
    raw_items = data.get("items")
    if day not in DAYS_MAP:
        return jsonify({"error": "Choose a valid day."}), 400
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({"error": "Add at least one receipt item."}), 400
    if len(raw_items) > MAX_RECEIPT_ITEMS:
        return jsonify({"error": f"At most {MAX_RECEIPT_ITEMS} receipt items are allowed."}), 400

    user_id = get_user_id()
    allowed = set(db.allowed_category_slugs(user_id))
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            return jsonify({"error": "Invalid receipt item."}), 400
        name = (raw.get("name") or "").strip()
        if not name or len(name) > MAX_ITEM_NAME_LEN:
            return jsonify({
                "error": f"Each item name must be between 1 and {MAX_ITEM_NAME_LEN} characters.",
            }), 400
        try:
            amount = money_value(raw.get("amount"), required=True)
        except ReceiptSchemaError:
            return jsonify({"error": "Each receipt amount must be valid."}), 400
        if amount <= 0:
            return jsonify({"error": "Each receipt amount must be greater than 0."}), 400
        category = (raw.get("category") or "").strip().lower()
        if category not in allowed:
            return jsonify({
                "error": "A selected category is no longer available. Review the receipt again.",
            }), 409
        notes, tags, meta_error = parse_item_notes_tags(raw)
        if meta_error:
            return jsonify({"error": meta_error}), 400
        items.append({
            "name": name,
            "amount": amount,
            "category": category,
            "notes": notes,
            "tags": tags,
        })

    week_start, week_end = get_week_range()
    budget = db.get_budget_by_week(user_id, week_start, week_end)
    if not budget:
        return jsonify({"error": "Please set allowance first."}), 404
    expense_date = week_start + timedelta(days=DAYS_MAP[day])
    result = db.add_expense_items_batch(
        user_id,
        budget["id"],
        day,
        expense_date,
        items,
        parsed_key,
    )
    if result is None:
        return jsonify({"error": "Budget not found."}), 404

    if not result["duplicate"]:
        for item in items:
            try:
                db.learn_category_correction(
                    user_id,
                    item["name"],
                    item["category"],
                )
            except Exception as error:
                logger.warning(
                    "Receipt category learning failed error=%s",
                    type(error).__name__,
                )

    payload = mutation_payload(
        result["day"],
        result["expense"],
        result["totals"],
        user_id,
    )
    return jsonify({
        **payload,
        "items": result["items"],
        "duplicate": result["duplicate"],
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
    notes, tags, meta_error = parse_item_notes_tags(data or {})
    if meta_error:
        return jsonify({"error": meta_error}), 400

    if not day:
        return jsonify({"error": "Day is required"}), 400
    if not name:
        return jsonify({"error": "Item name is required"}), 400
    if len(name) > MAX_ITEM_NAME_LEN:
        return jsonify({"error": f"Item name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400

    category = resolve_category(user_id, category, name)

    expense_date = week_start + timedelta(days=DAYS_MAP.get(day, 0))
    budget = db.get_budget_by_week(user_id, week_start, week_end)
    if not budget:
        return jsonify({"error": "Please set allowance first."}), 404

    item, day, day_expense, budget_totals = db.add_expense_item(
        budget["id"], day, expense_date, name, amount, category, notes=notes, tags=tags,
    )
    db.learn_category_correction(user_id, name, category)
    return jsonify({
        **mutation_payload(day, day_expense, budget_totals, user_id),
        "item": db.expense_item_dict(item),
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
    notes, tags, meta_error = parse_item_notes_tags(data or {})
    if meta_error:
        return jsonify({"error": meta_error}), 400

    if not name:
        return jsonify({"error": "Item name is required"}), 400
    if len(name) > MAX_ITEM_NAME_LEN:
        return jsonify({"error": f"Item name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400
    category = resolve_category(user_id, category, name)

    item, day, day_expense, budget_totals = db.update_expense_item(
        item_id, user_id, name, amount, category, notes=notes, tags=tags,
    )
    if not item:
        return jsonify({"error": "Item not found"}), 404

    db.learn_category_correction(user_id, name, category)

    week_start, week_end = get_week_range()
    return jsonify({
        **mutation_payload(day, day_expense, budget_totals, user_id),
        "item": db.expense_item_dict(item),
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
        return jsonify(empty_budget_payload(user_id))

    return jsonify(json_budget_payload(budget, rows, items_by_expense, user_id=user_id))


@api.route("/budget-settings", methods=["GET"])
@login_required
@handle_api_errors
def get_budget_settings():
    user_id = get_user_id()
    income_sources = db.get_user_income_sources(user_id)
    return jsonify({
        "category_limits": db.get_category_limits(user_id),
        "recurring_expenses": db.get_recurring_expenses(user_id),
        "category_rules": db.get_user_category_rules(user_id),
        "custom_categories": db.get_user_categories(user_id),
        "income_sources": income_sources,
        "income_total": db.income_sources_total(sources=income_sources, active_only=True),
    })


@api.route("/income-sources", methods=["GET"])
@login_required
@handle_api_errors
def list_income_sources():
    user_id = get_user_id()
    sources = db.get_user_income_sources(user_id)
    return jsonify({
        "income_sources": sources,
        "income_total": db.income_sources_total(sources=sources, active_only=True),
    })


@api.route("/income-sources", methods=["POST"])
@login_required
@handle_api_errors
def create_income_source():
    data = request.get_json() or {}
    user_id = get_user_id()
    try:
        source = db.create_user_income_source(
            user_id,
            label=data.get("label") or data.get("name"),
            amount=data.get("amount"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    sources = db.get_user_income_sources(user_id)
    apply_week = bool(data.get("apply_to_week"))
    allowance = None
    if apply_week:
        total = db.income_sources_total(sources=sources, active_only=True)
        if total > 0:
            week_start, week_end = get_week_range()
            existing = db.get_budget_by_week(user_id, week_start, week_end)
            if existing:
                db.update_budget(existing["id"], user_id, total)
            else:
                db.create_budget(user_id, week_start, week_end, total)
            allowance = total

    return jsonify({
        "success": True,
        "income_source": source,
        "income_sources": sources,
        "income_total": db.income_sources_total(sources=sources, active_only=True),
        "allowance": allowance,
    }), 201


@api.route("/income-sources/<int:source_id>", methods=["PUT"])
@login_required
@handle_api_errors
def update_income_source(source_id):
    data = request.get_json() or {}
    user_id = get_user_id()
    fields = {}
    if "label" in data or "name" in data:
        fields["label"] = data.get("label") or data.get("name")
    if "amount" in data:
        fields["amount"] = data.get("amount")
    if "active" in data:
        fields["active"] = data.get("active")
    if "sort_order" in data:
        fields["sort_order"] = data.get("sort_order")
    try:
        source = db.update_user_income_source(source_id, user_id, **fields)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not source:
        return jsonify({"error": "Income source not found."}), 404

    sources = db.get_user_income_sources(user_id)
    return jsonify({
        "success": True,
        "income_source": source,
        "income_sources": sources,
        "income_total": db.income_sources_total(sources=sources, active_only=True),
    })


@api.route("/income-sources/<int:source_id>", methods=["DELETE"])
@login_required
@handle_api_errors
def delete_income_source(source_id):
    user_id = get_user_id()
    if not db.delete_user_income_source(source_id, user_id):
        return jsonify({"error": "Income source not found."}), 404
    sources = db.get_user_income_sources(user_id)
    return jsonify({
        "success": True,
        "income_sources": sources,
        "income_total": db.income_sources_total(sources=sources, active_only=True),
    })


@api.route("/income-sources/apply", methods=["POST"])
@login_required
@handle_api_errors
def apply_income_sources():
    user_id = get_user_id()
    sources = db.get_user_income_sources(user_id)
    total = db.income_sources_total(sources=sources, active_only=True)
    if total <= 0:
        return jsonify({"error": "Add at least one active income source first."}), 400

    week_start, week_end = get_week_range()
    existing = db.get_budget_by_week(user_id, week_start, week_end)
    if existing:
        db.update_budget(existing["id"], user_id, total)
        budget_id = existing["id"]
    else:
        budget_id = db.create_budget(user_id, week_start, week_end, total)

    with db.db_cursor(dict_cursor=True) as cursor:
        totals = db.compute_budget_totals(cursor, budget_id)
    return jsonify({
        "success": True,
        "allowance": total,
        "budget_id": budget_id,
        "totals": totals,
        "income_sources": sources,
        "income_total": total,
    })


@api.route("/category-limits", methods=["PUT"])
@login_required
@handle_api_errors
def update_category_limits():
    data = request.get_json() or {}
    limits_in = data.get("limits") or {}
    if not isinstance(limits_in, dict):
        return jsonify({"error": "limits must be an object."}), 400

    user_id = get_user_id()
    allowed = set(db.allowed_category_slugs(user_id))
    parsed = {}
    for category, value in limits_in.items():
        if category not in allowed:
            continue
        if value is None or value == "":
            parsed[category] = None
        else:
            amount = float(value)
            if amount <= 0:
                parsed[category] = None
            else:
                parsed[category] = amount

    db.set_category_limits(user_id, parsed)
    limits = db.get_category_limits(user_id)
    categories = db.allowed_category_slugs(user_id)
    week_start, week_end = get_week_range()
    budget = db.get_budget_by_week(user_id, week_start, week_end)
    totals = {**{c: 0 for c in categories}, "spent": 0, "remaining": 0}
    if budget:
        with db.db_cursor(dict_cursor=True) as cursor:
            totals = db.compute_budget_totals(cursor, budget["id"])
    return jsonify({
        "success": True,
        "category_limits": limits,
        "category_status": db.build_category_status(totals, limits, categories),
    })


@api.route("/user-categories", methods=["GET"])
@login_required
@handle_api_errors
def list_user_categories():
    user_id = get_user_id()
    return jsonify({
        "custom_categories": db.get_user_categories(user_id),
        "categories": db.allowed_category_slugs(user_id),
        "labels": db.category_labels_for_user(user_id),
    })


@api.route("/user-categories", methods=["POST"])
@login_required
@handle_api_errors
def create_user_category_route():
    data = request.get_json() or {}
    user_id = get_user_id()
    try:
        category = db.create_user_category(
            user_id,
            label=data.get("label") or data.get("name"),
            color=data.get("color"),
            description=data.get("description", ""),
            keywords=data.get("keywords"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "success": True,
        "category": category,
        "custom_categories": db.get_user_categories(user_id),
        "categories": db.allowed_category_slugs(user_id),
        "labels": db.category_labels_for_user(user_id),
    }), 201


@api.route("/user-categories/<int:category_id>", methods=["PUT"])
@login_required
@handle_api_errors
def update_user_category_route(category_id):
    data = request.get_json() or {}
    user_id = get_user_id()
    fields = {}
    if "label" in data or "name" in data:
        fields["label"] = data.get("label") if "label" in data else data.get("name")
    if "color" in data:
        fields["color"] = data.get("color")
    if "description" in data:
        fields["description"] = data.get("description")
    if "keywords" in data:
        fields["keywords"] = data.get("keywords")
    try:
        category = db.update_user_category(category_id, user_id, **fields)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not category:
        return jsonify({"error": "Category not found."}), 404
    return jsonify({
        "success": True,
        "category": category,
        "custom_categories": db.get_user_categories(user_id),
        "categories": db.allowed_category_slugs(user_id),
        "labels": db.category_labels_for_user(user_id),
    })


@api.route("/user-categories/<int:category_id>", methods=["DELETE"])
@login_required
@handle_api_errors
def delete_user_category_route(category_id):
    user_id = get_user_id()
    if not db.delete_user_category(category_id, user_id):
        return jsonify({"error": "Category not found."}), 404
    return jsonify({
        "success": True,
        "custom_categories": db.get_user_categories(user_id),
        "categories": db.allowed_category_slugs(user_id),
        "labels": db.category_labels_for_user(user_id),
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
    category = resolve_category(user_id, category, name)

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
        allowed = db.allowed_category_slugs(user_id)
        if category not in allowed:
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


def period_date_range(period, month=None, year=None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    if period == "week":
        week_start, week_end = get_week_range()
        label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
        return week_start, week_end + timedelta(days=1), label

    if period == "month":
        start = datetime(year, month, 1).date()
        end = (
            datetime(year + 1, 1, 1).date() if month == 12
            else datetime(year, month + 1, 1).date()
        )
        label = datetime(year, month, 1).strftime("%B %Y")
        return start, end, label

    if period == "year":
        start = datetime(year, 1, 1).date()
        end = datetime(year + 1, 1, 1).date()
        label = str(year)
        return start, end, label

    if period == "all":
        return datetime(2000, 1, 1).date(), datetime(2100, 1, 1).date(), "All time"

    return None, None, None


@api.route("/savings-snapshot", methods=["GET"])
@login_required
@handle_api_errors
def savings_snapshot():
    user_id = get_user_id()
    period = (request.args.get("period") or "year").lower()
    if period not in ("week", "month", "year", "all"):
        return jsonify({"error": "period must be week, month, year, or all"}), 400

    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    if month is not None and (month < 1 or month > 12):
        return jsonify({"error": "month must be between 1 and 12"}), 400
    if year is not None and (year < 2000 or year > 2100):
        return jsonify({"error": "year is out of range"}), 400

    start_date, end_date, label = period_date_range(period, month=month, year=year)
    ledger, weeks = db.get_savings_ledger(user_id, start_date, end_date)
    return jsonify({
        "period": period,
        "label": label,
        "start_date": str(start_date),
        "end_date": str(end_date - timedelta(days=1)),
        **ledger,
    })


def parse_goal_deadline(value):
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return False
    return value


@api.route("/savings-goals", methods=["GET"])
@login_required
@handle_api_errors
def list_savings_goals():
    include_archived = request.args.get("include_archived", "false").lower() == "true"
    return jsonify({
        "goals": db.get_savings_goals(get_user_id(), include_archived=include_archived),
    })


@api.route("/savings-goals", methods=["POST"])
@login_required
@handle_api_errors
def create_savings_goal_route():
    data = request.get_json() or {}
    user_id = get_user_id()
    name = (data.get("name") or "").strip()
    try:
        target = float(data.get("target_amount", 0))
        current = float(data.get("current_amount", 0) or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Amounts must be valid numbers."}), 400

    if not name:
        return jsonify({"error": "Name is required."}), 400
    if len(name) > MAX_ITEM_NAME_LEN:
        return jsonify({"error": f"Name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
    if target <= 0:
        return jsonify({"error": "Target amount must be greater than 0."}), 400
    if current < 0:
        return jsonify({"error": "Current amount cannot be negative."}), 400

    deadline = parse_goal_deadline(data.get("deadline"))
    if deadline is False:
        return jsonify({"error": "Deadline must be YYYY-MM-DD."}), 400

    goal_id = db.create_savings_goal(user_id, name, target, current, deadline)
    return jsonify({
        "success": True,
        "id": goal_id,
        "goals": db.get_savings_goals(user_id),
    }), 201


@api.route("/savings-goals/<int:goal_id>", methods=["PUT"])
@login_required
@handle_api_errors
def update_savings_goal_route(goal_id):
    data = request.get_json() or {}
    user_id = get_user_id()
    if not db.get_savings_goal(goal_id, user_id):
        return jsonify({"error": "Savings goal not found."}), 404

    fields = {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name is required."}), 400
        if len(name) > MAX_ITEM_NAME_LEN:
            return jsonify({"error": f"Name must be at most {MAX_ITEM_NAME_LEN} characters."}), 400
        fields["name"] = name
    if "target_amount" in data:
        try:
            target = float(data.get("target_amount", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "Target amount must be a valid number."}), 400
        if target <= 0:
            return jsonify({"error": "Target amount must be greater than 0."}), 400
        fields["target_amount"] = target
    if "current_amount" in data:
        try:
            current = float(data.get("current_amount", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "Current amount must be a valid number."}), 400
        if current < 0:
            return jsonify({"error": "Current amount cannot be negative."}), 400
        fields["current_amount"] = current
    if "deadline" in data:
        deadline = parse_goal_deadline(data.get("deadline"))
        if deadline is False:
            return jsonify({"error": "Deadline must be YYYY-MM-DD."}), 400
        fields["deadline"] = deadline
    if "status" in data:
        status = (data.get("status") or "").strip().lower()
        if status not in ("active", "completed", "archived"):
            return jsonify({"error": "Status must be active, completed, or archived."}), 400
        fields["status"] = status

    goal = db.update_savings_goal(goal_id, user_id, **fields)
    if not goal:
        return jsonify({"error": "Savings goal not found."}), 404
    return jsonify({"success": True, "goal": goal, "goals": db.get_savings_goals(user_id)})


@api.route("/savings-goals/<int:goal_id>/contribute", methods=["POST"])
@login_required
@handle_api_errors
def contribute_savings_goal_route(goal_id):
    data = request.get_json() or {}
    user_id = get_user_id()
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Amount must be a valid number."}), 400
    if amount <= 0:
        return jsonify({"error": "Contribution must be greater than 0."}), 400

    goal = db.contribute_to_savings_goal(goal_id, user_id, amount)
    if not goal:
        return jsonify({"error": "Savings goal not found."}), 404
    return jsonify({"success": True, "goal": goal, "goals": db.get_savings_goals(user_id)})


@api.route("/savings-goals/<int:goal_id>", methods=["DELETE"])
@login_required
@handle_api_errors
def delete_savings_goal_route(goal_id):
    user_id = get_user_id()
    if not db.delete_savings_goal(goal_id, user_id):
        return jsonify({"error": "Savings goal not found."}), 404
    return jsonify({"success": True, "goals": db.get_savings_goals(user_id)})


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
    snapshot = db.build_savings_snapshot(weeks, finalized_only=False)

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
        "total_allowance": snapshot["total_allowance"],
        "total_spent": snapshot["total_spent"],
        "total_saved": snapshot["total_allowance"] - snapshot["total_spent"],
        "total_undersaved": snapshot["total_saved"],
        "total_overspent": snapshot["total_overspent"],
        "breakdown": {
            c: breakdown.get(c, 0)
            for c in db.allowed_category_slugs(user_id)
        },
        "custom_categories": db.get_user_categories(user_id),
        "weeks": weekly_data,
        "num_weeks": len(weekly_data),
    })


@api.route("/account-export", methods=["GET"])
@login_required
@limiter.limit(ACCOUNT_EXPORT_LIMIT)
@handle_api_errors
def account_export():
    started_at = time.perf_counter()
    snapshot = db.get_account_export_snapshot(get_user_id())
    archive, manifest = build_account_export(snapshot)
    filename = f"budget-tracker-account-export-{datetime.now().date()}.zip"
    response = send_file(
        archive,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store"
    response.call_on_close(archive.close)
    logger.info(
        "Account export completed records=%s elapsed_ms=%.1f",
        sum(file["records"] for file in manifest["files"]),
        (time.perf_counter() - started_at) * 1000,
    )
    return response


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
    elif scope == "year":
        year = request.args.get("year", datetime.now().year, type=int)
        if year < 2000 or year > 2100:
            return jsonify({"error": "year is out of range"}), 400
        start_date = datetime(year, 1, 1).date()
        end_date = datetime(year + 1, 1, 1).date()
        filename = f"budget-{year}.csv"
    elif scope == "range":
        start_raw = (request.args.get("start") or "").strip()
        end_raw = (request.args.get("end") or "").strip()
        try:
            start_date = datetime.strptime(start_raw[:10], "%Y-%m-%d").date()
            end_inclusive = datetime.strptime(end_raw[:10], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "start and end must be YYYY-MM-DD"}), 400
        if end_inclusive < start_date:
            return jsonify({"error": "end must be on or after start"}), 400
        end_date = end_inclusive + timedelta(days=1)
        filename = f"budget-{start_date}_to_{end_inclusive}.csv"
    else:
        week_start, week_end = get_week_range()
        start_date = week_start
        end_date = week_end + timedelta(days=1)
        filename = f"budget-week-{week_start}.csv"

    rows = db.fetch_export_rows(user_id, start_date, end_date)
    labels = db.category_labels_for_user(user_id)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Day", "Item", "Category", "Amount", "Notes", "Tags"])
    for row in rows:
        writer.writerow([
            row["expense_date"],
            row["day"],
            row["name"],
            labels.get(row["category"], row["category"]),
            f'{row["amount"]:.2f}',
            row.get("notes") or "",
            ", ".join(row.get("tags") or []),
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

    payload = json_budget_payload(budget, rows, items_by_expense, user_id=user_id)
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
    categories = db.allowed_category_slugs(user_id)
    labels = db.category_labels_for_user(user_id)
    cat_totals = {category: db.as_float(breakdown.get(category, 0)) for category in categories}
    for key, value in breakdown.items():
        if key not in cat_totals:
            cat_totals[key] = db.as_float(value)
    total_allowance = sum(db.as_float(week["allowance"]) for week in weeks)
    total_spent = sum(db.as_float(week["total_spent"]) for week in weeks)
    insights = generate_budget_insights(
        total_allowance,
        {**cat_totals, "spent": total_spent, "remaining": total_allowance - total_spent},
        period="month",
        labels=labels,
        username=session.get("username"),
    )
    buffer = build_monthly_pdf(year, month, weeks, cat_totals, insights, labels=labels)
    return pdf_response(buffer, f"{year}_{month}.pdf")


@api.route("/report-summary", methods=["GET"])
@login_required
@handle_api_errors
def report_summary():
    user_id = get_user_id()
    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()
    try:
        start_date = datetime.strptime(start_raw[:10], "%Y-%m-%d").date()
        end_inclusive = datetime.strptime(end_raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "start and end must be YYYY-MM-DD"}), 400
    if end_inclusive < start_date:
        return jsonify({"error": "end must be on or after start"}), 400
    if (end_inclusive - start_date).days > 366:
        return jsonify({"error": "Range cannot exceed 366 days"}), 400

    end_date = end_inclusive + timedelta(days=1)
    label = f"{start_date.strftime('%b %d, %Y')} to {end_inclusive.strftime('%b %d, %Y')}"
    report = db.build_period_report(user_id, start_date, end_date, label=label)
    report.pop("raw_weeks", None)
    return jsonify(report)


@api.route("/yearly-summary", methods=["GET"])
@login_required
@handle_api_errors
def yearly_summary():
    user_id = get_user_id()
    year = request.args.get("year", datetime.now().year, type=int)
    if year < 2000 or year > 2100:
        return jsonify({"error": "year is out of range"}), 400
    summary = db.get_yearly_summary(user_id, year)
    summary.pop("raw_weeks", None)
    summary.pop("month_rows", None)
    return jsonify(summary)


@api.route("/export-yearly-pdf", methods=["GET"])
@login_required
@handle_api_errors
def export_yearly_pdf():
    user_id = get_user_id()
    year = request.args.get("year", datetime.now().year, type=int)
    if year < 2000 or year > 2100:
        return jsonify({"error": "year is out of range"}), 400

    summary = db.get_yearly_summary(user_id, year)
    cat_totals = summary["breakdown"]
    labels = db.category_labels_for_user(user_id)
    insights = generate_budget_insights(
        summary["total_allowance"],
        {
            **cat_totals,
            "spent": summary["total_spent"],
            "remaining": summary["total_saved"],
        },
        period="year",
        labels=labels,
        username=session.get("username"),
    )
    buffer = build_yearly_pdf(year, summary["month_rows"], cat_totals, insights, labels=labels)
    return pdf_response(buffer, f"budget-{year}.pdf")


@api.route("/export-range-pdf", methods=["GET"])
@login_required
@handle_api_errors
def export_range_pdf():
    user_id = get_user_id()
    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()
    try:
        start_date = datetime.strptime(start_raw[:10], "%Y-%m-%d").date()
        end_inclusive = datetime.strptime(end_raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "start and end must be YYYY-MM-DD"}), 400
    if end_inclusive < start_date:
        return jsonify({"error": "end must be on or after start"}), 400
    if (end_inclusive - start_date).days > 366:
        return jsonify({"error": "Range cannot exceed 366 days"}), 400

    end_date = end_inclusive + timedelta(days=1)
    label = f"{start_date.strftime('%b %d, %Y')} to {end_inclusive.strftime('%b %d, %Y')}"
    report = db.build_period_report(user_id, start_date, end_date, label=label)
    labels = db.category_labels_for_user(user_id)
    insights = generate_budget_insights(
        report["total_allowance"],
        {
            **report["breakdown"],
            "spent": report["total_spent"],
            "remaining": report["total_saved"],
        },
        period="range",
        labels=labels,
        username=session.get("username"),
    )
    buffer = build_range_pdf(
        label, report["raw_weeks"], report["breakdown"], insights, labels=labels,
    )
    return pdf_response(buffer, f"budget-{start_date}_to_{end_inclusive}.pdf")

@api.route("/user/send-saturday-reminder", methods=["POST"])
@login_required
@handle_api_errors
def trigger_saturday_reminder():
    user_id = get_user_id()
    user = db.get_user_by_id(user_id)
    if not user or not user.get("email"):
        return jsonify({"error": "No verified email associated with this account"}), 400

    app_url = f"{app_base_url()}/dashboard"
    send_saturday_reminder_email_background(user["email"], app_url)
    return jsonify({"message": f"Saturday expense reminder email sent to {user['email']}"}), 200
