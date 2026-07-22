from collections import defaultdict
from statistics import median


HISTORY_WINDOW_DAYS = 90
MIN_CATEGORY_SAMPLES = 8
MIN_AMOUNT_RATIO = 2.0
MIN_ABSOLUTE_DIFFERENCE = 200.0
MIN_ROBUST_Z_SCORE = 3.5
MAX_ANOMALIES = 3
MAD_SCALE_FACTOR = 0.6745


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def category_baseline(amounts):
    typical = median(amounts)
    deviations = [abs(amount - typical) for amount in amounts]
    return typical, median(deviations)


def build_anomaly_report(rows, max_results=MAX_ANOMALIES):
    history_by_category = defaultdict(list)
    current_items = []

    for raw_row in rows or []:
        row = dict(raw_row)
        amount = as_float(row.get("amount"))
        category = str(row.get("category") or "").strip().lower()
        if amount <= 0 or not category:
            continue
        row["amount"] = amount
        row["category"] = category
        if row.get("is_current"):
            current_items.append(row)
        else:
            history_by_category[category].append(amount)

    baselines = {}
    for category, amounts in history_by_category.items():
        if len(amounts) < MIN_CATEGORY_SAMPLES:
            continue
        typical, mad = category_baseline(amounts)
        if typical > 0:
            baselines[category] = {
                "median": typical,
                "mad": mad,
                "sample_size": len(amounts),
            }

    anomalies = []
    for item in current_items:
        baseline = baselines.get(item["category"])
        if not baseline:
            continue

        amount = item["amount"]
        typical = baseline["median"]
        difference = amount - typical
        ratio = amount / typical
        mad = baseline["mad"]
        robust_z = MAD_SCALE_FACTOR * difference / mad if mad > 0 else None

        if ratio < MIN_AMOUNT_RATIO or difference < MIN_ABSOLUTE_DIFFERENCE:
            continue
        if robust_z is not None and robust_z < MIN_ROBUST_Z_SCORE:
            continue

        severity_score = max(ratio, (robust_z or 0) / MIN_ROBUST_Z_SCORE)
        severity = "high" if ratio >= 3.0 or (robust_z or 0) >= 5.0 else "moderate"
        expense_date = item.get("expense_date")
        anomalies.append({
            "item_id": item.get("item_id", item.get("id")),
            "name": str(item.get("name") or "Expense"),
            "amount": round(amount, 2),
            "category": item["category"],
            "expense_date": str(expense_date) if expense_date is not None else None,
            "baseline_median": round(typical, 2),
            "ratio": round(ratio, 2),
            "severity": severity,
            "sample_size": baseline["sample_size"],
            "severity_score": severity_score,
        })

    anomalies.sort(
        key=lambda item: (item["severity_score"], item["amount"], item["item_id"] or 0),
        reverse=True,
    )
    anomalies = anomalies[:max(0, max_results)]
    for item in anomalies:
        item.pop("severity_score", None)

    return {
        "anomalies": anomalies,
        "sample_size": sum(len(amounts) for amounts in history_by_category.values()),
        "eligible_category_count": len(baselines),
    }
