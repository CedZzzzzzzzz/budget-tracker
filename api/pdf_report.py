import logging
import os
from datetime import datetime
from io import BytesIO

from flask import make_response
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from api.categorize import CATEGORIES, CATEGORY_LABELS

logger = logging.getLogger(__name__)

FONT_BODY = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_UNICODE = "Helvetica"

font_path = os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "DejaVuSans.ttf")
try:
    if os.path.isfile(font_path):
        pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
        FONT_UNICODE = "DejaVuSans"
except (OSError, RuntimeError):
    logger.warning("DejaVuSans font not loaded; PDF amounts may fall back to default font")

BG_VOID = colors.HexColor("#14032c")
BG_DEEP = colors.HexColor("#1a0538")
BG_CARD = colors.HexColor("#241048")
BG_ROW = colors.HexColor("#1e0a3d")
BORDER = colors.HexColor("#6d2fb3")
BORDER_SOFT = colors.HexColor("#4a1f7a")
PRIMARY = colors.HexColor("#8b3ce0")
PRIMARY_LIGHT = colors.HexColor("#b982ff")
PRIMARY_DIM = colors.HexColor("#4d2088")
TEXT = colors.HexColor("#f5f4f8")
TEXT_SOFT = colors.HexColor("#bfbccb")
TEXT_MUTED = colors.HexColor("#9b98a6")
GOLD = colors.HexColor("#f5c542")
ROSE = colors.HexColor("#f472b6")
GREEN = colors.HexColor("#34d399")
CYAN = colors.HexColor("#22d3ee")
ORANGE = colors.HexColor("#fb923c")

CATEGORY_PDF_COLORS = {
    "fare": PRIMARY_LIGHT,
    "food": GOLD,
    "groceries": GREEN,
    "bills": ORANGE,
    "shopping": colors.HexColor("#c084fc"),
    "entertainment": ROSE,
    "health": CYAN,
    "other": TEXT_MUTED,
}

PAGE_W, PAGE_H = landscape(letter)
MARGIN = 0.40 * inch


def money(value):
    return f"₱{float(value):,.2f}"


def pdf_paragraph_style(name, font=FONT_BODY, size=10, color=TEXT, align=TA_LEFT, leading=None):
    return ParagraphStyle(
        name,
        fontName=font,
        fontSize=size,
        textColor=color,
        alignment=align,
        leading=leading or size * 1.35,
    )


def pdf_paragraph(text, font=FONT_BODY, size=10, color=TEXT, align=TA_LEFT, leading=None):
    return Paragraph(str(text), pdf_paragraph_style("_", font, size, color, align, leading))


def section_label(text):
    return pdf_paragraph(text.upper(), FONT_BOLD, 8, PRIMARY_LIGHT)


def page_header(title, badge):
    usable = PAGE_W - 2 * MARGIN
    brand = pdf_paragraph("Budget Tracker", FONT_BOLD, 11, PRIMARY_LIGHT)
    heading = pdf_paragraph(title, FONT_BOLD, 18, TEXT)
    period = pdf_paragraph(badge, FONT_BOLD, 10, PRIMARY_LIGHT, TA_RIGHT)
    generated = pdf_paragraph(
        datetime.now().strftime("Generated %b %d, %Y · %I:%M %p"),
        FONT_BODY,
        7,
        TEXT_MUTED,
        TA_RIGHT,
    )

    left = Table([[brand], [heading]], colWidths=[usable * 0.62])
    left.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("BOTTOMPADDING", (0, 1), (0, 1), 0),
    ]))

    right = Table([[period], [generated]], colWidths=[usable * 0.38])
    right.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("BOTTOMPADDING", (0, 1), (0, 1), 0),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
    ]))

    table = Table([[left, right]], colWidths=[usable * 0.62, usable * 0.38])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.25, PRIMARY),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def pdf_data_table(headers, rows, col_widths, emphasize_last=True):
    data = [[pdf_paragraph(header, FONT_BOLD, 7, TEXT_SOFT) for header in headers]]
    for row in rows:
        cells = []
        for index, cell in enumerate(row):
            font = FONT_UNICODE if emphasize_last and index == len(row) - 1 else FONT_BODY
            color = TEXT if emphasize_last and index == len(row) - 1 else TEXT_SOFT
            align = TA_RIGHT if emphasize_last and index == len(row) - 1 else TA_LEFT
            cells.append(pdf_paragraph(str(cell), font, 7.5, color, align))
        data.append(cells)

    table = Table(data, colWidths=col_widths)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_DIM),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_ROW, BG_CARD]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, BORDER),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, BORDER_SOFT),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, PRIMARY),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    table.setStyle(TableStyle(style))
    return table


def pdf_total_row(label, value, col_widths):
    count = len(col_widths)
    cells = [pdf_paragraph(label, FONT_BOLD, 7.5, PRIMARY_LIGHT)]
    for _ in range(count - 2):
        cells.append(pdf_paragraph("", FONT_BODY, 8))
    cells.append(pdf_paragraph(value, FONT_UNICODE, 8.5, GOLD, TA_RIGHT))
    table = Table([cells], colWidths=col_widths)
    table.setStyle(TableStyle([
        ("SPAN", (0, 0), (count - 2, 0)),
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY_DIM),
        ("LINEABOVE", (0, 0), (-1, 0), 1, PRIMARY),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def stat_card(label, value, accent, width=1.78 * inch, height=0.68 * inch):
    drawing = Drawing(width, height)
    drawing.add(Rect(
        0, 0, width, height,
        fillColor=BG_CARD, strokeColor=BORDER_SOFT, strokeWidth=0.8,
    ))
    drawing.add(Rect(
        0, height - 3, width, 3,
        fillColor=accent, strokeColor=None, strokeWidth=0,
    ))
    drawing.add(String(10, height - 17, label, fillColor=TEXT_MUTED, fontSize=7, fontName=FONT_BODY))
    drawing.add(String(
        10, 12, value,
        fillColor=TEXT, fontSize=11, fontName=FONT_UNICODE,
    ))
    return drawing


def usage_bar(spent, allowance, width=None, height=0.34 * inch):
    width = width or (PAGE_W - 2 * MARGIN)
    drawing = Drawing(width, height)
    drawing.add(Rect(
        0, 0, width, height,
        fillColor=BG_CARD, strokeColor=BORDER_SOFT, strokeWidth=0.6,
    ))
    ratio = min(spent / allowance, 1.0) if allowance > 0 else 0
    fill_width = max((width - 8) * ratio, 2) if spent > 0 else 0
    fill_color = ROSE if allowance > 0 and spent > allowance else (GOLD if ratio > 0.85 else GREEN)
    if fill_width:
        drawing.add(Rect(
            4, 3, fill_width, height - 6,
            fillColor=fill_color, strokeColor=None, strokeWidth=0,
        ))
    pct = (spent / allowance * 100) if allowance > 0 else 0
    label = f"Budget used  {pct:.0f}%"
    drawing.add(String(
        width / 2, height / 2 - 2.5, label,
        fillColor=TEXT, fontSize=7.5, fontName=FONT_BOLD, textAnchor="middle",
    ))
    return drawing


def category_bars(labels, values, bar_colors, width=420, height=120):
    drawing = Drawing(width, height)
    drawing.add(Rect(
        0, 0, width, height,
        fillColor=BG_CARD, strokeColor=BORDER_SOFT, strokeWidth=0.8,
    ))
    if not values or max(values) <= 0:
        drawing.add(String(
            width / 2, height / 2, "No expense data",
            fillColor=TEXT_MUTED, fontSize=9, textAnchor="middle", fontName=FONT_BODY,
        ))
        return drawing

    max_value = max(values)
    total = sum(values) or 1
    pad_x, pad_top, row_gap = 12, 12, 3
    row_h = min(16, (height - pad_top - 8) / max(len(values), 1) - row_gap)
    label_w = width * 0.34
    amount_w = width * 0.22
    bar_area = width - label_w - amount_w - pad_x * 2

    for index, (label, value) in enumerate(zip(labels, values)):
        y = height - pad_top - (index + 1) * (row_h + row_gap)
        color = bar_colors[index % len(bar_colors)]
        short = (label[:16] + "…") if len(label) > 16 else label
        drawing.add(String(
            pad_x, y + 3, short,
            fillColor=TEXT_SOFT, fontSize=7, fontName=FONT_BODY,
        ))
        track_x = pad_x + label_w
        drawing.add(Rect(
            track_x, y + 1, bar_area, row_h - 1,
            fillColor=BG_DEEP, strokeColor=None, strokeWidth=0,
        ))
        bar_w = max((value / max_value) * bar_area, 3)
        drawing.add(Rect(
            track_x, y + 1, bar_w, row_h - 1,
            fillColor=color, strokeColor=None, strokeWidth=0,
        ))
        pct = value / total * 100
        drawing.add(String(
            width - pad_x, y + 3, f"{value:,.0f}  ({pct:.0f}%)",
            fillColor=TEXT, fontSize=7, fontName=FONT_UNICODE, textAnchor="end",
        ))
    return drawing


def insight_card(index, text, width, height=0.72 * inch):
    body = pdf_paragraph(text, FONT_UNICODE, 7, TEXT_SOFT, leading=9)
    number = pdf_paragraph(f"{index:02d}", FONT_BOLD, 8, PRIMARY_LIGHT)
    inner = Table([[number], [body]], colWidths=[width - 12])
    inner.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 3),
        ("BOTTOMPADDING", (0, 1), (0, 1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    table = Table([[inner]], colWidths=[width], rowHeights=[height])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), BG_CARD),
        ("BOX", (0, 0), (0, 0), 0.6, BORDER_SOFT),
        ("LINEABOVE", (0, 0), (0, 0), 2, PRIMARY),
        ("LEFTPADDING", (0, 0), (0, 0), 8),
        ("RIGHTPADDING", (0, 0), (0, 0), 8),
        ("TOPPADDING", (0, 0), (0, 0), 6),
        ("BOTTOMPADDING", (0, 0), (0, 0), 6),
        ("VALIGN", (0, 0), (0, 0), "TOP"),
    ]))
    return table


def pdf_stack(*items, gap=3):
    table = Table([[item] for item in items])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), gap),
    ]))
    return table


CONSTELLATION_STARS = (
    (0.06, 0.92, 1.4, 0.55, False),
    (0.11, 0.84, 1.1, 0.35, False),
    (0.18, 0.94, 1.8, 0.75, True),
    (0.22, 0.78, 1.0, 0.30, False),
    (0.28, 0.88, 1.3, 0.50, False),
    (0.34, 0.96, 0.9, 0.28, False),
    (0.41, 0.86, 1.6, 0.70, True),
    (0.48, 0.93, 1.1, 0.40, False),
    (0.55, 0.82, 1.2, 0.45, False),
    (0.62, 0.95, 1.5, 0.65, True),
    (0.69, 0.87, 1.0, 0.32, False),
    (0.76, 0.93, 1.3, 0.52, False),
    (0.84, 0.85, 1.7, 0.72, True),
    (0.91, 0.94, 1.1, 0.38, False),
    (0.95, 0.80, 1.0, 0.30, False),
    (0.08, 0.18, 1.2, 0.42, False),
    (0.14, 0.10, 1.5, 0.60, True),
    (0.21, 0.22, 1.0, 0.28, False),
    (0.27, 0.08, 1.3, 0.48, False),
    (0.35, 0.16, 1.1, 0.35, False),
    (0.43, 0.07, 1.6, 0.68, True),
    (0.52, 0.14, 1.0, 0.30, False),
    (0.60, 0.06, 1.2, 0.44, False),
    (0.68, 0.18, 1.4, 0.58, True),
    (0.76, 0.09, 1.0, 0.32, False),
    (0.85, 0.20, 1.3, 0.50, False),
    (0.93, 0.11, 1.5, 0.62, True),
    (0.04, 0.55, 0.9, 0.25, False),
    (0.97, 0.48, 1.0, 0.28, False),
    (0.09, 0.42, 1.1, 0.33, False),
    (0.88, 0.58, 1.2, 0.40, False),
    (0.16, 0.62, 0.9, 0.22, False),
    (0.80, 0.38, 1.0, 0.30, False),
)

CONSTELLATION_EDGES = (
    (0, 1), (1, 2), (2, 4), (4, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 12), (12, 13),
    (15, 16), (16, 17), (17, 18), (18, 20), (20, 21), (21, 23), (23, 24), (24, 26),
    (2, 6), (6, 9), (16, 20), (20, 23),
    (0, 29), (29, 31), (13, 30), (30, 32),
)


def draw_star_glitter(canvas, x, y, size, brightness):
    half = size / 2
    alpha = 0.25 + brightness * 0.55
    canvas.setFillColorRGB(0.725, 0.510, 1.0, alpha=alpha)
    canvas.rect(x - half, y - half, size, size, fill=1, stroke=0)
    if brightness >= 0.55:
        arm = size * 2.2
        canvas.setStrokeColorRGB(0.725, 0.510, 1.0, alpha=alpha * 0.85)
        canvas.setLineWidth(0.45)
        canvas.line(x - arm, y, x + arm, y)
        canvas.line(x, y - arm, x, y + arm)
        d = size * 0.55
        canvas.setFillColorRGB(0.96, 0.96, 1.0, alpha=min(alpha + 0.2, 0.95))
        path = canvas.beginPath()
        path.moveTo(x, y + d)
        path.lineTo(x + d, y)
        path.lineTo(x, y - d)
        path.lineTo(x - d, y)
        path.close()
        canvas.drawPath(path, fill=1, stroke=0)


def draw_pdf_background(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG_VOID)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    canvas.setFillColorRGB(0.545, 0.235, 0.878, alpha=0.07)
    canvas.rect(0, PAGE_H * 0.72, PAGE_W * 0.55, PAGE_H * 0.28, fill=1, stroke=0)
    canvas.setFillColorRGB(0.545, 0.235, 0.878, alpha=0.05)
    canvas.rect(PAGE_W * 0.55, 0, PAGE_W * 0.45, PAGE_H * 0.35, fill=1, stroke=0)
    canvas.setFillColorRGB(0.353, 0.094, 0.604, alpha=0.06)
    canvas.rect(0, 0, PAGE_W * 0.40, PAGE_H * 0.30, fill=1, stroke=0)

    stars = [
        (PAGE_W * xf, PAGE_H * yf, size, bright, glitter)
        for xf, yf, size, bright, glitter in CONSTELLATION_STARS
    ]

    canvas.setStrokeColorRGB(0.725, 0.510, 1.0, alpha=0.18)
    canvas.setLineWidth(0.5)
    for i, j in CONSTELLATION_EDGES:
        x1, y1, *rest = stars[i]
        x2, y2, *rest = stars[j]
        canvas.line(x1, y1, x2, y2)

    for x, y, size, bright, glitter in stars:
        draw_star_glitter(canvas, x, y, size if not glitter else size * 1.15, bright)

    canvas.setStrokeColor(PRIMARY)
    canvas.setLineWidth(2)
    canvas.line(0, PAGE_H - 2, PAGE_W, PAGE_H - 2)

    canvas.restoreState()


def build_pdf(elements):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
    )
    doc.build(elements, onFirstPage=draw_pdf_background, onLaterPages=draw_pdf_background)
    buffer.seek(0)
    return buffer


def pdf_response(buffer, filename):
    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


def two_col_body(left_content, right_content):
    usable = PAGE_W - 2 * MARGIN
    left_width = usable * 0.48
    right_width = usable * 0.48
    gutter_width = usable * 0.04
    body = Table(
        [[pdf_stack(*left_content), Spacer(gutter_width, 1), pdf_stack(*right_content)]],
        colWidths=[left_width, gutter_width, right_width],
    )
    body.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return body, left_width, right_width, gutter_width


def stat_cards_row(*cards):
    n = len(cards)
    usable = PAGE_W - 2 * MARGIN
    gap = 0.10 * inch
    card_w = (usable - gap * (n - 1)) / n
    table = Table([list(cards)], colWidths=[card_w] * n, rowHeights=[0.70 * inch])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -2), gap),
        ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
    ]))
    return table


def build_monthly_pdf(year, month, weeks, cat_totals, insights, labels=None):
    badge = datetime(year, month, 1).strftime("%B %Y")
    return build_period_pdf(
        "Monthly Financial Report",
        badge,
        weeks,
        cat_totals,
        insights,
        income_source="Allowance",
        income_desc_fn=lambda index, row: f"Week {index + 1} budget",
        unit_label="Weeks tracked",
        unit_value=f"{len(weeks)}",
        balance_note="Total saved this month",
        labels=labels,
    )


def build_yearly_pdf(year, month_rows, cat_totals, insights, labels=None):
    rows = [
        {
            "week_start_date": row["week_start_date"],
            "allowance": row["allowance"],
            "total_spent": row["total_spent"],
            "month_label": row["month_name"],
        }
        for row in month_rows
    ]
    return build_period_pdf(
        "Yearly Financial Report",
        str(year),
        rows,
        cat_totals,
        insights,
        income_source="Allowance",
        income_desc_fn=lambda index, row: row.get("month_label", "Month"),
        expense_desc_fn=lambda label: f"Yearly {label.lower()} total",
        unit_label="Months tracked",
        unit_value=f"{len(month_rows)}",
        balance_note="Total saved this year",
        labels=labels,
    )


def build_range_pdf(label, weeks, cat_totals, insights, labels=None):
    return build_period_pdf(
        "Custom Range Report",
        label,
        weeks,
        cat_totals,
        insights,
        income_source="Allowance",
        income_desc_fn=lambda index, row: f"Week {index + 1} budget",
        expense_desc_fn=lambda cat_label: f"Range {cat_label.lower()} total",
        unit_label="Weeks tracked",
        unit_value=f"{len(weeks)}",
        balance_note="Net for selected range",
        labels=labels,
    )


def build_period_pdf(
    title,
    badge,
    rows,
    cat_totals,
    insights,
    *,
    income_source="Allowance",
    income_desc_fn=None,
    expense_desc_fn=None,
    unit_label="Periods",
    unit_value="0",
    balance_note="Balance",
    labels=None,
):
    if income_desc_fn is None:
        income_desc_fn = lambda index, row: f"Period {index + 1}"
    if expense_desc_fn is None:
        expense_desc_fn = lambda label: f"{label} total"
    label_map = {**CATEGORY_LABELS, **(labels or {})}

    total_allowance = sum(float(row["allowance"]) for row in rows)
    total_spent = sum(float(row.get("total_spent", row.get("spent", 0))) for row in rows)
    total_saved = total_allowance - total_spent
    saved_accent = GREEN if total_saved >= 0 else ROSE

    usable = PAGE_W - 2 * MARGIN
    left_width = usable * 0.48
    right_width = usable * 0.48

    income_col_widths = [left_width * 0.20, left_width * 0.22, left_width * 0.36, left_width * 0.22]
    savings_col_widths = [left_width * 0.34, left_width * 0.28, left_width * 0.38]

    income_rows = [
        [
            str(row["week_start_date"]),
            income_source,
            income_desc_fn(index, row),
            money(row["allowance"]),
        ]
        for index, row in enumerate(rows)
    ] or [["—", "—", "No data", money(0)]]

    category_order = list(dict.fromkeys([*CATEGORIES, *cat_totals.keys()]))
    chart_categories = [
        category for category in category_order
        if float(cat_totals.get(category, 0) or 0) > 0
    ]
    chart_height = min(175, 28 + max(len(chart_categories), 1) * 20)
    chart = category_bars(
        [label_map.get(category, category) for category in chart_categories],
        [float(cat_totals[category]) for category in chart_categories],
        [CATEGORY_PDF_COLORS.get(category, TEXT_MUTED) for category in chart_categories],
        width=right_width,
        height=chart_height,
    )

    left = [
        section_label("Income"),
        pdf_data_table(["Date", "Source", "Description", "Amount"], income_rows, income_col_widths),
        pdf_total_row("Total income", money(total_allowance), income_col_widths),
        Spacer(1, 4),
        section_label("Savings"),
        pdf_data_table(
            ["Method", "Amount", "Notes"],
            [
                ["Period balance", money(total_saved), balance_note],
                ["Total spent", money(total_spent), "All expenses combined"],
            ],
            savings_col_widths,
        ),
        pdf_total_row("Total saved", money(total_saved), savings_col_widths),
    ]

    right = [
        section_label("Spending by category"),
        chart,
        Spacer(1, 4),
        pdf_total_row("Total expenses", money(total_spent), [right_width * 0.62, right_width * 0.38]),
    ]

    note_items = list(insights or [])[:3]
    while len(note_items) < 3:
        note_items.append("No additional notes for this period.")
    note_gap = 0.08 * inch
    note_width = (usable - note_gap * 2) / 3
    note_row = Table(
        [[
            insight_card(1, note_items[0], note_width),
            insight_card(2, note_items[1], note_width),
            insight_card(3, note_items[2], note_width),
        ]],
        colWidths=[note_width + note_gap, note_width + note_gap, note_width],
    )
    note_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -2), note_gap),
        ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
    ]))

    card_w = (usable - 0.30 * inch) / 4
    elements = [
        page_header(title, badge),
        Spacer(1, 8),
        stat_cards_row(
            stat_card("Total allowance", money(total_allowance), PRIMARY, width=card_w),
            stat_card("Total spent", money(total_spent), ROSE, width=card_w),
            stat_card("Total saved", money(total_saved), saved_accent, width=card_w),
            stat_card(unit_label, str(unit_value), GOLD, width=card_w),
        ),
        Spacer(1, 6),
        usage_bar(total_spent, total_allowance, width=usable),
        Spacer(1, 8),
        two_col_body(left, right)[0],
        Spacer(1, 8),
        section_label("Insights"),
        Spacer(1, 3),
        note_row,
    ]

    return build_pdf(elements)
