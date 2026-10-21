"""Health, system, CRUD contract, authentication and error-envelope tests."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.helpers import API, dec


def test_health_root_and_readiness(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "app": settings.app_name,
        "env": "test",
    }

    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "database": "connected"}

    root = client.get("/")
    assert root.status_code == 200
    body = root.json()
    assert body["health"] == "/health"
    assert body["docs"] == "/docs"
    assert body["version"] == "1.0.0"


def test_system_status(client: TestClient) -> None:
    response = client.get(f"{API}/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["app_name"] == settings.app_name
    assert body["app_env"] == "test"
    assert body["currency"] == "PKR"
    assert body["auth_enabled"] is False
    assert body["baseline_date"] == "2026-11-01"
    assert body["database_connected"] is True
    assert body["version"] == "1.0.0"


def test_accounts_crud(client: TestClient) -> None:
    created = client.post(
        f"{API}/accounts",
        json={
            "name": "Test Wallet",
            "account_type": "cash",
            "currency": "usd",
            "opening_balance": "1000.00",
            "opening_date": "2026-11-01",
            "notes": "Created by contract test",
        },
    )
    assert created.status_code == 201, created.text
    account = created.json()
    assert account["name"] == "Test Wallet"
    assert account["currency"] == "USD"
    assert account["account_type"] == "cash"
    account_id = account["id"]

    listed = client.get(
        f"{API}/accounts", params={"start_date": "2026-11-01", "end_date": "2026-11-30"}
    ).json()
    assert {row["name"] for row in listed} == {
        "salary-M",
        "salary-A",
        "savings",
        "Test Wallet",
    }

    detail = client.get(
        f"{API}/accounts/{account_id}",
        params={"start_date": "2026-11-01", "end_date": "2026-11-30"},
    )
    assert detail.status_code == 200
    assert dec(detail.json()["current_balance"]) == Decimal("1000.00")
    assert dec(detail.json()["projected_balance"]) == Decimal("1000.00")

    updated = client.patch(
        f"{API}/accounts/{account_id}",
        json={"name": "Renamed Wallet", "opening_balance": "1500.00", "is_active": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Renamed Wallet"
    assert dec(updated.json()["opening_balance"]) == Decimal("1500.00")
    assert updated.json()["is_active"] is False

    active_only = client.get(
        f"{API}/accounts",
        params={
            "start_date": "2026-11-01",
            "end_date": "2026-11-30",
            "include_inactive": "false",
        },
    ).json()
    assert all(row["name"] != "Renamed Wallet" for row in active_only)

    deleted = client.delete(f"{API}/accounts/{account_id}")
    assert deleted.status_code == 200
    assert deleted.json()["message"] == "Account deleted."
    assert client.get(f"{API}/accounts/{account_id}").status_code == 404

    bad_type = client.post(
        f"{API}/accounts",
        json={
            "name": "Bad Type",
            "account_type": "credit",
            "opening_balance": "0.00",
            "opening_date": "2026-11-01",
        },
    )
    assert bad_type.status_code == 422


def test_account_conflicts_and_deletion_guard(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    duplicate = client.post(
        f"{API}/accounts",
        json={
            "name": "salary-M",
            "account_type": "checking",
            "opening_balance": "0.00",
            "opening_date": "2026-11-01",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"

    blank = client.post(
        f"{API}/accounts",
        json={
            "name": "   ",
            "account_type": "checking",
            "opening_balance": "0.00",
            "opening_date": "2026-11-01",
        },
    )
    assert blank.status_code == 422

    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="100.00",
        description="History blocks deletion",
    )
    blocked = client.delete(f"{API}/accounts/{accounts['salary-M']}")
    assert blocked.status_code == 409
    assert "Deactivate" in blocked.json()["error"]["message"]

    deactivated = client.patch(
        f"{API}/accounts/{accounts['salary-M']}", json={"is_active": False}
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    visible = client.get(
        f"{API}/accounts", params={"start_date": "2026-11-01", "end_date": "2026-11-30"}
    ).json()
    salary = next(row for row in visible if row["name"] == "salary-M")
    assert salary["is_active"] is False


def test_categories_crud_and_deletion(client: TestClient) -> None:
    created = client.post(
        f"{API}/categories",
        json={
            "name": "Books",
            "category_type": "expense",
            "color": "#123456",
            "is_essential": True,
            "expense_nature": "variable",
            "sort_order": 5,
        },
    )
    assert created.status_code == 201, created.text
    category = created.json()
    assert category["parent_name"] is None
    assert category["transaction_count"] == 0

    updated = client.patch(
        f"{API}/categories/{category['id']}",
        json={"name": "Books & Media", "is_essential": False, "sort_order": 7},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Books & Media"
    assert updated.json()["is_essential"] is False
    assert updated.json()["sort_order"] == 7

    deleted = client.delete(f"{API}/categories/{category['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {
        "id": category["id"],
        "deactivated": False,
        "message": "Category deleted.",
    }
    names = {row["name"] for row in client.get(f"{API}/categories").json()}
    assert "Books & Media" not in names

    invalid_color = client.post(
        f"{API}/categories",
        json={"name": "Bad Color", "category_type": "expense", "color": "red"},
    )
    assert invalid_color.status_code == 422


def test_category_in_use_is_deactivated(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="250.00",
        description="Groceries",
    )
    response = client.delete(f"{API}/categories/{categories['Groceries']}")
    assert response.status_code == 200
    assert response.json()["deactivated"] is True

    active = client.get(f"{API}/categories").json()
    assert all(row["id"] != str(categories["Groceries"]) for row in active)

    all_categories = client.get(
        f"{API}/categories", params={"include_inactive": "true"}
    ).json()
    groceries = next(
        row for row in all_categories if row["id"] == str(categories["Groceries"])
    )
    assert groceries["is_active"] is False
    assert groceries["transaction_count"] == 1


def test_category_hierarchy_and_type_rules(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    income_parent = client.post(
        f"{API}/categories",
        json={"name": "Bonus Income", "category_type": "income"},
    ).json()
    mismatched_parent = client.post(
        f"{API}/categories",
        json={
            "name": "Expense Child",
            "category_type": "expense",
            "parent_category_id": income_parent["id"],
        },
    )
    assert mismatched_parent.status_code == 422

    parent = client.post(
        f"{API}/categories", json={"name": "Parent Expense", "category_type": "expense"}
    ).json()
    child = client.post(
        f"{API}/categories",
        json={
            "name": "Child Expense",
            "category_type": "expense",
            "parent_category_id": parent["id"],
        },
    ).json()

    self_parent = client.patch(
        f"{API}/categories/{parent['id']}", json={"parent_category_id": parent["id"]}
    )
    assert self_parent.status_code == 422

    cycle = client.patch(
        f"{API}/categories/{parent['id']}", json={"parent_category_id": child["id"]}
    )
    assert cycle.status_code == 422

    used = client.post(
        f"{API}/categories", json={"name": "Used Category", "category_type": "expense"}
    ).json()
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=used["id"],
        transaction_type="expense",
        amount="10.00",
        description="Uses category",
    )
    type_change = client.patch(
        f"{API}/categories/{used['id']}", json={"category_type": "income"}
    )
    assert type_change.status_code == 409
    assert type_change.json()["error"]["code"] == "conflict"


def test_optional_bearer_authentication(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "api_auth_token", "top-secret")

    missing = client.get(f"{API}/accounts")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"
    assert missing.headers["www-authenticate"] == "Bearer"

    wrong = client.get(
        f"{API}/accounts", headers={"Authorization": "Bearer wrong-token"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["message"] == "Invalid bearer token."

    accepted = client.get(
        f"{API}/accounts", headers={"Authorization": "Bearer top-secret"}
    )
    assert accepted.status_code == 200

    public_health = client.get("/health")
    assert public_health.status_code == 200


def test_error_envelopes(client: TestClient) -> None:
    missing = client.get(f"{API}/transactions/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {
            "code": "not_found",
            "message": "Transaction not found.",
            "details": None,
        }
    }

    unknown_route = client.get(f"{API}/does-not-exist")
    assert unknown_route.status_code == 404
    assert unknown_route.json()["error"]["code"] == "http_error"

    malformed = client.get(f"{API}/transactions/not-a-uuid")
    assert malformed.status_code == 422
    body = malformed.json()["error"]
    assert body["code"] == "validation_error"
    assert body["message"] == "Request validation failed."
    assert any("transaction_id" in detail["field"] for detail in body["details"])


def test_page_meta_contract(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    for index in range(3):
        make_transaction(
            account_id=accounts["salary-M"],
            category_id=categories["Salary"],
            amount=f"{100 + index}.00",
            description=f"Transaction {index}",
            transaction_date=f"2026-11-0{index + 1}",
        )

    first = client.get(f"{API}/transactions", params={"page": 1, "page_size": 2}).json()
    assert first["meta"] == {
        "page": 1,
        "page_size": 2,
        "total": 3,
        "total_pages": 2,
    }
    assert len(first["items"]) == 2

    second = client.get(f"{API}/transactions", params={"page": 2, "page_size": 2}).json()
    assert len(second["items"]) == 1

    bad_page = client.get(f"{API}/transactions", params={"page": 0})
    assert bad_page.status_code == 422
    bad_size = client.get(f"{API}/transactions", params={"page_size": 101})
    assert bad_size.status_code == 422
