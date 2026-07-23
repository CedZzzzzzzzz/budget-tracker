import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


MAX_RECEIPT_ITEMS = 50
MAX_RECEIPT_WARNINGS = 10
MAX_MERCHANT_LEN = 120
MAX_RECEIPT_ITEM_NAME_LEN = 200
MONEY_QUANTUM = Decimal("0.01")


class ReceiptSchemaError(ValueError):
    pass


def clean_text(value, maximum):
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    text = " ".join(text.split())
    return text[:maximum]


def money_value(value, *, required=False):
    if value in (None, ""):
        if required:
            raise ReceiptSchemaError("A receipt amount is missing.")
        return None
    try:
        amount = Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ReceiptSchemaError("A receipt amount is invalid.") from error
    if (
        not amount.is_finite()
        or amount < 0
        or amount > Decimal("9999999999.99")
    ):
        raise ReceiptSchemaError("A receipt amount is outside the supported range.")
    return amount


def date_value(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return None


def confidence_value(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def provider_schema(category_slugs):
    allowed = list(dict.fromkeys(category_slugs)) or ["other"]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["merchant", "purchase_date", "currency", "total", "items", "warnings"],
        "properties": {
            "merchant": {"type": "string"},
            "merchant_confidence": {"type": "number"},
            "purchase_date": {"type": ["string", "null"], "format": "date"},
            "date_confidence": {"type": "number"},
            "currency": {"type": "string"},
            "subtotal": {"type": ["number", "null"]},
            "tax": {"type": ["number", "null"]},
            "discount": {"type": ["number", "null"]},
            "total": {"type": ["number", "null"]},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "amount", "category", "confidence"],
                    "properties": {
                        "name": {"type": "string"},
                        "quantity": {"type": ["number", "null"]},
                        "unit_price": {"type": ["number", "null"]},
                        "amount": {"type": ["number", "null"]},
                        "category": {"type": "string", "enum": allowed},
                        "confidence": {"type": "number"},
                    },
                },
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }


def parse_provider_text(text):
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError as error:
        raise ReceiptSchemaError("The receipt response was not valid JSON.") from error
    if not isinstance(payload, dict):
        raise ReceiptSchemaError("The receipt response must be an object.")
    return payload


def normalize_receipt(payload):
    if not isinstance(payload, dict):
        raise ReceiptSchemaError("The receipt response must be an object.")
    merchant = clean_text(payload.get("merchant"), MAX_MERCHANT_LEN)
    total = money_value(payload.get("total"))
    items = []
    raw_items = payload.get("items") or []
    if not isinstance(raw_items, list):
        raise ReceiptSchemaError("Receipt items must be a list.")
    if len(raw_items) > MAX_RECEIPT_ITEMS:
        raise ReceiptSchemaError("The receipt contains too many items.")

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        name = clean_text(raw.get("name"), MAX_RECEIPT_ITEM_NAME_LEN)
        amount = money_value(raw.get("amount"))
        if not name or amount is None or amount <= 0:
            continue
        items.append({
            "name": name,
            "quantity": float(money_value(raw.get("quantity")) or 1),
            "unit_price": (
                float(unit_price)
                if (unit_price := money_value(raw.get("unit_price"))) is not None
                else None
            ),
            "amount": float(amount),
            "category": clean_text(raw.get("category"), 32).lower(),
            "confidence": confidence_value(raw.get("confidence")),
        })

    if not items and total is not None and total > 0:
        items.append({
            "name": merchant or "Receipt purchase",
            "quantity": 1.0,
            "unit_price": float(total),
            "amount": float(total),
            "category": "",
            "confidence": confidence_value(payload.get("merchant_confidence")),
        })

    if not items and (total is None or total <= 0):
        raise ReceiptSchemaError("No usable receipt total or line items were found.")

    warnings = []
    raw_warnings = payload.get("warnings") or []
    if not isinstance(raw_warnings, list):
        raw_warnings = []
    for warning in raw_warnings:
        cleaned = clean_text(warning, 160)
        if cleaned and cleaned not in warnings:
            warnings.append(cleaned)
        if len(warnings) >= MAX_RECEIPT_WARNINGS:
            break

    detected_currency = clean_text(payload.get("currency"), 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", detected_currency):
        currency = "PHP"
        warnings.append("The receipt currency was unclear, so PHP was assumed.")
    else:
        currency = detected_currency
        if currency != "PHP":
            warnings.append(
                f"The receipt appears to use {currency}. Budget Tracker stores amounts in PHP."
            )

    line_sum = sum((Decimal(str(item["amount"])) for item in items), Decimal("0"))
    if total is None:
        total = line_sum.quantize(MONEY_QUANTUM)
        warnings.append("Receipt total was calculated from the readable line items.")
    difference = abs(total - line_sum)
    tolerance = max(Decimal("1.00"), total * Decimal("0.01"))
    reconciled = difference <= tolerance
    if not reconciled:
        warnings.append("Line items do not match the detected receipt total.")

    return {
        "merchant": merchant,
        "merchant_confidence": confidence_value(payload.get("merchant_confidence")),
        "purchase_date": date_value(payload.get("purchase_date")),
        "date_confidence": confidence_value(payload.get("date_confidence")),
        "currency": currency,
        "subtotal": (
            float(subtotal)
            if (subtotal := money_value(payload.get("subtotal"))) is not None
            else None
        ),
        "tax": (
            float(tax)
            if (tax := money_value(payload.get("tax"))) is not None
            else None
        ),
        "discount": (
            float(discount)
            if (discount := money_value(payload.get("discount"))) is not None
            else None
        ),
        "total": float(total),
        "items": items,
        "warnings": warnings[:MAX_RECEIPT_WARNINGS],
        "reconciled": reconciled,
        "mode": "itemized" if len(items) > 1 and reconciled else "total",
    }
