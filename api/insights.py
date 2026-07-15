from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from api.categorize import CATEGORY_LABELS
from api.errors import GEMINI_ERRORS

logger = logging.getLogger(__name__)

INSIGHT_MODEL = "gemini-2.5-flash-lite"
GEMINI_TIMEOUT_SEC = float(os.environ.get("GEMINI_AI_INSIGHT_TIMEOUT", "2.5"))

PROMPT = (
    "Write exactly 3 short, casual tips from this budget data.\n"
    "Sound like a helpful friend, not a finance advisor or chatbot.\n"
    "No buzzwords, no 'habits', no 'improve spending'. Just clear facts and simple notes.\n"
    "Max 80 characters per line. No bullets or numbers.\n"
    "You may mention the username casually.\n"
    "Use ₱ for money.\n"
    "Data:\n"
    "- Username : {username}\n"
    "- Period : {period}\n"
    "- Allowance : ₱{allowance:.2f}\n"
    "- Spending by category :\n"
    "{category_lines}\n"
    "- Total Spent : ₱{spent:.2f}\n"
    "- Remaining : ₱{remaining:.2f}"
)

GENERIC_FALLBACK = (
    "Check this week's buys when you have a minute.",
    "Log today's expenses so your balance stays accurate.",
    "A bit left? Saving even a little still counts.",
)


def insight_api_keys():
    keys = []
    for name in (
        "GEMINI_AI_INSIGHT_API_KEY",
        "GEMINI_AI_INSIGHT_API_KEY_SECONDARY",
        "GEMINI_API_KEY",
    ):
        value = (os.environ.get(name) or "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def category_spend(totals, labels):
    skip = {"spent", "remaining", "allowance"}
    rows = []
    for key, value in totals.items():
        if key in skip:
            continue
        amount = float(value or 0)
        if amount <= 0:
            continue
        rows.append((key, labels.get(key, key), amount))
    rows.sort(key=lambda item: item[2], reverse=True)
    return rows


def rule_based_insights(
    allowance,
    totals,
    *,
    labels=None,
    username=None,
    category_status=None,
    comparison=None,
    days_remaining=None,
    period="week",
):
    label_map = labels or CATEGORY_LABELS
    spent = float(totals.get("spent") or 0)
    remaining = float(totals.get("remaining", allowance - spent) or 0)
    allowance = float(allowance or 0)
    tips = []

    categories = category_spend(totals, label_map)
    if categories and spent > 0:
        name, amount = categories[0][1], categories[0][2]
        share = amount / spent * 100
        tips.append(f"Most of your spend went to {name} — ₱{amount:,.0f} ({share:.0f}%).")

    if allowance > 0:
        used_pct = spent / allowance * 100
        if remaining < 0:
            tips.append(f"You're ₱{abs(remaining):,.0f} over for this {period}.")
        elif used_pct >= 85:
            tips.append(f"{used_pct:.0f}% of your allowance is used — ₱{remaining:,.0f} left.")
        elif days_remaining and days_remaining > 0 and remaining > 0:
            per_day = remaining / days_remaining
            tips.append(
                f"₱{remaining:,.0f} left for {days_remaining} day"
                f"{'' if days_remaining == 1 else 's'} (~₱{per_day:,.0f}/day)."
            )
        elif remaining > 0:
            tips.append(f"₱{remaining:,.0f} left of ₱{allowance:,.0f}.")
        else:
            tips.append("Allowance is fully used this week.")

    if category_status:
        over = []
        if isinstance(category_status, dict):
            for category, row in category_status.items():
                if not row or not row.get("over"):
                    continue
                limit = float(row.get("limit") or 0)
                spent_cat = float(row.get("spent") or 0)
                if limit > 0 and spent_cat > limit:
                    over.append((category, spent_cat - limit))
        else:
            for row in category_status:
                limit = float(row.get("limit") or 0)
                spent_cat = float(row.get("spent") or 0)
                if limit > 0 and spent_cat > limit:
                    over.append((row.get("category"), spent_cat - limit))
        if over:
            category, over_by = max(over, key=lambda item: item[1])
            name = label_map.get(category, category or "One category")
            tips.append(f"{name} is ₱{over_by:,.0f} over the limit you set.")

    previous = (comparison or {}).get("previous") or {}
    delta = (comparison or {}).get("delta") or {}
    if previous.get("has_budget") and delta.get("spent_pct_change") is not None:
        pct = float(delta["spent_pct_change"])
        if pct > 5:
            tips.append(f"You spent {pct:.0f}% more than last {period}.")
        elif pct < -5:
            tips.append(f"You spent {abs(pct):.0f}% less than last {period}.")

    if username and len(tips) < 3:
        tips.append(f"Hey {username} — keep logging as you go.")

    while len(tips) < 3:
        tips.append(GENERIC_FALLBACK[len(tips) % len(GENERIC_FALLBACK)])

    return tips[:3]


def parse_gemini_lines(text):
    lines = []
    for raw in (text or "").strip().splitlines():
        line = raw.strip()
        line = re.sub(r"^[\-\*\d]+[\.\)\]]\s*", "", line)
        line = line.replace("&#8369;", "₱").strip()
        if line:
            lines.append(line)
    return lines[:3]


def call_gemini(api_key, prompt_text, timeout=GEMINI_TIMEOUT_SEC):
    import google.generativeai as genai

    def run():
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(INSIGHT_MODEL)
        try:
            from google.api_core import retry as google_retry
            request_options = {
                "timeout": max(timeout, 1.0),
                "retry": google_retry.Retry(
                    predicate=lambda exc: False,
                    initial=0,
                    maximum=0,
                    multiplier=1,
                    deadline=timeout,
                ),
            }
        except Exception:
            request_options = {"timeout": max(timeout, 1.0)}

        response = model.generate_content(prompt_text, request_options=request_options)
        lines = parse_gemini_lines(getattr(response, "text", "") or "")
        if len(lines) < 1:
            raise ValueError("Gemini returned no insight lines")
        while len(lines) < 3:
            lines.append(GENERIC_FALLBACK[len(lines)])
        return lines[:3]

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(run)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeout as exc:
        future.cancel()
        raise TimeoutError(f"Gemini timed out after {timeout}s") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def build_insights(
    allowance,
    totals,
    *,
    period="week",
    labels=None,
    username=None,
    category_status=None,
    comparison=None,
    days_remaining=None,
    prefer_speed=False,
):
    label_map = labels or CATEGORY_LABELS
    rules = rule_based_insights(
        allowance,
        totals,
        labels=label_map,
        username=username,
        category_status=category_status,
        comparison=comparison,
        days_remaining=days_remaining,
        period=period,
    )

    if prefer_speed:
        return {"insights": rules, "source": "rules"}

    keys = insight_api_keys()
    if not keys:
        return {"insights": rules, "source": "rules"}

    skip = {"spent", "remaining", "allowance"}
    category_keys = [
        key for key, value in totals.items()
        if key not in skip and float(value or 0) > 0
    ]
    category_lines = "\n".join(
        f"            - {label_map.get(c, c)} : ₱{float(totals.get(c, 0)):.2f}"
        for c in category_keys
    ) or "            - No category spending yet"

    prompt_text = PROMPT.format(
        username=username or "there",
        period=period,
        allowance=float(allowance or 0),
        category_lines=category_lines,
        spent=float(totals.get("spent") or 0),
        remaining=float(totals.get("remaining", 0) or 0),
    )

    for index, api_key in enumerate(keys):
        try:
            lines = call_gemini(api_key, prompt_text, timeout=GEMINI_TIMEOUT_SEC)
            return {"insights": lines, "source": "gemini"}
        except (GEMINI_ERRORS, TimeoutError, FuturesTimeout) as exc:
            which = "primary" if index == 0 else f"key-{index + 1}"
            logger.warning("Gemini AI insight (%s) failed: %s", which, exc)
        except Exception as exc:
            which = "primary" if index == 0 else f"key-{index + 1}"
            logger.warning("Gemini AI insight (%s) unexpected error: %s", which, exc)

    return {"insights": rules, "source": "rules"}


def generate_budget_insights(allowance, totals, period="week", labels=None, username=None, **kwargs):
    result = build_insights(
        allowance,
        totals,
        period=period,
        labels=labels,
        username=username,
        **kwargs,
    )
    return result["insights"]
