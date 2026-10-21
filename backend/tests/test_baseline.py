"""Baseline semantics: opening balances are context, never income or expenses."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import API, BASELINE_DATE, NOV_END, NOV_START, dec

BASELINE_ACCOUNTS = {
    "salary-M": ("75000.00", "48000.00", "27000.00"),
    "salary-A": ("63000.00", "63000.00", "0.00"),
    "savings": ("300000.00", "195000.00", "105000.00"),
}


def _baseline_payload(data: dict, *, date: str | None = None) -> dict:
    return {
        "name": data["name"],
        "baseline_date": date or data["baseline_date"],
        "notes": data["notes"],
        "accounts": [
            {
                "account_id": entry["account_id"],
                "original_funds": entry["original_funds"],
                "historical_usage": entry["historical_usage"],
                "opening_balance": entry["opening_balance"],
                "usage_items": [
                    {
                        "description": item["description"],
                        "amount": item["amount"],
                    }
                    for item in entry["usage_items"]
                ],
            }
            for entry in data["accounts"]
        ],
    }


def test_seed_account_opening_totals(client: TestClient) -> None:
    response = client.get(
        f"{API}/accounts",
        params={"start_date": "2026-11-01", "end_date": "2026-11-30"},
    )
    assert response.status_code == 200
    accounts = {row["name"]: row for row in response.json()}
    assert set(accounts) == {"salary-M", "salary-A", "savings"}

    assert dec(accounts["salary-M"]["opening_balance"]) == Decimal("27000.00")
    assert dec(accounts["salary-A"]["opening_balance"]) == Decimal("0.00")
    assert dec(accounts["savings"]["opening_balance"]) == Decimal("105000.00")

    total = sum((dec(row["opening_balance"]) for row in accounts.values()), Decimal("0.00"))
    assert total == Decimal("132000.00")
    for row in accounts.values():
        assert dec(row["current_balance"]) == dec(row["opening_balance"])


def test_baseline_read_reflects_opening_balances(client: TestClient) -> None:
    response = client.get(f"{API}/baseline")
    assert response.status_code == 200
    data = response.json()

    assert data["baseline_date"] == BASELINE_DATE.isoformat()
    assert dec(data["total_opening_balance"]) == Decimal("132000.00")
    assert dec(data["total_original_funds"]) == Decimal("438000.00")
    assert dec(data["total_historical_usage"]) == Decimal("306000.00")

    by_name = {entry["account_name"]: entry for entry in data["accounts"]}
    assert set(by_name) == set(BASELINE_ACCOUNTS)
    for name, (original, usage, opening) in BASELINE_ACCOUNTS.items():
        entry = by_name[name]
        assert dec(entry["original_funds"]) == Decimal(original)
        assert dec(entry["historical_usage"]) == Decimal(usage)
        assert dec(entry["opening_balance"]) == Decimal(opening)
        assert entry["currency"] == "PKR"

    savings = by_name["savings"]
    assert dec(savings["itemized_usage"]) == Decimal("195000.00")
    assert dec(savings["unclassified_usage"]) == Decimal("0.00")
    usage_items = {item["description"]: dec(item["amount"]) for item in savings["usage_items"]}
    assert usage_items == {
        "Laptop": Decimal("125000.00"),
        "Committee": Decimal("70000.00"),
    }
    assert by_name["salary-M"]["usage_items"] == []


def test_baseline_summary_labels_usage_as_non_reporting(client: TestClient) -> None:
    response = client.get(f"{API}/baseline/summary")
    assert response.status_code == 200
    summary = response.json()

    assert dec(summary["opening_total"]) == Decimal("132000.00")
    assert dec(summary["historical_usage_total"]) == Decimal("306000.00")
    assert dec(summary["original_funds_total"]) == Decimal("438000.00")
    assert "not counted" in summary["note"]


def test_baseline_update_rejects_unbalanced_original_funds(client: TestClient) -> None:
    current = client.get(f"{API}/baseline").json()
    salary_m = next(
        entry for entry in current["accounts"] if entry["account_name"] == "salary-M"
    )
    payload = {
        "accounts": [
            {
                "account_id": salary_m["account_id"],
                "original_funds": "80000.00",
                "historical_usage": "48000.00",
                "opening_balance": "27000.00",
                "usage_items": [],
            }
        ]
    }
    response = client.put(f"{API}/baseline", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

    unchanged = client.get(f"{API}/baseline").json()
    assert dec(unchanged["total_original_funds"]) == Decimal("438000.00")


def test_baseline_update_is_idempotent(client: TestClient) -> None:
    before = client.get(f"{API}/baseline").json()
    payload = _baseline_payload(before)

    first = client.put(f"{API}/baseline", json=payload)
    assert first.status_code == 200, first.text
    second = client.put(f"{API}/baseline", json=payload)
    assert second.status_code == 200, second.text

    for data in (first.json(), second.json()):
        assert dec(data["total_opening_balance"]) == Decimal("132000.00")
        assert dec(data["total_historical_usage"]) == Decimal("306000.00")
        assert dec(data["total_original_funds"]) == Decimal("438000.00")
        assert data["baseline_date"] == BASELINE_DATE.isoformat()

    after = client.get(f"{API}/baseline").json()
    assert dec(after["total_opening_balance"]) == dec(before["total_opening_balance"])
    assert len(after["accounts"]) == len(before["accounts"])


def test_baseline_update_syncs_account_opening_balance(client: TestClient) -> None:
    current = client.get(f"{API}/baseline").json()
    salary_m = next(
        entry for entry in current["accounts"] if entry["account_name"] == "salary-M"
    )
    payload = {
        "accounts": [
            {
                "account_id": salary_m["account_id"],
                "original_funds": "75000.00",
                "historical_usage": "45000.00",
                "opening_balance": "30000.00",
                "usage_items": [],
            }
        ]
    }
    response = client.put(f"{API}/baseline", json=payload)
    assert response.status_code == 200, response.text
    updated = next(
        entry for entry in response.json()["accounts"] if entry["account_name"] == "salary-M"
    )
    assert dec(updated["opening_balance"]) == Decimal("30000.00")

    accounts = client.get(
        f"{API}/accounts", params={"start_date": "2026-11-01", "end_date": "2026-11-30"}
    ).json()
    salary_account = next(row for row in accounts if row["name"] == "salary-M")
    assert dec(salary_account["opening_balance"]) == Decimal("30000.00")
    assert dec(salary_account["current_balance"]) == Decimal("30000.00")

    report = client.get(
        f"{API}/reports/monthly",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    ).json()
    assert dec(report["opening_balance"]) == Decimal("135000.00")
    assert dec(report["closing_balance"]) == Decimal("135000.00")


def test_baseline_date_cannot_move_after_transactions(
    client: TestClient, accounts, categories
) -> None:
    created = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-05",
            "transaction_type": "expense",
            "amount": "100.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Groceries"]),
            "description": "Before the attempted baseline move",
        },
    )
    assert created.status_code == 201, created.text

    current = client.get(f"{API}/baseline").json()
    payload = _baseline_payload(current, date="2026-11-10")
    response = client.put(f"{API}/baseline", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"

    unchanged = client.get(f"{API}/baseline").json()
    assert unchanged["baseline_date"] == BASELINE_DATE.isoformat()


def test_historical_usage_is_excluded_from_reports(client: TestClient) -> None:
    report = client.get(
        f"{API}/reports/monthly",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    ).json()

    assert dec(report["opening_balance"]) == Decimal("132000.00")
    assert dec(report["baseline_effect"]) == Decimal("0.00")
    assert dec(report["income"]) == Decimal("0.00")
    assert dec(report["expenses_gross"]) == Decimal("0.00")
    assert dec(report["expenses_net"]) == Decimal("0.00")
    assert dec(report["net_cash_flow"]) == Decimal("0.00")
    assert dec(report["closing_balance"]) == Decimal("132000.00")
    assert report["categories"] == []
    assert report["transaction_count"] == 0

    analytics = client.get(
        f"{API}/reports/analytics",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    ).json()
    assert dec(analytics["income"]) == Decimal("0.00")
    assert dec(analytics["expenses_net"]) == Decimal("0.00")
    assert analytics["savings_rate_pct"] is None
    assert analytics["income_sources"] == []
