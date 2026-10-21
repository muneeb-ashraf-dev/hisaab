"""Dashboard KPIs, cashflow series, category slices, recents and budgets."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import API, NOV_END, NOV_START, dec

NOV_PARAMS = {"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()}


def _dashboard(client: TestClient, params: dict[str, str] | None = None) -> dict:
    response = client.get(f"{API}/dashboard", params=params or NOV_PARAMS)
    assert response.status_code == 200, response.text
    return response.json()


def test_dashboard_kpis(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="50000.00",
        description="Salary",
        transaction_date="2026-11-02",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Rent"],
        transaction_type="expense",
        amount="20000.00",
        description="Rent",
        transaction_date="2026-11-03",
    )

    body = _dashboard(client)
    assert body["as_of"] == date.today().isoformat()
    assert body["period_start"] == "2026-11-01"
    assert body["period_end"] == "2026-11-30"
    assert body["month_start"] == date.today().replace(day=1).isoformat()

    assert dec(body["total_opening_balance"]) == Decimal("132000.00")
    assert dec(body["total_balance"]) == Decimal("162000.00")
    assert dec(body["projected_balance"]) == Decimal("162000.00")
    assert dec(body["savings_balance"]) == Decimal("105000.00")

    assert dec(body["period_income"]) == Decimal("50000.00")
    assert dec(body["period_expenses_gross"]) == Decimal("20000.00")
    assert dec(body["period_refunds"]) == Decimal("0.00")
    assert dec(body["period_expenses_net"]) == Decimal("20000.00")
    assert dec(body["period_net_cash_flow"]) == Decimal("30000.00")

    assert body["has_any_transactions"] is True
    assert body["days_remaining_in_month"] >= 1
    assert len(body["accounts"]) == 3


def test_dashboard_cashflow_points(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="50000.00",
        description="Salary",
        transaction_date="2026-11-02",
    )
    expense = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Rent"],
        transaction_type="expense",
        amount="20000.00",
        description="Rent",
        transaction_date="2026-11-03",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="refund",
        amount="5000.00",
        description="Refund",
        related_transaction_id=expense["id"],
        transaction_date="2026-11-04",
    )

    points = _dashboard(client)["cashflow"]
    assert len(points) == 30
    assert [point["month"] for point in points][:4] == [
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
        "2026-11-04",
    ]
    assert points[0]["label"] == "01 Nov"

    income_point = next(point for point in points if point["month"] == "2026-11-02")
    assert dec(income_point["income"]) == Decimal("50000.00")
    assert dec(income_point["net_cash_flow"]) == Decimal("50000.00")

    expense_point = next(point for point in points if point["month"] == "2026-11-03")
    assert dec(expense_point["expenses"]) == Decimal("20000.00")
    assert dec(expense_point["net_expenses"]) == Decimal("20000.00")
    assert dec(expense_point["net_cash_flow"]) == Decimal("-20000.00")

    refund_point = next(point for point in points if point["month"] == "2026-11-04")
    assert dec(refund_point["refunds"]) == Decimal("5000.00")
    assert dec(refund_point["net_expenses"]) == Decimal("-5000.00")
    assert dec(refund_point["net_cash_flow"]) == Decimal("5000.00")

    assert sum((dec(point["income"]) for point in points), Decimal("0.00")) == Decimal(
        "50000.00"
    )
    assert sum((dec(point["expenses"]) for point in points), Decimal("0.00")) == Decimal(
        "20000.00"
    )
    assert sum(
        (dec(point["net_expenses"]) for point in points), Decimal("0.00")
    ) == Decimal("15000.00")
    assert sum(
        (dec(point["net_cash_flow"]) for point in points), Decimal("0.00")
    ) == Decimal("35000.00")


def test_dashboard_expense_categories_and_recent_transactions(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="1000.00",
        description="Groceries",
        transaction_date="2026-11-09",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Rent"],
        transaction_type="expense",
        amount="4000.00",
        description="Rent",
        transaction_date="2026-11-10",
    )
    for day in range(1, 9):
        make_transaction(
            account_id=accounts["salary-M"],
            category_id=categories["Freelance"],
            amount="100.00",
            description=f"Freelance {day}",
            transaction_date=f"2026-11-0{day}",
        )

    body = _dashboard(client)
    slices = body["expense_categories"]
    assert len(slices) == 2
    assert sum((dec(item["amount"]) for item in slices), Decimal("0.00")) == Decimal(
        "5000.00"
    )
    by_name = {item["name"]: item for item in slices}
    assert dec(by_name["Rent"]["amount"]) == Decimal("4000.00")
    assert by_name["Rent"]["percentage"] == 80.0
    assert dec(by_name["Groceries"]["amount"]) == Decimal("1000.00")
    assert by_name["Groceries"]["percentage"] == 20.0
    assert all(item["amount"] != "0.00" for item in slices)

    recent = body["recent_transactions"]
    assert len(recent) == 8
    dates = [item["entry_date"] for item in recent]
    assert dates == sorted(dates, reverse=True)
    assert recent[0]["description"] == "Rent"
    assert recent[1]["description"] == "Groceries"


def test_dashboard_budget_progress(
    client: TestClient, categories
) -> None:
    current_month = date.today().replace(day=1).isoformat()
    overall = client.post(
        f"{API}/budgets",
        json={"period_start": current_month, "amount": "10000.00"},
    )
    assert overall.status_code == 201, overall.text
    category_budget = client.post(
        f"{API}/budgets",
        json={
            "category_id": str(categories["Groceries"]),
            "period_start": current_month,
            "amount": "5000.00",
            "warning_threshold": 75,
        },
    )
    assert category_budget.status_code == 201, category_budget.text

    body = _dashboard(client)
    budget = body["budget"]
    assert budget is not None
    assert budget["category_id"] is None
    assert budget["category_name"] == "Overall budget"
    assert dec(budget["amount"]) == Decimal("10000.00")
    assert dec(budget["spent"]) == Decimal("0.00")
    assert budget["status"] == "on_track"

    progress = body["budget_progress"]
    assert len(progress) == 2
    assert progress[0]["category_id"] is None
    groceries = next(
        row for row in progress if row["category_id"] == str(categories["Groceries"])
    )
    assert dec(groceries["remaining"]) == Decimal("5000.00")
    assert groceries["warning_threshold"] == 75


def test_dashboard_date_filters(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="7000.00",
        description="October groceries",
        transaction_date="2026-10-10",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="50000.00",
        description="November salary",
        transaction_date="2026-11-02",
    )

    october = _dashboard(
        client, {"start_date": "2026-10-01", "end_date": "2026-10-31"}
    )
    assert october["period_start"] == "2026-10-01"
    assert october["period_end"] == "2026-10-31"
    assert dec(october["period_income"]) == Decimal("0.00")
    assert dec(october["period_expenses_net"]) == Decimal("7000.00")
    assert dec(october["period_net_cash_flow"]) == Decimal("-7000.00")
    assert len(october["cashflow"]) == 31
    assert dec(october["total_balance"]) == Decimal("175000.00")

    november = _dashboard(client)
    assert dec(november["period_income"]) == Decimal("50000.00")
    assert dec(november["period_expenses_net"]) == Decimal("0.00")

    quarterly = _dashboard(
        client, {"start_date": "2026-09-01", "end_date": "2026-11-30"}
    )
    assert len(quarterly["cashflow"]) == 3
    assert [point["month"] for point in quarterly["cashflow"]] == [
        "2026-09",
        "2026-10",
        "2026-11",
    ]
    october_point = quarterly["cashflow"][1]
    november_point = quarterly["cashflow"][2]
    assert dec(october_point["expenses"]) == Decimal("7000.00")
    assert dec(november_point["income"]) == Decimal("50000.00")

    invalid = client.get(
        f"{API}/dashboard",
        params={"start_date": "2026-11-30", "end_date": "2026-11-01"},
    )
    assert invalid.status_code == 422


def test_dashboard_accounts_balances_and_recurring(
    client: TestClient, accounts, categories
) -> None:
    empty = _dashboard(client)
    assert empty["has_any_transactions"] is False
    assert empty["recent_transactions"] == []
    assert len(empty["accounts"]) == 3
    balances = {row["name"]: dec(row["balance"]) for row in empty["account_balances"]}
    assert balances == {
        "salary-M": Decimal("27000.00"),
        "salary-A": Decimal("0.00"),
        "savings": Decimal("105000.00"),
    }
    assert dec(empty["total_balance"]) == Decimal("132000.00")

    today = date.today()
    template = client.post(
        f"{API}/recurring",
        json={
            "name": "Upcoming on dashboard",
            "transaction_type": "expense",
            "amount": "300.00",
            "account_id": str(accounts["salary-M"]),
            "category_id": str(categories["Groceries"]),
            "description": "Upcoming bill",
            "frequency": "monthly",
            "start_date": today.isoformat(),
            "next_due_date": (today + timedelta(days=4)).isoformat(),
        },
    )
    assert template.status_code == 201, template.text

    with_upcoming = _dashboard(client)
    assert len(with_upcoming["upcoming_recurring"]) == 1
    assert with_upcoming["upcoming_recurring"][0]["template_id"] == template.json()["id"]
    assert with_upcoming["upcoming_recurring"][0]["is_overdue"] is False

    account_rows = {row["name"]: row for row in with_upcoming["accounts"]}
    assert dec(account_rows["salary-M"]["current_balance"]) == Decimal("27000.00")
    assert dec(account_rows["salary-M"]["opening_balance"]) == Decimal("27000.00")
    assert account_rows["salary-M"]["recent_activity"] == []
