from datetime import date

from api.anomalies import build_anomaly_report


def row(item_id, amount, category="food", current=False):
    return {
        "item_id": item_id,
        "name": f"Item {item_id}",
        "amount": amount,
        "category": category,
        "expense_date": date(2026, 7, 20),
        "is_current": current,
    }


def test_flags_obvious_spike_with_zero_mad():
    rows = [row(i, 100) for i in range(1, 9)]
    rows.append(row(20, 500, current=True))

    report = build_anomaly_report(rows)

    assert report["sample_size"] == 8
    assert report["eligible_category_count"] == 1
    assert report["anomalies"][0]["item_id"] == 20
    assert report["anomalies"][0]["baseline_median"] == 100
    assert report["anomalies"][0]["ratio"] == 5


def test_requires_enough_history_in_same_category():
    rows = [row(i, 100) for i in range(1, 8)]
    rows += [row(i, 50, category="fare") for i in range(10, 18)]
    rows.append(row(30, 600, current=True))

    report = build_anomaly_report(rows)

    assert report["eligible_category_count"] == 1
    assert report["anomalies"] == []


def test_relative_and_absolute_guards_reduce_false_positives():
    history = [90, 95, 98, 100, 100, 102, 105, 110]
    rows = [row(i, amount) for i, amount in enumerate(history, 1)]
    rows.extend([
        row(20, 190, current=True),
        row(21, 250, current=True),
    ])

    report = build_anomaly_report(rows)

    assert report["anomalies"] == []


def test_mad_guard_rejects_a_variable_category():
    history = [10, 20, 30, 80, 120, 170, 200, 250]
    rows = [row(i, amount) for i, amount in enumerate(history, 1)]
    rows.append(row(20, 400, current=True))

    report = build_anomaly_report(rows)

    assert report["anomalies"] == []


def test_ranks_and_caps_results_by_severity():
    rows = [row(i, 100) for i in range(1, 9)]
    rows += [row(20, 350, current=True), row(21, 700, current=True), row(22, 500, current=True)]

    report = build_anomaly_report(rows, max_results=2)

    assert [item["item_id"] for item in report["anomalies"]] == [21, 22]


def test_current_items_never_enter_the_baseline():
    rows = [row(i, 100) for i in range(1, 9)]
    rows += [row(20, 1000, current=True), row(21, 1100, current=True)]

    report = build_anomaly_report(rows)

    assert all(item["baseline_median"] == 100 for item in report["anomalies"])
