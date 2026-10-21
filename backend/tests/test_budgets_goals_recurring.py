"""Budgets, financial goals and recurring templates."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import API, dec

BUDGET_MONTH = "2026-11-01"


def _create_budget(
    client: TestClient,
    *,
    category_id: uuid.UUID | None,
    amount: str,
    period_start: str = BUDGET_MONTH,
    warning_threshold: int = 80,
) -> dict:
    payload = {
        "category_id": str(category_id) if category_id else None,
        "period_start": period_start,
        "amount": amount,
        "warning_threshold": warning_threshold,
    }
    response = client.post(f"{API}/budgets", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _progress(client: TestClient, category_id: uuid.UUID | None = None) -> dict | None:
    rows = client.get(
        f"{API}/budgets/progress", params={"period_start": BUDGET_MONTH}
    ).json()
    if category_id is None:
        return next((row for row in rows if row["category_id"] is None), None)
    return next((row for row in rows if row["category_id"] == str(category_id)), None)


def test_budget_create_list_and_progress(
    client: TestClient, categories
) -> None:
    created = _create_budget(
        client, category_id=categories["Groceries"], amount="20000.00"
    )
    assert created["category_name"] == "Groceries"
    assert dec(created["amount"]) == Decimal("20000.00")
    assert created["period_start"] == BUDGET_MONTH
    assert created["warning_threshold"] == 80

    listed = client.get(
        f"{API}/budgets", params={"period_start": BUDGET_MONTH}
    ).json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]

    progress = _progress(client, categories["Groceries"])
    assert progress is not None
    assert progress["budget_id"] == created["id"]
    assert dec(progress["spent"]) == Decimal("0.00")
    assert dec(progress["remaining"]) == Decimal("20000.00")
    assert progress["utilization_pct"] == 0.0
    assert progress["status"] == "on_track"

    with_progress = client.get(
        f"{API}/budgets",
        params={"period_start": BUDGET_MONTH, "include_progress": "true"},
    ).json()
    assert with_progress[0]["spent"] == "0.00"


def test_budget_progress_thresholds(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    _create_budget(client, category_id=categories["Groceries"], amount="10000.00")

    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="5000.00",
        description="First spend",
        transaction_date="2026-11-05",
    )
    progress = _progress(client, categories["Groceries"])
    assert progress["utilization_pct"] == 50.0
    assert progress["status"] == "on_track"
    assert dec(progress["remaining"]) == Decimal("5000.00")

    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="3000.00",
        description="Reaches warning threshold",
        transaction_date="2026-11-06",
    )
    progress = _progress(client, categories["Groceries"])
    assert progress["utilization_pct"] == 80.0
    assert progress["status"] == "warning"

    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="4000.00",
        description="Over budget",
        transaction_date="2026-11-07",
    )
    progress = _progress(client, categories["Groceries"])
    assert progress["utilization_pct"] == 120.0
    assert progress["status"] == "over"
    assert dec(progress["remaining"]) == Decimal("-2000.00")


def test_budget_validation_and_duplicate_conflict(
    client: TestClient, categories
) -> None:
    income_category = client.post(
        f"{API}/budgets",
        json={
            "category_id": str(categories["Salary"]),
            "period_start": BUDGET_MONTH,
            "amount": "1000.00",
        },
    )
    assert income_category.status_code == 422
    assert income_category.json()["error"]["code"] == "validation_error"

    bad_period = client.post(
        f"{API}/budgets",
        json={
            "category_id": str(categories["Groceries"]),
            "period_start": "2026-11-02",
            "amount": "1000.00",
        },
    )
    assert bad_period.status_code == 422

    _create_budget(client, category_id=categories["Groceries"], amount="10000.00")
    duplicate = client.post(
        f"{API}/budgets",
        json={
            "category_id": str(categories["Groceries"]),
            "period_start": BUDGET_MONTH,
            "amount": "12000.00",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"

    _create_budget(client, category_id=None, amount="50000.00")
    overall_duplicate = client.post(
        f"{API}/budgets",
        json={"period_start": BUDGET_MONTH, "amount": "60000.00"},
    )
    assert overall_duplicate.status_code == 409


def test_budget_delete(client: TestClient, categories) -> None:
    created = _create_budget(client, category_id=categories["Rent"], amount="15000.00")
    deleted = client.delete(f"{API}/budgets/{created['id']}")
    assert deleted.status_code == 200
    assert client.get(f"{API}/budgets", params={"period_start": BUDGET_MONTH}).json() == []
    assert (
        client.get(f"{API}/budgets/progress", params={"period_start": BUDGET_MONTH}).json()
        == []
    )
    missing = client.delete(f"{API}/budgets/{created['id']}")
    assert missing.status_code == 404


def test_goal_contributions_and_completion(client: TestClient) -> None:
    created = client.post(
        f"{API}/goals",
        json={
            "name": "Emergency fund",
            "target_amount": "10000.00",
            "target_date": "2027-06-30",
        },
    )
    assert created.status_code == 201, created.text
    goal = created.json()
    assert goal["status"] == "active"
    assert dec(goal["current_amount"]) == Decimal("0.00")
    assert goal["progress_pct"] == 0.0

    first = client.post(
        f"{API}/goals/{goal['id']}/contributions",
        json={"amount": "6000.00", "contribution_date": "2026-11-05"},
    )
    assert first.status_code == 200, first.text
    data = first.json()
    assert dec(data["current_amount"]) == Decimal("6000.00")
    assert dec(data["remaining_amount"]) == Decimal("4000.00")
    assert data["progress_pct"] == 60.0
    assert data["status"] == "active"
    assert len(data["contributions"]) == 1

    second = client.post(
        f"{API}/goals/{goal['id']}/contributions",
        json={"amount": "5000.00", "contribution_date": "2026-11-06"},
    )
    assert second.status_code == 200, second.text
    over = second.json()
    assert dec(over["current_amount"]) == Decimal("11000.00")
    assert dec(over["remaining_amount"]) == Decimal("0.00")
    assert over["progress_pct"] == 110.0
    assert over["status"] == "completed"

    goals = client.get(f"{API}/goals").json()
    assert len(goals) == 1
    assert goals[0]["id"] == goal["id"]


def test_goal_delete_contribution_and_validation(client: TestClient) -> None:
    goal = client.post(
        f"{API}/goals",
        json={"name": "Laptop", "target_amount": "10000.00"},
    ).json()
    contribution = client.post(
        f"{API}/goals/{goal['id']}/contributions",
        json={"amount": "10000.00", "contribution_date": "2026-11-05"},
    ).json()
    assert contribution["status"] == "completed"
    contribution_id = contribution["contributions"][0]["id"]

    after_delete = client.delete(
        f"{API}/goals/{goal['id']}/contributions/{contribution_id}"
    )
    assert after_delete.status_code == 200, after_delete.text
    data = after_delete.json()
    assert dec(data["current_amount"]) == Decimal("0.00")
    assert data["progress_pct"] == 0.0
    assert data["status"] == "active"

    missing = client.delete(
        f"{API}/goals/{goal['id']}/contributions/{uuid.uuid4()}"
    )
    assert missing.status_code == 404

    duplicate = client.post(
        f"{API}/goals", json={"name": "laptop", "target_amount": "5000.00"}
    )
    assert duplicate.status_code == 409

    cancelled = client.patch(f"{API}/goals/{goal['id']}", json={"status": "cancelled"})
    assert cancelled.status_code == 200
    refused = client.post(
        f"{API}/goals/{goal['id']}/contributions",
        json={"amount": "100.00", "contribution_date": "2026-11-06"},
    )
    assert refused.status_code == 422


def test_recurring_create_upcoming_and_reminders(
    client: TestClient, accounts, categories
) -> None:
    today = date.today()
    created = client.post(
        f"{API}/recurring",
        json={
            "name": "Gym membership",
            "transaction_type": "expense",
            "amount": "1500.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Groceries"]),
            "description": "Monthly gym",
            "frequency": "monthly",
            "start_date": today.isoformat(),
            "next_due_date": (today + timedelta(days=5)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    template = created.json()
    assert template["days_until_due"] == 5
    assert template["is_active"] is True
    assert template["account_name"] == "salary-M"

    listed = client.get(f"{API}/recurring").json()
    assert len(listed) == 1
    assert listed[0]["id"] == template["id"]

    upcoming = client.get(
        f"{API}/recurring/upcoming", params={"horizon_days": 30}
    ).json()
    assert len(upcoming) == 1
    assert upcoming[0]["template_id"] == template["id"]
    assert upcoming[0]["due_date"] == (today + timedelta(days=5)).isoformat()
    assert upcoming[0]["is_overdue"] is False
    assert upcoming[0]["occurrence_status"] == "pending"

    overdue = client.post(
        f"{API}/recurring",
        json={
            "name": "Overdue bill",
            "transaction_type": "expense",
            "amount": "800.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Rent"]),
            "description": "Overdue rent",
            "frequency": "monthly",
            "start_date": (today - timedelta(days=3)).isoformat(),
            "next_due_date": (today - timedelta(days=3)).isoformat(),
        },
    )
    assert overdue.status_code == 201, overdue.text

    reminders = client.get(f"{API}/recurring/reminders").json()
    assert reminders["overdue_count"] == 1
    assert reminders["due_count"] == 0
    assert len(reminders["upcoming"]) == 2
    assert any(item["is_overdue"] for item in reminders["upcoming"])


def test_recurring_post_due_creates_transaction_once(
    client: TestClient, accounts, categories, balance_of
) -> None:
    template = client.post(
        f"{API}/recurring",
        json={
            "name": "Monthly gym",
            "transaction_type": "expense",
            "amount": "1500.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Groceries"]),
            "description": "Gym fee",
            "frequency": "monthly",
            "start_date": "2026-11-01",
            "next_due_date": "2026-11-05",
            "end_date": "2026-11-30",
        },
    ).json()

    first = client.post(
        f"{API}/recurring/{template['id']}/post", params={"through": "2026-11-30"}
    )
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["created_count"] == 1
    assert len(result["transactions"]) == 1
    assert dec(balance_of(accounts["salary-M"])) == Decimal("25500.00")

    transactions = client.get(f"{API}/transactions", params={"search": "Gym fee"}).json()
    assert transactions["meta"]["total"] == 1
    posted = transactions["items"][0]
    assert posted["source"] == "recurring"
    assert posted["transaction_date"] == "2026-11-05"

    occurrences = client.get(f"{API}/recurring/{template['id']}/occurrences").json()
    assert len(occurrences) == 1
    assert occurrences[0]["status"] == "posted"
    assert occurrences[0]["transaction_id"] == posted["id"]

    second = client.post(
        f"{API}/recurring/{template['id']}/post", params={"through": "2026-11-30"}
    ).json()
    assert second["created_count"] == 0
    assert (
        client.get(f"{API}/transactions", params={"search": "Gym fee"}).json()["meta"][
            "total"
        ]
        == 1
    )

    # Rewind the template so the occurrence guard itself is exercised.
    rewound = client.patch(
        f"{API}/recurring/{template['id']}", json={"next_due_date": "2026-11-05"}
    )
    assert rewound.status_code == 200, rewound.text
    third = client.post(
        f"{API}/recurring/{template['id']}/post", params={"through": "2026-11-30"}
    ).json()
    assert third["created_count"] == 0
    assert third["skipped_count"] == 1
    assert (
        client.get(f"{API}/transactions", params={"search": "Gym fee"}).json()["meta"][
            "total"
        ]
        == 1
    )


def test_recurring_skip_occurrence(
    client: TestClient, accounts, categories
) -> None:
    template = client.post(
        f"{API}/recurring",
        json={
            "name": "Skipped subscription",
            "transaction_type": "expense",
            "amount": "700.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Groceries"]),
            "description": "Subscription",
            "frequency": "monthly",
            "start_date": "2026-11-01",
            "next_due_date": "2026-11-05",
            "end_date": "2026-11-30",
        },
    ).json()

    skipped = client.post(
        f"{API}/recurring/{template['id']}/skip",
        params={"due_date": "2026-11-05"},
    )
    assert skipped.status_code == 200, skipped.text
    assert skipped.json()["next_due_date"] == "2026-12-05"

    occurrences = client.get(f"{API}/recurring/{template['id']}/occurrences").json()
    assert len(occurrences) == 1
    assert occurrences[0]["status"] == "skipped"

    run = client.post(
        f"{API}/recurring/{template['id']}/post", params={"through": "2026-11-30"}
    ).json()
    assert run["created_count"] == 0
    assert client.get(f"{API}/transactions").json()["meta"]["total"] == 0

    wrong_date = client.post(
        f"{API}/recurring/{template['id']}/skip",
        params={"due_date": "2026-11-05"},
    )
    assert wrong_date.status_code == 422


def test_recurring_delete_keeps_posted_transactions(
    client: TestClient, accounts, categories
) -> None:
    template = client.post(
        f"{API}/recurring",
        json={
            "name": "Temporary template",
            "transaction_type": "expense",
            "amount": "900.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Groceries"]),
            "description": "Temporary fee",
            "frequency": "monthly",
            "start_date": "2026-11-01",
            "next_due_date": "2026-11-05",
            "end_date": "2026-11-30",
        },
    ).json()
    posted = client.post(
        f"{API}/recurring/{template['id']}/post", params={"through": "2026-11-30"}
    ).json()
    assert posted["created_count"] == 1

    deleted = client.delete(f"{API}/recurring/{template['id']}")
    assert deleted.status_code == 200
    assert client.get(f"{API}/recurring/{template['id']}").status_code == 404
    assert client.get(f"{API}/recurring").json() == []

    transactions = client.get(f"{API}/transactions", params={"search": "Temporary fee"}).json()
    assert transactions["meta"]["total"] == 1
