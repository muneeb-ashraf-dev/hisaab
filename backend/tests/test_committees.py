from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from tests.helpers import API


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Monthly committee",
        "monthly_amount": "5000.00",
        "start_month": "2026-01-15",
        "end_month": "2027-07-20",
        "prior_paid_installments": 0,
        "notes": "Planning record only.",
    }
    payload.update(overrides)
    return payload


def _september_committee(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Monthly committee",
        "monthly_amount": "10000.00",
        "start_month": "2026-09-01",
        "end_month": "2028-03-01",
        "prior_paid_installments": 2,
        "notes": "Started September 2026; 19 monthly installments.",
    }
    payload.update(overrides)
    return payload


def _link_expense(
    make_transaction,
    *,
    account_id,
    category_id,
    committee_id: str,
    transaction_date: str,
    amount: str = "10000.00",
) -> dict:
    return make_transaction(
        account_id=account_id,
        category_id=category_id,
        transaction_type="expense",
        transaction_date=transaction_date,
        amount=amount,
        description=f"Committee installment {transaction_date}",
        committee_id=committee_id,
    )


def test_create_committee_calculates_schedule_and_progress(
    client: TestClient, db: Session
) -> None:
    response = client.post(f"{API}/committees", json=_payload())
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["name"] == "Monthly committee"
    assert body["start_month"] == "2026-01-01"
    assert body["end_month"] == "2027-07-01"
    assert body["total_installments"] == 19
    assert body["total_amount"] == "95000.00"
    assert body["paid_installments"] == 0
    assert body["total_paid"] == "0.00"
    assert body["remaining_installments"] == 19
    assert body["remaining_amount"] == "95000.00"
    assert len(body["schedule"]) == 19
    assert body["schedule"][0]["month"] == "2026-01-01"
    assert body["schedule"][-1]["month"] == "2027-07-01"

    audit = db.scalar(
        select(AuditLog)
        .where(AuditLog.entity_type == "committee")
        .order_by(AuditLog.created_at.desc())
    )
    assert audit is not None
    assert audit.summary.startswith("Created committee")


def test_prior_paid_installments_match_the_current_example(
    client: TestClient,
) -> None:
    created = client.post(f"{API}/committees", json=_september_committee())
    assert created.status_code == 201, created.text

    response = client.get(f"{API}/committees", params={"as_of": "2026-10-15"})
    assert response.status_code == 200, response.text
    body = response.json()[0]

    assert body["total_installments"] == 19
    assert body["total_amount"] == "190000.00"
    assert body["current_month"] == "2026-10-01"
    assert body["paid_installments"] == 2
    assert body["total_paid"] == "20000.00"
    assert body["remaining_installments"] == 17
    assert body["remaining_amount"] == "170000.00"
    assert body["progress_pct"] == 10.5
    assert body["prior_paid_installments"] == 2
    assert body["linked_paid_installments"] == 0
    assert [item["status"] for item in body["schedule"][:3]] == [
        "paid",
        "paid",
        "upcoming",
    ]


def test_linked_committee_expenses_mark_months_paid(
    client: TestClient,
    accounts: dict,
    categories: dict,
    make_transaction,
) -> None:
    created = client.post(
        f"{API}/committees", json=_september_committee(prior_paid_installments=0)
    )
    assert created.status_code == 201, created.text
    committee_id = created.json()["id"]

    _link_expense(
        make_transaction,
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        committee_id=committee_id,
        transaction_date="2026-09-05",
    )
    _link_expense(
        make_transaction,
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        committee_id=committee_id,
        transaction_date="2026-10-05",
    )

    response = client.get(f"{API}/committees", params={"as_of": "2026-10-31"})
    assert response.status_code == 200, response.text
    body = response.json()[0]
    assert body["paid_installments"] == 2
    assert body["linked_paid_installments"] == 2
    assert body["total_paid"] == "20000.00"
    assert body["remaining_installments"] == 17
    assert body["remaining_amount"] == "170000.00"
    assert body["schedule"][0]["source"] == "transaction"
    assert body["schedule"][0]["paid_amount"] == "10000.00"
    assert body["schedule"][1]["status"] == "paid"


def test_as_of_month_limits_linked_payments(
    client: TestClient,
    accounts: dict,
    categories: dict,
    make_transaction,
) -> None:
    created = client.post(f"{API}/committees", json=_september_committee())
    committee_id = created.json()["id"]
    for month in ("2026-09-05", "2026-10-05", "2026-11-05"):
        _link_expense(
            make_transaction,
            account_id=accounts["salary-M"],
            category_id=categories["Groceries"],
            committee_id=committee_id,
            transaction_date=month,
        )

    october = client.get(f"{API}/committees", params={"as_of": "2026-10-15"}).json()[0]
    november = client.get(f"{API}/committees", params={"as_of": "2026-11-15"}).json()[0]
    assert october["paid_installments"] == 2
    assert november["paid_installments"] == 3
    assert november["remaining_amount"] == "160000.00"


def test_multiple_committees_are_supported(client: TestClient) -> None:
    first = client.post(f"{API}/committees", json=_september_committee())
    second = client.post(
        f"{API}/committees",
        json=_payload(name="New committee", start_month="2027-01-01", end_month="2027-12-01"),
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    listing = client.get(f"{API}/committees").json()
    assert len(listing) == 2
    assert {row["name"] for row in listing} == {"Monthly committee", "New committee"}


def test_linked_committee_expense_must_be_an_expense(
    client: TestClient, accounts: dict, categories: dict
) -> None:
    created = client.post(f"{API}/committees", json=_september_committee())
    committee_id = created.json()["id"]

    response = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-09-05",
            "transaction_type": "income",
            "amount": "10000.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Salary"]),
            "description": "Not a committee expense",
            "committee_id": committee_id,
        },
    )
    assert response.status_code == 422, response.text


def test_linked_committee_expense_date_must_be_within_plan(
    client: TestClient, accounts: dict, categories: dict
) -> None:
    created = client.post(f"{API}/committees", json=_september_committee())
    committee_id = created.json()["id"]

    response = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-08-05",
            "transaction_type": "expense",
            "amount": "10000.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Groceries"]),
            "description": "Before the plan started",
            "committee_id": committee_id,
        },
    )
    assert response.status_code == 422, response.text
    assert "committee plan period" in response.json()["error"]["message"]


def test_deleting_committee_unlinks_expenses(
    client: TestClient,
    accounts: dict,
    categories: dict,
    make_transaction,
) -> None:
    created = client.post(f"{API}/committees", json=_september_committee())
    committee_id = created.json()["id"]
    transaction = _link_expense(
        make_transaction,
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        committee_id=committee_id,
        transaction_date="2026-09-05",
    )

    deleted = client.delete(f"{API}/committees/{committee_id}")
    assert deleted.status_code == 200, deleted.text

    detail = client.get(f"{API}/transactions/{transaction['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["transaction"]["committee_id"] is None
    assert detail.json()["transaction"]["committee_name"] is None


def test_update_committee_recalculates_period(client: TestClient) -> None:
    created = client.post(f"{API}/committees", json=_payload())
    assert created.status_code == 201, created.text
    committee_id = created.json()["id"]

    response = client.patch(
        f"{API}/committees/{committee_id}",
        json={"monthly_amount": "6000.00", "end_month": "2027-08-01"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["monthly_amount"] == "6000.00"
    assert body["total_installments"] == 20
    assert body["total_amount"] == "120000.00"


def test_delete_committee(client: TestClient) -> None:
    created = client.post(f"{API}/committees", json=_payload())
    committee_id = created.json()["id"]

    response = client.delete(f"{API}/committees/{committee_id}")
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Committee deleted."

    listing = client.get(f"{API}/committees")
    assert listing.status_code == 200
    assert listing.json() == []


def test_committee_rejects_end_before_start(client: TestClient) -> None:
    response = client.post(
        f"{API}/committees",
        json=_payload(start_month="2027-01-01", end_month="2026-12-01"),
    )
    assert response.status_code == 422, response.text


def test_committee_rejects_non_positive_amount(client: TestClient) -> None:
    response = client.post(f"{API}/committees", json=_payload(monthly_amount="0.00"))
    assert response.status_code == 422, response.text


def test_committee_rejects_prior_paid_above_total(client: TestClient) -> None:
    response = client.post(
        f"{API}/committees",
        json=_september_committee(prior_paid_installments=20),
    )
    assert response.status_code == 422, response.text


def test_committee_update_rejects_invalid_merged_period(client: TestClient) -> None:
    created = client.post(f"{API}/committees", json=_payload())
    committee_id = created.json()["id"]

    response = client.patch(
        f"{API}/committees/{committee_id}", json={"end_month": "2025-12-01"}
    )
    assert response.status_code == 422, response.text
    assert "end_month" in response.json()["error"]["message"]
