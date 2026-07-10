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

font_path = os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "DejaVuSans.ttf")
try:
    if os.path.isfile(font_path):
        pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
except (OSError, RuntimeError):
    logger.warning("DejaVuSans font not loaded; PDF notes may fall back to default font")

BG_DEEP = colors.HexColor("#03071a")
BG_CARD = colors.HexColor("#0a1240")
BG_ROW_ALT = colors.HexColor("#060d2e")
PURPLE_BORDER = colors.HexColor("#1a3a80")
PURPLE_MAIN = colors.HexColor("#1e6bff")
PURPLE_LIGHT = colors.HexColor("#448aff")
TEXT_WHITE = colors.HexColor("#e8eeff")
TEXT_LIGHT = colors.HexColor("#9eb3d8")
TEXT_MUTED = colors.HexColor("#4a6080")
GOLD = colors.HexColor("#ffab00")
PINK = colors.HexColor("#e8001d")
GREEN = colors.HexColor("#00e5a0")

CATEGORY_PDF_COLORS = {
    "fare": PURPLE_MAIN,
    "food": GOLD,
    "groceries": GREEN,
    "bills": colors.HexColor("#ff8f00"),
    "shopping": PURPLE_LIGHT,
    "entertainment": PINK,
    "health": colors.HexColor("#00b8d4"),
    "other": TEXT_MUTED,
}

PAGE_W, PAGE_H = landscape(letter)
MARGIN = 0.42 * inch


def pdf_paragraph_style(name, font="Helvetica", size=12, color=TEXT_WHITE, align=TA_LEFT):
    return ParagraphStyle(
        name,
        fontName=font,
        fontSize=size,
        textColor=color,
        alignment=align,
        leading=size * 1.35,
    )


def pdf_paragraph(text, font="Helvetica", size=12, color=TEXT_WHITE, align=TA_LEFT):
    return Paragraph(text, pdf_paragraph_style("_", font, size, color, align))


def section_label(text):
    return pdf_paragraph(text, "Helvetica-BoldOblique", 11, PURPLE_LIGHT)


def page_header(title, badge):
    usable = PAGE_W - 2 * MARGIN
    table = Table(
        [[
            pdf_paragraph(title, "Helvetica-Bold", 19, PURPLE_LIGHT),
            pdf_paragraph(badge, "Helvetica-Bold", 10, PURPLE_MAIN, TA_RIGHT),
        ]],
        colWidths=[usable * 0.65, usable * 0.35],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, PURPLE_MAIN),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def pdf_data_table(headers, rows, col_widths):
    data = [[pdf_paragraph(header, "Helvetica-Bold", 8, TEXT_WHITE) for header in headers]]
    for row in rows:
        data.append([pdf_paragraph(str(cell), "Helvetica", 8, TEXT_LIGHT) for cell in row])
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_ROW_ALT, BG_CARD]),
        ("GRID", (0, 0), (-1, -1), 0.4, PURPLE_BORDER),
        ("LINEBELOW", (0, -1), (-1, -1), 1.2, PURPLE_MAIN),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def pdf_total_row(label, value, col_widths):
    count = len(col_widths)
    cells = [pdf_paragraph(f"<b>{label}</b>", "Helvetica-Bold", 8, PURPLE_LIGHT)]
    for _ in range(count - 2):
        cells.append(pdf_paragraph("", "Helvetica", 8))
    cells.append(pdf_paragraph(f"<b>{value}</b>", "Helvetica-Bold", 9, GOLD))
    table = Table([cells], colWidths=col_widths)
    table.setStyle(TableStyle([
        ("SPAN", (0, 0), (count - 2, 0)),
        ("BACKGROUND", (0, 0), (-1, -1), PURPLE_BORDER),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, PURPLE_MAIN),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def stat_card(label, value, accent, width=1.65 * inch, height=0.70 * inch):
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=BG_CARD, strokeColor=accent, strokeWidth=1))
    drawing.add(Rect(0, height - 3, width, 3, fillColor=accent, strokeColor=None))
    drawing.add(String(8, height - 17, label, fillColor=TEXT_MUTED, fontSize=12, fontName="Helvetica"))
    drawing.add(String(8, 10, value, fillColor=accent, fontSize=12, fontName="Helvetica-Bold"))
    return drawing


def bar_chart(labels, values, bar_colors, width=420, height=108):
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=BG_CARD, strokeColor=PURPLE_BORDER, strokeWidth=0.8))
    if not values or max(values) == 0:
        drawing.add(String(width / 2, height / 2, "No expense data", fillColor=TEXT_MUTED, fontSize=12, textAnchor="middle"))
        return drawing

    max_value = max(values)
    count = len(values)
    pad_left, pad_right, pad_bottom, pad_top = 14, 14, 30, 14
    chart_width = width - pad_left - pad_right
    chart_height = height - pad_bottom - pad_top
    gap = chart_width / count
    bar_width = gap * 0.55
    for index, (label, value) in enumerate(zip(labels, values)):
        x = pad_left + index * gap + (gap - bar_width) / 2
        bar_height = (value / max_value) * chart_height if max_value else 0
        y = pad_bottom
        color = bar_colors[index % len(bar_colors)]
        drawing.add(Rect(x, y, bar_width, max(bar_height, 2), fillColor=color, strokeColor=None))
        if value > 0:
            drawing.add(String(
                x + bar_width / 2, y + bar_height + 3, f"{value:,.0f}",
                fillColor=TEXT_WHITE, fontSize=10, textAnchor="middle",
            ))
        drawing.add(String(x + bar_width / 2, y - 14, label, fillColor=TEXT_LIGHT, fontSize=10, textAnchor="middle"))
    return drawing


def note_box(text, width=1.5 * inch, height=0.70 * inch):
    return Table(
        [[pdf_paragraph(text, "DejaVuSans", 7, TEXT_LIGHT)]],
        colWidths=[width],
        rowHeights=[height],
        style=[
            ("BACKGROUND", (0, 0), (0, 0), BG_CARD),
            ("PADDING", (0, 0), (0, 0), 7),
            ("VALIGN", (0, 0), (0, 0), "TOP"),
            ("LINEABOVE", (0, 0), (0, 0), 2, PURPLE_MAIN),
            ("GRID", (0, 0), (0, 0), 0.4, PURPLE_BORDER),
        ],
    )


def pdf_stack(*items):
    table = Table([[item] for item in items])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def draw_pdf_background(canvas, _doc):
    canvas.saveState()
    canvas.setFillColor(BG_DEEP)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    for radius, alpha in [(200, 0.04), (130, 0.07), (70, 0.11)]:
        canvas.setFillColorRGB(0.54, 0.36, 0.96, alpha=alpha)
        canvas.circle(PAGE_W * 0.14, PAGE_H * 0.86, radius, fill=1, stroke=0)
    for radius, alpha in [(160, 0.03), (90, 0.05)]:
        canvas.setFillColorRGB(0.93, 0.32, 0.60, alpha=alpha)
        canvas.circle(PAGE_W * 0.87, PAGE_H * 0.14, radius, fill=1, stroke=0)
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
    left_width = usable * 0.475
    right_width = usable * 0.475
    gutter_width = usable * 0.05
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
    table = Table([list(cards)], colWidths=[1.72 * inch] * len(cards), rowHeights=[0.74 * inch])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def build_monthly_pdf(year, month, weeks, cat_totals, insights):
    total_allowance = sum(float(week["allowance"]) for week in weeks)
    total_spent = sum(float(week["total_spent"]) for week in weeks)
    total_saved = total_allowance - total_spent

    usable = PAGE_W - 2 * MARGIN
    left_width = usable * 0.475
    right_width = usable * 0.475
    gutter_width = usable * 0.05

    income_col_widths = [left_width * 0.18, left_width * 0.22, left_width * 0.38, left_width * 0.22]
    savings_col_widths = [left_width * 0.33, left_width * 0.30, left_width * 0.37]
    expense_col_widths = [right_width * 0.17, right_width * 0.23, right_width * 0.38, right_width * 0.22]

    income_rows = [
        [str(week["week_start_date"]), "Allowance", f"Week {index + 1} budget", f"{float(week['allowance']):,.2f}"]
        for index, week in enumerate(weeks)
    ] or [["—", "—", "No data", "0.00"]]

    expense_rows = [
        ["—", CATEGORY_LABELS[category], f"Monthly {CATEGORY_LABELS[category].lower()} total", f"{cat_totals[category]:,.2f}"]
        for category in CATEGORIES
        if cat_totals[category] > 0
    ] or [["—", "—", "No expenses", "0.00"]]

    left = [
        section_label("Income"),
        pdf_data_table(["Date", "Source", "Description", "Amount"], income_rows, income_col_widths),
        pdf_total_row("Total Income", f"{total_allowance:,.2f}", income_col_widths),
        Spacer(1, 8),
        section_label("Savings"),
        pdf_data_table(
            ["Method", "Amount Saved", "Notes"],
            [
                ["Monthly balance", f"{total_saved:,.2f}", "Total saved this month"],
                ["Total spent", f"{total_spent:,.2f}", "All expenses combined"],
            ],
            savings_col_widths,
        ),
        pdf_total_row("Total Saved", f"{total_saved:,.2f}", savings_col_widths),
    ]

    right = [
        section_label("Expenses"),
        pdf_data_table(["Date", "Category", "Description", "Amount"], expense_rows, expense_col_widths),
        pdf_total_row("Total Expenses", f"{total_spent:,.2f}", expense_col_widths),
    ]

    elements = [
        page_header("MONTHLY FINANCIAL TRACKER", f"[ {datetime(year, month, 1).strftime('%B %Y').upper()} ]"),
        Spacer(1, 10),
        stat_cards_row(
            stat_card("Total Allowance", f"{total_allowance:,.2f}", PURPLE_MAIN),
            stat_card("Total Spent", f"{total_spent:,.2f}", PINK),
            stat_card("Total Saved", f"{total_saved:,.2f}", GREEN),
            stat_card("Weeks Tracked", f"{len(weeks)} wk(s)", GOLD),
        ),
        Spacer(1, 10),
        two_col_body(left, right)[0],
        Spacer(1, 10),
    ]

    chart_width = int(left_width + gutter_width * 0.5)
    chart_categories = [category for category in CATEGORIES if cat_totals[category] > 0]
    chart = bar_chart(
        [CATEGORY_LABELS[category] for category in chart_categories],
        [cat_totals[category] for category in chart_categories],
        [CATEGORY_PDF_COLORS[category] for category in chart_categories],
        width=chart_width,
        height=108,
    )

    note_width = right_width * 0.30
    note_row = Table(
        [[note_box(insights[0], width=note_width), note_box(insights[1], width=note_width), note_box(insights[2], width=note_width)]],
        colWidths=[right_width * 0.32] * 3,
    )
    note_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    bottom = Table(
        [[
            pdf_stack(section_label("Expenses Chart"), Spacer(1, 4), chart),
            Spacer(gutter_width * 0.5, 1),
            pdf_stack(section_label("Notes"), Spacer(1, 4), note_row),
        ]],
        colWidths=[left_width + gutter_width * 0.5, gutter_width * 0.5, right_width],
    )
    bottom.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(bottom)

    return build_pdf(elements)
