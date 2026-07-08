from flask import Blueprint, request, jsonify, session, make_response
from datetime import datetime, timedelta
import database as db
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String
from functools import wraps
import google.generativeai as genai
import os
from api.categorize import categorize_item, CATEGORY_LABELS, CATEGORIES

font_path = os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "DejaVuSans.ttf")
pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))

api = Blueprint("api", __name__, url_prefix="/api")

prompt = """You are a financial assistant that provides insights and recommendations based on the user's budget weekly data.
            Give exactly 3 lines, a short paragraph/analysis.
            Provide actionable advice for the user to improve their spending habits and manage their budget effectively.
            Maximum of 80 characters.
            Return only the 3 lines, no bullet points, no numbering, only follow the instruction stated above.
            Mention the username.
            Always use'&#8369;' when mentioning amounts.
            You may use this as reference for the data structure:
            - Username : {username}
            - Allowance : &#8369;{allowance:.2f}
            - Spending by category :
{category_lines}
            - Total Spent : &#8369;{spent:.2f}
            - Remaining : &#8369;{remaining:.2f}
        """
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
    except Exception:
        return [
            "Review your spending habits to identify areas for improvement.",
            "Consider setting aside a portion of your remaining budget for savings.",
            "Track your expenses daily to stay within your allowance and avoid overspending.",
        ]

BG_DEEP       = colors.HexColor("#03071a")
BG_CARD       = colors.HexColor("#0a1240")
BG_ROW_ALT    = colors.HexColor("#060d2e")
PURPLE_BORDER = colors.HexColor("#1a3a80")
PURPLE_MAIN   = colors.HexColor("#1e6bff")
PURPLE_LIGHT  = colors.HexColor("#448aff")
TEXT_WHITE    = colors.HexColor("#e8eeff")
TEXT_LIGHT    = colors.HexColor("#9eb3d8")
TEXT_MUTED    = colors.HexColor("#4a6080")
GOLD          = colors.HexColor("#ffab00")
PINK          = colors.HexColor("#e8001d")
GREEN         = colors.HexColor("#00e5a0")

CATEGORY_PDF_COLORS = {
    "fare":          PURPLE_MAIN,
    "food":          GOLD,
    "groceries":     GREEN,
    "bills":         colors.HexColor("#ff8f00"),
    "shopping":      PURPLE_LIGHT,
    "entertainment": PINK,
    "health":        colors.HexColor("#00b8d4"),
    "other":         TEXT_MUTED,
}

PAGE_W, PAGE_H = landscape(letter)
MARGIN = 0.42 * inch
DAYS_MAP = {
    "Sunday": 0, "Monday": 1, "Tuesday": 2, "Wednesday": 3,
    "Thursday": 4, "Friday": 5, "Saturday": 6,
}


def _ps(name, font="Helvetica", size=12, color=TEXT_WHITE, align=TA_LEFT):
    return ParagraphStyle(name, fontName=font, fontSize=size,
                          textColor=color, alignment=align,
                          leading=size * 1.35)


def _p(text, font="Helvetica", size=12, color=TEXT_WHITE, align=TA_LEFT):
    return Paragraph(text, _ps("_", font, size, color, align))


def _section_label(text):
    return _p(text, "Helvetica-BoldOblique", 11, PURPLE_LIGHT)


def _page_header(title, badge):
    usable = PAGE_W - 2 * MARGIN
    data = [[
        _p(title, "Helvetica-Bold", 19, PURPLE_LIGHT),
        _p(badge,  "Helvetica-Bold", 10, PURPLE_MAIN, TA_RIGHT),
    ]]
    t = Table(data, colWidths=[usable * 0.65, usable * 0.35])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("LINEBELOW",     (0, 0), (-1,  0), 1.5, PURPLE_MAIN),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    return t


def _data_table(headers, rows, col_widths):
    data = [[_p(h, "Helvetica-Bold", 8, TEXT_WHITE) for h in headers]]
    for row in rows:
        data.append([_p(str(c), "Helvetica", 8, TEXT_LIGHT) for c in row])
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), PURPLE_BORDER),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [BG_ROW_ALT, BG_CARD]),
        ("GRID",          (0, 0), (-1, -1), 0.4, PURPLE_BORDER),
        ("LINEBELOW",     (0, -1),(-1, -1), 1.2, PURPLE_MAIN),
        ("PADDING",       (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _total_row(label, value, col_widths):
    n = len(col_widths)
    cells = [_p(f"<b>{label}</b>", "Helvetica-Bold", 8, PURPLE_LIGHT)]
    for _ in range(n - 2):
        cells.append(_p("", "Helvetica", 8))
    cells.append(_p(f"<b>{value}</b>", "Helvetica-Bold", 9, GOLD))
    t = Table([cells], colWidths=col_widths)
    t.setStyle(TableStyle([
        ("SPAN",       (0, 0), (n - 2, 0)),
        ("BACKGROUND", (0, 0), (-1,    -1), PURPLE_BORDER),
        ("LINEABOVE",  (0, 0), (-1,     0), 1.2, PURPLE_MAIN),
        ("PADDING",    (0, 0), (-1,    -1), 6),
        ("VALIGN",     (0, 0), (-1,    -1), "MIDDLE"),
    ]))
    return t


def _stat_card(label, value, accent, w=1.65 * inch, h=0.70 * inch):
    d = Drawing(w, h)
    d.add(Rect(0, 0,     w,  h, fillColor=BG_CARD,  strokeColor=accent, strokeWidth=1))
    d.add(Rect(0, h - 3, w,  3, fillColor=accent,   strokeColor=None))
    d.add(String(8, h - 17, label, fillColor=TEXT_MUTED, fontSize=12,  fontName="Helvetica"))
    d.add(String(8,      10, value, fillColor=accent,     fontSize=12, fontName="Helvetica-Bold"))
    return d


def _bar_chart(labels, values, bar_colors, width=420, height=108):
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=BG_CARD,
               strokeColor=PURPLE_BORDER, strokeWidth=0.8))
    if not values or max(values) == 0:
        d.add(String(width / 2, height / 2, "No expense data",
                     fillColor=TEXT_MUTED, fontSize=12, textAnchor="middle"))
        return d
    max_v = max(values)
    n     = len(values)
    pl, pr, pb, pt = 14, 14, 30, 14
    cw = width - pl - pr
    ch = height - pb - pt
    gap = cw / n
    bw  = gap * 0.55
    for i, (label, val) in enumerate(zip(labels, values)):
        x  = pl + i * gap + (gap - bw) / 2
        bh = (val / max_v) * ch if max_v else 0
        y  = pb
        c  = bar_colors[i % len(bar_colors)]
        d.add(Rect(x, y, bw, max(bh, 2), fillColor=c, strokeColor=None))
        if val > 0:
            d.add(String(x + bw / 2, y + bh + 3,
                         f"{val:,.0f}",
                         fillColor=TEXT_WHITE, fontSize=10, textAnchor="middle"))
        d.add(String(x + bw / 2, y - 14, label,
                     fillColor=TEXT_LIGHT, fontSize=10, textAnchor="middle"))
    return d


def _note_box(text, w=1.5 * inch, h=0.70 * inch):
    return Table(
        [[_p(text, "DejaVuSans", 7, TEXT_LIGHT)]],
        colWidths=[w], rowHeights=[h],
        style=[
            ("BACKGROUND", (0, 0), (0, 0), BG_CARD),
            ("PADDING",    (0, 0), (0, 0), 7),
            ("VALIGN",     (0, 0), (0, 0), "TOP"),
            ("LINEABOVE",  (0, 0), (0, 0), 2, PURPLE_MAIN),
            ("GRID",       (0, 0), (0, 0), 0.4, PURPLE_BORDER),
        ]
    )


def _stack(*items):
    t = Table([[item] for item in items])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _draw_bg(canv, doc):
    canv.saveState()
    canv.setFillColor(BG_DEEP)
    canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    for radius, alpha in [(200, 0.04), (130, 0.07), (70, 0.11)]:
        canv.setFillColorRGB(0.54, 0.36, 0.96, alpha=alpha)
        canv.circle(PAGE_W * 0.14, PAGE_H * 0.86, radius, fill=1, stroke=0)
    for radius, alpha in [(160, 0.03), (90, 0.05)]:
        canv.setFillColorRGB(0.93, 0.32, 0.60, alpha=alpha)
        canv.circle(PAGE_W * 0.87, PAGE_H * 0.14, radius, fill=1, stroke=0)
    canv.restoreState()


def _make_doc(buffer):
    return SimpleDocTemplate(
        buffer, pagesize=landscape(letter),
        topMargin=MARGIN, bottomMargin=MARGIN,
        leftMargin=MARGIN, rightMargin=MARGIN,
    )


def _build(elements):
    buffer = BytesIO()
    doc = _make_doc(buffer)
    doc.build(elements, onFirstPage=_draw_bg, onLaterPages=_draw_bg)
    buffer.seek(0)
    return buffer


def _pdf_resp(buffer, filename):
    resp = make_response(buffer.read())
    resp.headers["Content-Type"]        = "application/pdf"
    resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return resp


def _two_col_body(left_content, right_content):
    usable = PAGE_W - 2 * MARGIN
    lw = usable * 0.475
    rw = usable * 0.475
    gw = usable * 0.05
    body = Table(
        [[_stack(*left_content), Spacer(gw, 1), _stack(*right_content)]],
        colWidths=[lw, gw, rw],
    )
    body.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    return body, lw, rw, gw


def _stat_cards_row(*cards):
    ct = Table([list(cards)], colWidths=[1.72 * inch] * len(cards),
               rowHeights=[0.74 * inch])
    ct.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return ct


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


def get_week_range():
    today      = datetime.now().date()
    week_start = today - timedelta(days=(today.weekday() + 1) % 7)
    return week_start, week_start + timedelta(days=6)


def get_current_day():
    return ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"][datetime.now().weekday()]


@api.route("/register", methods=["POST"])
def register():
    try:
        data     = request.get_json()
        username = data.get("username", "").strip()
        email    = data.get("email",    "").strip()
        password = data.get("password", "").strip()

        if not username or len(username) < 5:
            return jsonify({"error": "Username must be at least 3 characters long."}), 400
        if not email or "@" not in email:
            return jsonify({"error": "Invalid email address."}), 400
        is_valid, msg = validate_password(password)
        if not is_valid:
            return jsonify({"error": msg}), 400
        if db.get_user_by_username(username):
            return jsonify({"error": "Username already exists"}), 400
        if db.get_user_by_email(email):
            return jsonify({"error": "An account is already registered with this email"}), 400

        user_id = db.create_user(username, email, password)
        if user_id:
            session["user_id"]  = user_id
            session["username"] = username
            return jsonify({"success": True, "username": username})
        return jsonify({"error": "Registration failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/login", methods=["POST"])
def login():
    try:
        data     = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400
        user = db.get_user_by_username(username)
        if not user:
            return jsonify({"error": "Username does not exist"}), 401
        if not db.verify_password(user, password):
            return jsonify({"error": "Incorrect password"}), 401

        session["user_id"]  = user["id"]
        session["username"] = user["username"]
        return jsonify({"success": True, "username": user["username"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@api.route("/check-auth", methods=["GET"])
def check_auth():
    if "user_id" in session:
        return jsonify({"authenticated": True, "username": session.get("username")})
    return jsonify({"authenticated": False})


@api.route("/current-week-info", methods=["GET"])
@login_required
def current_week_info():
    week_start, week_end = get_week_range()
    today          = datetime.now().date()
    days_remaining = (week_end - today).days
    return jsonify({
        "week_start":           str(week_start),
        "week_end":             str(week_end),
        "current_day":          get_current_day(),
        "days_remaining":       max(0, days_remaining),
        "week_start_formatted": week_start.strftime("%B %d, %Y"),
        "week_end_formatted":   week_end.strftime("%B %d, %Y"),
    })


@api.route("/set-allowance", methods=["POST"])
@login_required
def set_allowance():
    try:
        data      = request.get_json()
        allowance = float(data.get("allowance", 0))
        if allowance <= 0:
            return jsonify({"error": "Allowance must be greater than 0"}), 400

        user_id = get_user_id()
        week_start, week_end = get_week_range()
        existing = db.get_budget_by_week(user_id, week_start, week_end)
        if existing:
            db.update_budget(existing["id"], allowance)
            budget_id = existing["id"]
        else:
            budget_id = db.create_budget(user_id, week_start, week_end, allowance)
        return jsonify({"success": True, "allowance": allowance, "budget_id": budget_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/categorize-item", methods=["POST"])
@login_required
def categorize_item_route():
    try:
        data = request.get_json()
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Item name is required"}), 400
        category = categorize_item(name)
        return jsonify({
            "category": category,
            "label": CATEGORY_LABELS[category],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/add-expense-item", methods=["POST"])
@login_required
def add_expense_item_route():
    try:
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
        if amount <= 0:
            return jsonify({"error": "Amount must be greater than 0"}), 400

        if category not in CATEGORIES:
            category = categorize_item(name)

        expense_date = week_start + timedelta(days=DAYS_MAP.get(day, 0))
        budget = db.get_budget_by_week(user_id, week_start, week_end)
        if not budget:
            return jsonify({"error": "Please set allowance first."}), 404

        item, totals = db.add_expense_item(
            budget["id"], day, expense_date, name, amount, category,
        )
        return jsonify({
            "success": True,
            "day": day,
            "item": {
                "id": item["id"],
                "name": item["name"],
                "amount": item["amount"],
                "category": item["category"],
            },
            "totals": totals,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/delete-expense-item/<int:item_id>", methods=["DELETE"])
@login_required
def delete_expense_item_route(item_id):
    try:
        deleted, _ = db.delete_expense_item(item_id)
        if deleted:
            return jsonify({"success": True})
        return jsonify({"error": "Item not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/add-expense", methods=["POST"])
@login_required
def add_expense():
    try:
        data    = request.get_json()
        user_id = get_user_id()
        week_start, week_end = get_week_range()

        day   = data.get("day")
        fare  = float(data.get("fare",  0))
        food  = float(data.get("food",  0))
        other = float(data.get("other", 0))
        total = fare + food + other
        expense_date = week_start + timedelta(days=DAYS_MAP.get(day, 0))

        budget = db.get_budget_by_week(user_id, week_start, week_end)
        if not budget:
            return jsonify({"error": "Please set allowance first."}), 404
        if db.add_expense(budget["id"], day, expense_date, fare, food, other, total):
            return jsonify({"success": True, "day": day,
                            "expense": {"fare": fare, "food": food,
                                        "other": other, "total": total}})
        return jsonify({"error": f"Expenses for {day} already exist"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/delete-expense/<day>", methods=["DELETE"])
@login_required
def delete_expense(day):
    try:
        user_id = get_user_id()
        week_start, week_end = get_week_range()
        budget = db.get_budget_by_week(user_id, week_start, week_end)
        if not budget:
            return jsonify({"error": "Budget not found."}), 404
        if db.delete_expense_by_day(budget["id"], day):
            return jsonify({"success": True})
        return jsonify({"error": f"No expenses for {day}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/get-budget", methods=["GET"])
@login_required
def get_budget():
    try:
        user_id = get_user_id()
        week_start, week_end = get_week_range()
        budget = db.get_budget_by_week(user_id, week_start, week_end)

        if not budget:
            return jsonify({
                "allowance": 0, "expenses": {},
                "totals": {**{c: 0 for c in CATEGORIES}, "spent": 0, "remaining": 0},
                "days_logged": 0,
            })

        rows = db.get_expenses_by_budget(budget["id"])
        expenses = {}
        cat_totals = {c: 0 for c in CATEGORIES}
        for r in rows:
            items = db.get_items_by_expense(r["id"])
            expenses[r["day"]] = {
                **{c: r[c] for c in CATEGORIES},
                "total": r["total"],
                "items": [
                    {"id": i["id"], "name": i["name"],
                     "amount": i["amount"], "category": i["category"]}
                    for i in items
                ],
            }
            for c in CATEGORIES:
                cat_totals[c] += r[c]

        spent = sum(cat_totals.values())
        return jsonify({
            "allowance":   budget["allowance"],
            "expenses":    expenses,
            "totals":      {**cat_totals, "spent": spent,
                            "remaining": budget["allowance"] - spent},
            "days_logged": len(expenses),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/monthly-summary", methods=["GET"])
@login_required
def monthly_summary():
    try:
        user_id = get_user_id()
        month   = request.args.get("month", datetime.now().month, type=int)
        year    = request.args.get("year",  datetime.now().year,  type=int)

        start_date = datetime(year, month, 1).date()
        end_date   = (datetime(year + 1, 1, 1).date() if month == 12
                      else datetime(year, month + 1, 1).date())

        weeks     = db.get_budgets_by_month(user_id, start_date, end_date)
        breakdown = db.get_monthly_expense_breakdown(user_id, start_date, end_date)

        total_allowance = sum(w["allowance"]   for w in weeks)
        total_spent     = sum(w["total_spent"] for w in weeks)
        weekly_data = [
            {"week_start": str(w["week_start_date"]), "allowance": w["allowance"],
             "spent": w["total_spent"], "saved": w["allowance"] - w["total_spent"]}
            for w in weeks
        ]
        return jsonify({
            "month": month, "year": year,
            "month_name":      datetime(year, month, 1).strftime("%B %Y"),
            "total_allowance": total_allowance,
            "total_spent":     total_spent,
            "total_saved":     total_allowance - total_spent,
            "breakdown":       {c: breakdown.get(c, 0) for c in CATEGORIES},
            "weeks":     weekly_data,
            "num_weeks": len(weekly_data),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/week-detail", methods=["GET"])
@login_required
def week_detail():
    try:
        user_id = get_user_id()
        week_start_str = request.args.get("week_start")
        if not week_start_str:
            return jsonify({"error": "week_start is required"}), 400

        try:
            week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Invalid week_start format"}), 400

        week_end = week_start + timedelta(days=6)
        budget = db.get_budget_by_week(user_id, week_start, week_end)
        if not budget:
            return jsonify({"error": "Week not found"}), 404

        rows = db.get_expenses_by_budget(budget["id"])
        expenses = {}
        cat_totals = {c: 0 for c in CATEGORIES}
        for r in rows:
            items = db.get_items_by_expense(r["id"])
            expenses[r["day"]] = {
                **{c: r[c] for c in CATEGORIES},
                "total": r["total"],
                "items": [
                    {"id": i["id"], "name": i["name"],
                     "amount": i["amount"], "category": i["category"]}
                    for i in items
                ],
            }
            for c in CATEGORIES:
                cat_totals[c] += r[c]

        spent = sum(cat_totals.values())
        return jsonify({
            "week_start":           str(week_start),
            "week_end":             str(week_end),
            "week_start_formatted": week_start.strftime("%B %d, %Y"),
            "week_end_formatted":   week_end.strftime("%B %d, %Y"),
            "allowance":            budget["allowance"],
            "expenses":             expenses,
            "totals": {
                **cat_totals,
                "spent":     spent,
                "remaining": budget["allowance"] - spent,
            },
            "days_logged": len(expenses),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@api.route("/export-pdf", methods=["GET"])
@login_required
def export_pdf():
    try:
        user_id  = get_user_id()
        username = session.get("username", "User")
        week_start, week_end = get_week_range()

        budget = db.get_budget_by_week(user_id, week_start, week_end)
        if not budget:
            return jsonify({"error": "Budget not found."}), 404

        db_rows    = db.get_expenses_by_budget(budget["id"])
        cat_totals = {c: sum(r[c] for r in db_rows) for c in CATEGORIES}
        t_spent    = sum(cat_totals.values())
        remaining  = budget["allowance"] - t_spent

        usable = PAGE_W - 2 * MARGIN
        lw     = usable * 0.475
        rw     = usable * 0.475
        gw     = usable * 0.05

        icw = [lw*0.18, lw*0.22, lw*0.38, lw*0.22]
        scw = [lw*0.33, lw*0.30, lw*0.37]
        ecw = [rw*0.17, rw*0.23, rw*0.38, rw*0.22]

        exp_rows = []
        for r in db_rows:
            d = week_start + timedelta(days=DAYS_MAP.get(r["day"], 0))
            ds = d.strftime("%b %d")
            items = db.get_items_by_expense(r["id"])
            if items:
                for item in items:
                    cat_label = CATEGORY_LABELS.get(item["category"], "Other")
                    exp_rows.append([ds, cat_label, item["name"], f"{item['amount']:,.2f}"])
            else:
                for c in CATEGORIES:
                    if r[c] > 0:
                        exp_rows.append([ds, CATEGORY_LABELS[c], f"{CATEGORY_LABELS[c]} ({r['day']})", f"{r[c]:,.2f}"])
        if not exp_rows:
            exp_rows = [["—", "—", "No expenses logged yet", "0.00"]]

        elements = []

        badge = f"[ {week_start.strftime('%b %d')} \u2013 {week_end.strftime('%b %d, %Y').upper()} ]"
        elements.append(_page_header("WEEKLY BUDGET TRACKER", badge))
        elements.append(Spacer(1, 10))

        elements.append(_stat_cards_row(
            _stat_card("Allowance",   f"{budget['allowance']:,.2f}", PURPLE_MAIN),
            _stat_card("Total Spent", f"{t_spent:,.2f}",             PINK),
            _stat_card("Remaining",   f"{remaining:,.2f}",           GREEN),
            _stat_card("Days Logged", f"{len(db_rows)} / 7",               GOLD),
        ))
        elements.append(Spacer(1, 10))

        left = [
            _section_label("Income"),
            _data_table(
                ["Date", "Source", "Description", "Amount"],
                [[week_start.strftime("%b %d"), "Allowance",
                  f"{username}'s weekly budget", f"{budget['allowance']:,.2f}"]],
                icw,
            ),
            _total_row("Total Income", f"{budget['allowance']:,.2f}", icw),
            Spacer(1, 8),
            _section_label("Savings"),
            _data_table(
                ["Method", "Amount Saved", "Notes"],
                [["End balance",  f"{remaining:,.2f}", "Remaining this week"],
                 ["Disbursed",    f"{t_spent:,.2f}",  "All categories combined"]],
                scw,
            ),
            _total_row("Total Saved", f"{remaining:,.2f}", scw),
        ]

        right = [
            _section_label("Expenses"),
            _data_table(["Date", "Category", "Description", "Amount"], exp_rows, ecw),
            _total_row("Total Expenses", f"{t_spent:,.2f}", ecw),
        ]

        body = Table(
            [[_stack(*left), Spacer(gw, 1), _stack(*right)]],
            colWidths=[lw, gw, rw],
        )
        body.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ]))
        elements.append(body)
        elements.append(Spacer(1, 10))

        chart_w = int(lw + gw * 0.5)
        chart_cats = [c for c in CATEGORIES if cat_totals[c] > 0]
        chart = _bar_chart(
            [CATEGORY_LABELS[c] for c in chart_cats],
            [cat_totals[c] for c in chart_cats],
            [CATEGORY_PDF_COLORS[c] for c in chart_cats],
            width=chart_w, height=108,
        )

        totals = {**cat_totals, "spent": t_spent, "remaining": remaining}
        ai_notes = generate_budget_insights(budget["allowance"], totals, period="week")
        nw = rw * 0.30
        note_row = Table(
            [[_note_box(ai_notes[0], w=nw),
              _note_box(ai_notes[1], w=nw),
              _note_box(ai_notes[2], w=nw)]],
            colWidths=[rw * 0.32] * 3,
        )
        note_row.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 4),
        ]))

        bottom = Table(
            [[_stack(_section_label("Expenses Chart"), Spacer(1, 4), chart),
              Spacer(gw * 0.5, 1),
              _stack(_section_label("Notes"), Spacer(1, 4), note_row)]],
            colWidths=[lw + gw * 0.5, gw * 0.5, rw],
        )
        bottom.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ]))
        elements.append(bottom)

        return _pdf_resp(_build(elements), f"budget_{week_start}-{week_end}.pdf")


    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/export-monthly-pdf", methods=["GET"])
@login_required
def export_monthly_pdf():
    try:
        user_id = get_user_id()
        month   = request.args.get("month", datetime.now().month, type=int)
        year    = request.args.get("year",  datetime.now().year,  type=int)

        start_date = datetime(year, month, 1).date()
        end_date   = (datetime(year + 1, 1, 1).date() if month == 12
                      else datetime(year, month + 1, 1).date())

        weeks     = db.get_budgets_by_month(user_id, start_date, end_date)
        breakdown = db.get_monthly_expense_breakdown(user_id, start_date, end_date)

        t_allow = sum(w["allowance"]   for w in weeks)
        t_spent = sum(w["total_spent"] for w in weeks)
        t_saved = t_allow - t_spent
        cat_totals = {c: breakdown.get(c, 0) for c in CATEGORIES}

        usable = PAGE_W - 2 * MARGIN
        lw = usable * 0.475
        rw = usable * 0.475
        gw = usable * 0.05

        icw = [lw*0.18, lw*0.22, lw*0.38, lw*0.22]
        scw = [lw*0.33, lw*0.30, lw*0.37]
        ecw = [rw*0.17, rw*0.23, rw*0.38, rw*0.22]

        income_rows = [
            [w["week_start_date"], "Allowance",
             f"Week {i+1} budget", f"{w['allowance']:,.2f}"]
            for i, w in enumerate(weeks)
        ] or [["—", "—", "No data", "0.00"]]

        elements = []

        badge = f"[ {datetime(year, month, 1).strftime('%B %Y').upper()} ]"
        elements.append(_page_header("MONTHLY FINANCIAL TRACKER", badge))
        elements.append(Spacer(1, 10))

        elements.append(_stat_cards_row(
            _stat_card("Total Allowance", f"{t_allow:,.2f}", PURPLE_MAIN),
            _stat_card("Total Spent",     f"{t_spent:,.2f}", PINK),
            _stat_card("Total Saved",     f"{t_saved:,.2f}", GREEN),
            _stat_card("Weeks Tracked",   f"{len(weeks)} wk(s)",   GOLD),
        ))
        elements.append(Spacer(1, 10))

        left = [
            _section_label("Income"),
            _data_table(["Date", "Source", "Description", "Amount"],
                        income_rows, icw),
            _total_row("Total Income", f"{t_allow:,.2f}", icw),
            Spacer(1, 8),
            _section_label("Savings"),
            _data_table(
                ["Method", "Amount Saved", "Notes"],
                [["Monthly balance", f"{t_saved:,.2f}", "Total saved this month"],
                 ["Total spent",     f"{t_spent:,.2f}", "All expenses combined"]],
                scw,
            ),
            _total_row("Total Saved", f"{t_saved:,.2f}", scw),
        ]

        right = [
            _section_label("Expenses"),
            _data_table(
                ["Date", "Category", "Description", "Amount"],
                ([["—", CATEGORY_LABELS[c], f"Monthly {CATEGORY_LABELS[c].lower()} total", f"{cat_totals[c]:,.2f}"]
                  for c in CATEGORIES if cat_totals[c] > 0]
                 or [["—", "—", "No expenses", "0.00"]]),
                ecw,
            ),
            _total_row("Total Expenses", f"{t_spent:,.2f}", ecw),
        ]

        body = Table(
            [[_stack(*left), Spacer(gw, 1), _stack(*right)]],
            colWidths=[lw, gw, rw],
        )
        body.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ]))
        elements.append(body)
        elements.append(Spacer(1, 10))

        chart_w = int(lw + gw * 0.5)
        chart_cats = [c for c in CATEGORIES if cat_totals[c] > 0]
        chart = _bar_chart(
            [CATEGORY_LABELS[c] for c in chart_cats],
            [cat_totals[c] for c in chart_cats],
            [CATEGORY_PDF_COLORS[c] for c in chart_cats],
            width=chart_w, height=108,
        )

        totals = {**cat_totals, "spent": t_spent, "remaining": t_saved}
        ai_notes = generate_budget_insights(t_allow, totals, period="month")
        nw = rw * 0.30
        note_row = Table(
            [[_note_box(ai_notes[0], w=nw),
              _note_box(ai_notes[1], w=nw),
              _note_box(ai_notes[2], w=nw)]],
            colWidths=[rw * 0.32] * 3,
        )
        note_row.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 4),
        ]))

        bottom = Table(
            [[_stack(_section_label("Expenses Chart"), Spacer(1, 4), chart),
              Spacer(gw * 0.5, 1),
              _stack(_section_label("Notes"), Spacer(1, 4), note_row)]],
            colWidths=[lw + gw * 0.5, gw * 0.5, rw],
        )
        bottom.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ]))
        elements.append(bottom)

        return _pdf_resp(_build(elements), f"{year}_{month}.pdf")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

