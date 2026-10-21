"""Transaction CRUD, validation, refunds, soft delete and ledger listing."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import API, NOV_END, NOV_START, dec


def test_create_income_and_expense_update_balances(
    client: TestClient, accounts, categories, make_transaction, balance_of
) -> None:
    income = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="50000.00",
        description="November salary",
        merchant_or_payee="Employer",
    )
    assert income["transaction_type"] == "income"
    assert income["account_name"] == "salary-M"
    assert income["category_name"] == "Salary"
    assert dec(income["net_amount"]) == Decimal("50000.00")
    assert dec(balance_of(accounts["salary-M"])) == Decimal("77000.00")

    expense = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="2500.00",
        description="Weekly groceries",
    )
    assert expense["transaction_type"] == "expense"
    assert dec(expense["refunded_amount"]) == Decimal("0.00")
    assert dec(expense["net_amount"]) == Decimal("2500.00")
    assert dec(balance_of(accounts["salary-M"])) == Decimal("74500.00")


def test_adjustments_require_no_category_and_move_balance(
    client: TestClient, accounts, categories, make_transaction, balance_of
) -> None:
    increase = make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="adjustment_increase",
        amount="250.00",
        description="Cash count correction",
    )
    assert increase["category_id"] is None
    assert dec(balance_of(accounts["salary-M"])) == Decimal("27250.00")

    decrease = make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="adjustment_decrease",
        amount="100.00",
        description="Missing cash correction",
    )
    assert decrease["category_id"] is None
    assert dec(balance_of(accounts["salary-M"])) == Decimal("27150.00")

    invalid = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-05",
            "transaction_type": "adjustment_increase",
            "amount": "10.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Groceries"]),
            "description": "Adjustment with category",
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_category_is_required_and_must_match_type(
    client: TestClient, accounts, categories
) -> None:
    missing = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-05",
            "transaction_type": "income",
            "amount": "100.00",
            "account_id": str(accounts["salary-M"]),
            "description": "No category",
        },
    )
    assert missing.status_code == 422

    wrong_type = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-05",
            "transaction_type": "income",
            "amount": "100.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Groceries"]),
            "description": "Income with expense category",
        },
    )
    assert wrong_type.status_code == 422
    assert wrong_type.json()["error"]["code"] == "validation_error"


def test_refund_links_to_expense_and_reduces_net_spending(
    client: TestClient, accounts, categories, make_transaction, balance_of
) -> None:
    expense = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="5000.00",
        description="Groceries",
    )
    refund = make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="refund",
        amount="2000.00",
        description="Returned groceries",
        related_transaction_id=expense["id"],
    )
    assert refund["transaction_type"] == "refund"
    assert refund["category_id"] == expense["category_id"]
    assert dec(balance_of(accounts["salary-M"])) == Decimal("24000.00")

    listed = client.get(f"{API}/transactions", params={"transaction_type": "expense"}).json()
    expense_row = listed["items"][0]
    assert dec(expense_row["refunded_amount"]) == Decimal("2000.00")
    assert dec(expense_row["net_amount"]) == Decimal("3000.00")

    detail = client.get(f"{API}/transactions/{expense['id']}").json()
    assert dec(detail["refundable_remaining"]) == Decimal("3000.00")
    assert len(detail["refunds"]) == 1
    refund_detail = client.get(f"{API}/transactions/{refund['id']}").json()
    assert refund_detail["original_transaction"]["id"] == expense["id"]


def test_refund_validation_rules(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    expense = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="5000.00",
        description="Groceries",
        transaction_date="2026-11-05",
    )

    no_original = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-06",
            "transaction_type": "refund",
            "amount": "100.00",
            "account_id": str(accounts["salary-M"]),
            "description": "Refund without original",
        },
    )
    assert no_original.status_code == 422

    too_large = make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="refund",
        amount="4000.00",
        description="First refund",
        related_transaction_id=expense["id"],
        transaction_date="2026-11-06",
    )
    assert too_large["transaction_type"] == "refund"
    exceeds = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-07",
            "transaction_type": "refund",
            "amount": "2000.00",
            "account_id": str(accounts["salary-M"]),
            "description": "Second refund exceeds remainder",
            "related_transaction_id": expense["id"],
        },
    )
    assert exceeds.status_code == 422
    assert "exceeds" in exceeds.json()["error"]["message"]

    income = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="1000.00",
        description="Salary",
    )
    refund_income = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-07",
            "transaction_type": "refund",
            "amount": "100.00",
            "account_id": str(accounts["salary-M"]),
            "description": "Refund linked to income",
            "related_transaction_id": income["id"],
        },
    )
    assert refund_income.status_code == 422

    before_original = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-01",
            "transaction_type": "refund",
            "amount": "100.00",
            "account_id": str(accounts["salary-M"]),
            "description": "Dated before the expense",
            "related_transaction_id": expense["id"],
        },
    )
    assert before_original.status_code == 422


def test_soft_delete_reverses_and_restore_reapplies(
    client: TestClient, accounts, categories, make_transaction, balance_of
) -> None:
    income = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="1000.00",
        description="Salary to be deleted",
    )
    assert dec(balance_of(accounts["salary-M"])) == Decimal("28000.00")

    deleted = client.delete(
        f"{API}/transactions/{income['id']}", params={"reason": "Duplicate entry"}
    )
    assert deleted.status_code == 200
    assert dec(balance_of(accounts["salary-M"])) == Decimal("27000.00")

    active = client.get(f"{API}/transactions").json()
    assert all(row["id"] != income["id"] for row in active["items"])
    with_deleted = client.get(
        f"{API}/transactions", params={"include_deleted": "true"}
    ).json()
    deleted_row = next(row for row in with_deleted["items"] if row["id"] == income["id"])
    assert deleted_row["deleted_at"] is not None

    restored = client.post(f"{API}/transactions/{income['id']}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["deleted_at"] is None
    assert dec(balance_of(accounts["salary-M"])) == Decimal("28000.00")

    second_delete = client.delete(
        f"{API}/transactions/{income['id']}", params={"reason": "Deleted again"}
    )
    assert second_delete.status_code == 200


def test_expense_with_refunds_cannot_be_deleted_first(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    expense = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="3000.00",
        description="Refunded expense",
    )
    refund = make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="refund",
        amount="1000.00",
        description="Partial refund",
        related_transaction_id=expense["id"],
        transaction_date="2026-11-06",
    )

    blocked = client.delete(
        f"{API}/transactions/{expense['id']}", params={"reason": "Try deleting expense"}
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "conflict"

    assert client.delete(
        f"{API}/transactions/{refund['id']}", params={"reason": "Remove refund"}
    ).status_code == 200
    assert client.delete(
        f"{API}/transactions/{expense['id']}", params={"reason": "Remove expense"}
    ).status_code == 200


def test_update_reverses_and_reapplies_balance(
    client: TestClient, accounts, categories, make_transaction, balance_of
) -> None:
    income = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="1000.00",
        description="Initial salary",
    )

    raised = client.patch(
        f"{API}/transactions/{income['id']}", json={"amount": "1500.00"}
    )
    assert raised.status_code == 200, raised.text
    assert dec(raised.json()["amount"]) == Decimal("1500.00")
    assert dec(balance_of(accounts["salary-M"])) == Decimal("28500.00")

    moved = client.patch(
        f"{API}/transactions/{income['id']}",
        json={"account_id": str(accounts["salary-A"])},
    )
    assert moved.status_code == 200, moved.text
    assert dec(balance_of(accounts["salary-M"])) == Decimal("27000.00")
    assert dec(balance_of(accounts["salary-A"])) == Decimal("1500.00")

    assert client.delete(
        f"{API}/transactions/{income['id']}", params={"reason": "For update test"}
    ).status_code == 200
    deleted_update = client.patch(
        f"{API}/transactions/{income['id']}", json={"amount": "2000.00"}
    )
    assert deleted_update.status_code == 409


def test_invalid_references_are_rejected(
    client: TestClient, accounts, categories
) -> None:
    random_id = uuid.uuid4()
    bad_account = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-05",
            "transaction_type": "income",
            "amount": "100.00",
            "account_id": str(random_id),
            "category_id": str(categories["Salary"]),
            "description": "Unknown account",
        },
    )
    assert bad_account.status_code == 422

    bad_category = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-05",
            "transaction_type": "expense",
            "amount": "100.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(random_id),
            "description": "Unknown category",
        },
    )
    assert bad_category.status_code == 422

    bad_refund_target = client.post(
        f"{API}/transactions",
        json={
            "transaction_date": "2026-11-05",
            "transaction_type": "refund",
            "amount": "100.00",
            "account_id": str(accounts["salary-M"]),
            "description": "Unknown original",
            "related_transaction_id": str(random_id),
        },
    )
    assert bad_refund_target.status_code == 404
    assert bad_refund_target.json()["error"]["code"] == "not_found"


def test_idempotency_key_returns_same_transaction(
    client: TestClient, accounts, categories
) -> None:
    payload = {
        "transaction_date": "2026-11-05",
        "transaction_type": "expense",
        "amount": "1234.00",
        "account_id": str(accounts["salary-M"]),
        "category_id": str(categories["Groceries"]),
        "description": "Idempotent expense",
        "idempotency_key": "expense-key-1",
    }
    first = client.post(f"{API}/transactions", json=payload)
    second = client.post(f"{API}/transactions", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    listed = client.get(f"{API}/transactions").json()
    assert listed["meta"]["total"] == 1


def test_list_filter_search_sort_and_pagination(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="1000.00",
        description="Salary November",
        transaction_date="2026-11-05",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="300.00",
        description="Groceries run",
        merchant_or_payee="Metro Store",
        transaction_date="2026-11-06",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Rent"],
        transaction_type="expense",
        amount="5000.00",
        description="November rent",
        transaction_date="2026-11-07",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Freelance"],
        amount="200.00",
        description="Side project",
        transaction_date="2026-11-08",
    )

    by_type = client.get(f"{API}/transactions", params={"transaction_type": "expense"}).json()
    assert by_type["meta"]["total"] == 2

    by_category = client.get(
        f"{API}/transactions", params={"category_id": str(categories["Groceries"])}
    ).json()
    assert by_category["meta"]["total"] == 1

    by_account = client.get(
        f"{API}/transactions", params={"account_id": str(accounts["salary-M"])}
    ).json()
    assert by_account["meta"]["total"] == 4

    by_date = client.get(
        f"{API}/transactions",
        params={"start_date": "2026-11-06", "end_date": "2026-11-07"},
    ).json()
    assert by_date["meta"]["total"] == 2

    by_amount = client.get(
        f"{API}/transactions", params={"amount_min": "1000.00"}
    ).json()
    assert by_amount["meta"]["total"] == 2

    search = client.get(f"{API}/transactions", params={"search": "metro"}).json()
    assert search["meta"]["total"] == 1
    assert search["items"][0]["merchant_or_payee"] == "Metro Store"

    ascending = client.get(
        f"{API}/transactions",
        params={"sort_by": "amount", "sort_dir": "asc", "page_size": 2, "page": 1},
    ).json()
    assert ascending["meta"] == {"page": 1, "page_size": 2, "total": 4, "total_pages": 2}
    assert [dec(row["amount"]) for row in ascending["items"]] == [
        Decimal("200.00"),
        Decimal("300.00"),
    ]
    second_page = client.get(
        f"{API}/transactions",
        params={"sort_by": "amount", "sort_dir": "asc", "page_size": 2, "page": 2},
    ).json()
    assert [dec(row["amount"]) for row in second_page["items"]] == [
        Decimal("1000.00"),
        Decimal("5000.00"),
    ]


def test_ledger_includes_transfers_with_directional_entries(
    client: TestClient, accounts, categories, make_transaction, make_transfer
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="7000.00",
        description="Ledger salary",
    )
    transfer = make_transfer(
        from_account_id=accounts["salary-M"],
        to_account_id=accounts["savings"],
        amount="3000.00",
        description="Move to savings",
    )

    params = {"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()}
    ledger = client.get(f"{API}/ledger", params=params).json()
    assert ledger["meta"]["total"] == 2
    kinds = {row["entry_kind"] for row in ledger["items"]}
    assert kinds == {"transaction", "transfer"}
    transfer_row = next(row for row in ledger["items"] if row["entry_kind"] == "transfer")
    assert transfer_row["id"] == transfer["id"]
    assert transfer_row["direction"] == "transfer"
    assert transfer_row["from_account_name"] == "salary-M"
    assert transfer_row["to_account_name"] == "savings"

    outgoing = client.get(
        f"{API}/ledger", params={**params, "account_id": str(accounts["salary-M"])}
    ).json()
    out_transfer = next(row for row in outgoing["items"] if row["entry_kind"] == "transfer")
    assert out_transfer["direction"] == "out"

    incoming = client.get(
        f"{API}/ledger", params={**params, "account_id": str(accounts["savings"])}
    ).json()
    in_transfer = next(row for row in incoming["items"] if row["entry_kind"] == "transfer")
    assert in_transfer["direction"] == "in"
