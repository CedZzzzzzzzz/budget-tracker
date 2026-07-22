import csv
import io
import json
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from html import escape
from zipfile import ZIP_DEFLATED, ZipFile

from reportlab.platypus import PageBreak, Spacer

from api.pdf_report import (
    GOLD,
    GREEN,
    PAGE_W,
    MARGIN,
    PRIMARY_LIGHT,
    ROSE,
    TEXT_MUTED,
    build_pdf,
    money,
    page_header,
    pdf_data_table,
    pdf_paragraph,
    section_label,
    stat_card,
    stat_cards_row,
)


SCHEMA_VERSION = 1
ARCHIVE_MAX_MEMORY_BYTES = 5 * 1024 * 1024
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
PROFILE_FIELDS = ("username", "email", "created_at", "onboarding_completed")
CUSTOM_CATEGORY_FIELDS = ("slug", "label", "color", "created_at")
CATEGORY_LIMIT_FIELDS = ("category", "weekly_limit")
RECURRING_EXPENSE_FIELDS = (
    "name", "amount", "category", "frequency", "apply_day",
    "apply_day_of_month", "active", "created_at",
)
RECURRING_APPLICATION_FIELDS = (
    "recurring_name", "period_key", "applied_at", "expense_item_name", "expense_date",
)
SAVINGS_GOAL_FIELDS = (
    "name", "target_amount", "current_amount", "deadline", "status", "created_at", "updated_at",
)
INCOME_SOURCE_FIELDS = ("label", "amount", "active", "sort_order", "created_at", "updated_at")
CATEGORY_RULE_FIELDS = ("pattern", "category", "hit_count", "updated_at")


def json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def safe_csv_value(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value)
    text = str(value)
    if text.lstrip().startswith(CSV_FORMULA_PREFIXES):
        return "'" + text
    return text


def json_bytes(value):
    return json.dumps(json_value(value), ensure_ascii=False, indent=2).encode("utf-8")


def select_fields(row, fields):
    row = row or {}
    return {field: row.get(field) for field in fields}


def select_records(rows, fields):
    return [select_fields(row, fields) for row in rows or []]


def csv_bytes(columns, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([label for _, label in columns])
    for row in rows:
        writer.writerow([safe_csv_value(row.get(key)) for key, _ in columns])
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def pdf_text(value):
    return escape(str(value if value is not None else ""))


def build_account_summary_pdf(snapshot, exported_at):
    profile = snapshot.get("profile") or {}
    budgets = snapshot.get("budgets") or []
    expense_items = snapshot.get("expense_items") or []
    custom_categories = snapshot.get("custom_categories") or []
    category_limits = snapshot.get("category_limits") or []
    recurring_expenses = snapshot.get("recurring_expenses") or []
    recurring_applications = snapshot.get("recurring_applications") or []
    savings_goals = snapshot.get("savings_goals") or []
    income_sources = snapshot.get("income_sources") or []
    category_rules = snapshot.get("category_rules") or []

    total_allowance = sum(float(row.get("allowance") or 0) for row in budgets)
    total_spent = sum(float(row.get("amount") or 0) for row in expense_items)
    balance = total_allowance - total_spent
    category_totals = {}
    for item in expense_items:
        category = str(item.get("category") or "other")
        category_totals[category] = category_totals.get(category, 0) + float(item.get("amount") or 0)
    category_labels = {row.get("slug"): row.get("label") for row in custom_categories}
    content_width = PAGE_W - 2 * MARGIN
    category_rows = [
        [pdf_text(category_labels.get(category) or category.replace("_", " ").title()), money(amount)]
        for category, amount in sorted(category_totals.items(), key=lambda row: row[1], reverse=True)
    ]
    if not category_rows:
        category_rows = [["No expense data", money(0)]]

    profile_rows = [
        ["Username", pdf_text(profile.get("username")), "Email", pdf_text(profile.get("email"))],
        ["Account created", pdf_text(profile.get("created_at")), "Onboarding", "Completed" if profile.get("onboarding_completed") else "Not completed"],
    ]
    data_rows = [
        ["Tracked weeks", len(budgets)],
        ["Expense items", len(expense_items)],
        ["Custom categories", len(custom_categories)],
        ["Category limits", len(category_limits)],
        ["Recurring expenses", len(recurring_expenses)],
        ["Recurring applications", len(recurring_applications)],
        ["Savings goals", len(savings_goals)],
        ["Income sources", len(income_sources)],
        ["Learned category rules", len(category_rules)],
    ]
    income_rows = [
        [pdf_text(row.get("label")), money(row.get("amount") or 0), "Active" if row.get("active") else "Paused"]
        for row in income_sources
    ] or [["No income sources", money(0), "-"]]
    recurring_rows = [
        [
            pdf_text(row.get("name")),
            pdf_text(row.get("frequency") or ""),
            money(row.get("amount") or 0),
            "Active" if row.get("active") else "Paused",
        ]
        for row in recurring_expenses
    ] or [["No recurring expenses", "-", money(0), "-"]]
    goal_rows = [
        [
            pdf_text(row.get("name")),
            money(row.get("current_amount") or 0),
            money(row.get("target_amount") or 0),
            pdf_text(row.get("status") or ""),
        ]
        for row in savings_goals
    ] or [["No savings goals", money(0), money(0), "-"]]

    elements = [
        page_header("Account Summary", exported_at.strftime("Exported %b %d, %Y")),
        Spacer(1, 10),
        stat_cards_row(
            stat_card("Lifetime allowance", money(total_allowance), PRIMARY_LIGHT),
            stat_card("Lifetime spending", money(total_spent), GOLD),
            stat_card("Net balance", money(balance), GREEN if balance >= 0 else ROSE),
            stat_card("Expense items", f"{len(expense_items):,}", TEXT_MUTED),
        ),
        Spacer(1, 12),
        section_label("Profile"),
        Spacer(1, 4),
        pdf_data_table(["Field", "Value", "Field", "Value"], profile_rows, [content_width * 0.16, content_width * 0.34, content_width * 0.16, content_width * 0.34], emphasize_last=False, unicode_all=True),
        Spacer(1, 10),
        section_label("Spending by category"),
        Spacer(1, 4),
        pdf_data_table(["Category", "Amount"], category_rows, [content_width * 0.70, content_width * 0.30], unicode_all=True),
        Spacer(1, 10),
        section_label("Data included"),
        Spacer(1, 4),
        pdf_data_table(["Record type", "Count"], data_rows, [content_width * 0.70, content_width * 0.30]),
        PageBreak(),
        page_header("Account Details", exported_at.strftime("Exported %b %d, %Y")),
        Spacer(1, 10),
        section_label("Income sources"),
        Spacer(1, 4),
        pdf_data_table(["Source", "Amount", "Status"], income_rows, [content_width * 0.46, content_width * 0.30, content_width * 0.24], emphasize_last=False, unicode_all=True),
        Spacer(1, 10),
        section_label("Recurring expenses"),
        Spacer(1, 4),
        pdf_data_table(["Expense", "Frequency", "Amount", "Status"], recurring_rows, [content_width * 0.38, content_width * 0.20, content_width * 0.24, content_width * 0.18], emphasize_last=False, unicode_all=True),
        Spacer(1, 10),
        section_label("Savings goals"),
        Spacer(1, 4),
        pdf_data_table(["Goal", "Current", "Target", "Status"], goal_rows, [content_width * 0.38, content_width * 0.22, content_width * 0.22, content_width * 0.18], emphasize_last=False, unicode_all=True),
        Spacer(1, 12),
        pdf_paragraph("The CSV and JSON files in this archive contain the complete detailed records.", size=8, color=TEXT_MUTED),
    ]
    buffer = build_pdf(elements)
    try:
        return buffer.read()
    finally:
        buffer.close()


def build_account_export(snapshot, exported_at=None):
    exported_at = exported_at or datetime.now(timezone.utc)
    profile = select_fields(snapshot.get("profile"), PROFILE_FIELDS)
    custom_categories = select_records(snapshot.get("custom_categories"), CUSTOM_CATEGORY_FIELDS)
    category_limits = select_records(snapshot.get("category_limits"), CATEGORY_LIMIT_FIELDS)
    recurring_expenses = select_records(snapshot.get("recurring_expenses"), RECURRING_EXPENSE_FIELDS)
    recurring_applications = select_records(snapshot.get("recurring_applications"), RECURRING_APPLICATION_FIELDS)
    savings_goals = select_records(snapshot.get("savings_goals"), SAVINGS_GOAL_FIELDS)
    income_sources = select_records(snapshot.get("income_sources"), INCOME_SOURCE_FIELDS)
    category_rules = select_records(snapshot.get("category_rules"), CATEGORY_RULE_FIELDS)
    summary_pdf = build_account_summary_pdf(snapshot, exported_at)
    files = [
        ("account-summary.pdf", summary_pdf, 1),
        ("profile.json", json_bytes(profile), 1 if snapshot.get("profile") else 0),
        (
            "budgets.csv",
            csv_bytes(
                [
                    ("week_start_date", "Week Start"),
                    ("week_end_date", "Week End"),
                    ("allowance", "Allowance"),
                    ("created_at", "Created At"),
                ],
                snapshot.get("budgets") or [],
            ),
            len(snapshot.get("budgets") or []),
        ),
        (
            "expense-items.csv",
            csv_bytes(
                [
                    ("expense_date", "Date"),
                    ("day", "Day"),
                    ("name", "Item"),
                    ("category", "Category"),
                    ("amount", "Amount"),
                    ("notes", "Notes"),
                    ("tags", "Tags"),
                    ("created_at", "Created At"),
                ],
                snapshot.get("expense_items") or [],
            ),
            len(snapshot.get("expense_items") or []),
        ),
        ("custom-categories.json", json_bytes(custom_categories), len(custom_categories)),
        ("category-limits.json", json_bytes(category_limits), len(category_limits)),
        ("recurring-expenses.json", json_bytes({
            "expenses": recurring_expenses,
            "applications": recurring_applications,
        }), len(recurring_expenses) + len(recurring_applications)),
        ("savings-goals.json", json_bytes(savings_goals), len(savings_goals)),
        ("income-sources.json", json_bytes(income_sources), len(income_sources)),
        ("category-rules.json", json_bytes(category_rules), len(category_rules)),
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": exported_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "application": "Budget Tracker",
        "files": [{"name": name, "records": records} for name, _, records in files],
    }
    archive = tempfile.SpooledTemporaryFile(max_size=ARCHIVE_MAX_MEMORY_BYTES, mode="w+b")
    with ZipFile(archive, mode="w", compression=ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json_bytes(manifest))
        for name, content, _ in files:
            bundle.writestr(name, content)
    archive.seek(0)
    return archive, manifest
