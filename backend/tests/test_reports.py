"""Monthly, annual, category, account and analytics reporting."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import API, NOV_END, NOV_START, dec


def _monthly(client: TestClient) -> dict:
    response = client.get(
        f"{API}/reports/monthly",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_monthly_report_income_expenses_net_and_savings_rate(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="100000.00",
        description="November salary",
        transaction_date="2026-11-02",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Rent"],
        transaction_type="expense",
        amount="40000.00",
        description="November rent",
        transaction_date="2026-11-03",
    )

    report = _monthly(client)
    assert report["start_date"] == "2026-11-01"
    assert report["end_date"] == "2026-11-30"
    assert report["label"] == "November 2026"
    assert report["is_partial_month"] is False
    assert dec(report["opening_balance"]) == Decimal("132000.00")
    assert dec(report["baseline_effect"]) == Decimal("0.00")
    assert dec(report["income"]) == Decimal("100000.00")
    assert dec(report["expenses_gross"]) == Decimal("40000.00")
    assert dec(report["refunds"]) == Decimal("0.00")
    assert dec(report["expenses_net"]) == Decimal("40000.00")
    assert dec(report["net_cash_flow"]) == Decimal("60000.00")
    assert report["savings_rate_pct"] == 60.0
    assert dec(report["closing_balance"]) == Decimal("192000.00")
    assert dec(report["reconciliation_difference"]) == Decimal("0.00")
    assert report["transaction_count"] == 2

    accounts_by_name = {row["account_name"]: row for row in report["accounts"]}
    salary = accounts_by_name["salary-M"]
    assert dec(salary["opening_balance"]) == Decimal("27000.00")
    assert dec(salary["closing_balance"]) == Decimal("87000.00")
    assert dec(accounts_by_name["savings"]["closing_balance"]) == Decimal("105000.00")

    assert len(report["categories"]) == 1
    rent = report["categories"][0]
    assert rent["name"] == "Rent"
    assert dec(rent["amount"]) == Decimal("40000.00")
    assert rent["percentage"] == 100.0


def test_refunds_reduce_net_expenses(
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
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="10000.00",
        description="Groceries",
        transaction_date="2026-11-03",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="refund",
        amount="3000.00",
        description="Grocery refund",
        related_transaction_id=expense["id"],
        transaction_date="2026-11-04",
    )

    report = _monthly(client)
    assert dec(report["expenses_gross"]) == Decimal("10000.00")
    assert dec(report["refunds"]) == Decimal("3000.00")
    assert dec(report["expenses_net"]) == Decimal("7000.00")
    assert dec(report["net_cash_flow"]) == Decimal("43000.00")
    assert dec(report["closing_balance"]) == Decimal("175000.00")
    assert report["transaction_count"] == 3
    assert dec(report["categories"][0]["amount"]) == Decimal("7000.00")


def test_reconciliation_with_transfers_and_adjustments(
    client: TestClient, accounts, categories, make_transaction, make_transfer
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="20000.00",
        description="Income",
        transaction_date="2026-11-02",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="6000.00",
        description="Expense",
        transaction_date="2026-11-03",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="adjustment_increase",
        amount="1000.00",
        description="Positive adjustment",
        transaction_date="2026-11-04",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="adjustment_decrease",
        amount="500.00",
        description="Negative adjustment",
        transaction_date="2026-11-05",
    )
    make_transfer(
        from_account_id=accounts["salary-M"],
        to_account_id=accounts["savings"],
        amount="3000.00",
        transfer_date="2026-11-06",
    )

    report = _monthly(client)
    assert dec(report["net_cash_flow"]) == Decimal("14000.00")
    assert dec(report["adjustments_increase"]) == Decimal("1000.00")
    assert dec(report["adjustments_decrease"]) == Decimal("500.00")
    assert dec(report["adjustments_net"]) == Decimal("500.00")
    assert dec(report["transfers_in"]) == Decimal("3000.00")
    assert dec(report["transfers_out"]) == Decimal("3000.00")

    expected_closing = (
        dec(report["opening_balance"])
        + dec(report["net_cash_flow"])
        + dec(report["adjustments_net"])
    )
    assert dec(report["closing_balance"]) == expected_closing
    assert expected_closing == Decimal("146500.00")
    assert dec(report["reconciliation_difference"]) == Decimal("0.00")


def test_annual_report_months_and_sums_match(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="100000.00",
        description="November salary",
        transaction_date="2026-11-02",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Rent"],
        transaction_type="expense",
        amount="40000.00",
        description="November rent",
        transaction_date="2026-11-03",
    )

    response = client.get(f"{API}/reports/annual", params={"year": 2026})
    assert response.status_code == 200, response.text
    report = response.json()

    assert report["year"] == 2026
    assert report["start_date"] == "2026-01-01"
    assert report["end_date"] == "2026-12-31"
    assert dec(report["opening_balance"]) == Decimal("0.00")
    assert dec(report["baseline_effect"]) == Decimal("132000.00")
    assert dec(report["income"]) == Decimal("100000.00")
    assert dec(report["expenses_net"]) == Decimal("40000.00")
    assert dec(report["net_cash_flow"]) == Decimal("60000.00")
    assert dec(report["closing_balance"]) == Decimal("192000.00")
    assert report["savings_rate_pct"] == 60.0
    assert report["transaction_count"] == 2
    assert report["year_over_year"] is None

    months = report["months"]
    assert len(months) == 12
    assert [point["month"] for point in months][0] == "2026-01"
    assert [point["month"] for point in months][-1] == "2026-12"
    assert sum((dec(point["income"]) for point in months), Decimal("0.00")) == Decimal(
        "100000.00"
    )
    assert sum((dec(point["net_expenses"]) for point in months), Decimal("0.00")) == Decimal(
        "40000.00"
    )
    november = next(point for point in months if point["month"] == "2026-11")
    assert dec(november["opening_balance"]) == Decimal("132000.00")
    assert dec(november["closing_balance"]) == Decimal("192000.00")
    assert dec(november["income"]) == Decimal("100000.00")
    assert report["highest_spending_month"]["month"] == "2026-11"
    assert dec(report["monthly_average_expenses"]) == Decimal("3333.33")

    accounts_by_name = {row["account_name"]: row for row in report["accounts"]}
    assert dec(accounts_by_name["salary-M"]["opening_balance"]) == Decimal("27000.00")
    assert dec(accounts_by_name["salary-M"]["closing_balance"]) == Decimal("87000.00")
    assert dec(accounts_by_name["savings"]["opening_balance"]) == Decimal("105000.00")
    assert dec(accounts_by_name["savings"]["closing_balance"]) == Decimal("105000.00")
    assert sum(
        (dec(row["closing_balance"]) for row in report["accounts"]), Decimal("0.00")
    ) == dec(report["closing_balance"])


def test_account_report_before_baseline_starts_from_opening_balance(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="10000.00",
        description="November income",
        transaction_date="2026-11-02",
    )

    response = client.get(
        f"{API}/reports/accounts/{accounts['salary-M']}",
        params={"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert dec(report["opening_balance"]) == Decimal("27000.00")
    assert dec(report["closing_balance"]) == Decimal("37000.00")
    assert dec(report["current_balance"]) == Decimal("37000.00")
    assert dec(report["opening_balance"]) + dec(report["net_movement"]) == dec(
        report["closing_balance"]
    )


def test_account_summaries_are_zero_before_the_account_opened(
    client: TestClient,
) -> None:
    response = client.get(
        f"{API}/reports/monthly",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    assert response.status_code == 200, response.text
    for row in response.json()["accounts"]:
        assert dec(row["opening_balance"]) == Decimal("0.00")
        assert dec(row["closing_balance"]) == Decimal("0.00")


def test_category_report_matches_monthly_and_compares_previous_period(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Rent"],
        transaction_type="expense",
        amount="8000.00",
        description="October rent",
        transaction_date="2026-10-10",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="5000.00",
        description="November groceries",
        transaction_date="2026-11-05",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Rent"],
        transaction_type="expense",
        amount="4000.00",
        description="November rent",
        transaction_date="2026-11-06",
    )

    response = client.get(
        f"{API}/reports/categories",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert dec(report["total_expenses_net"]) == Decimal("9000.00")
    assert report["previous_start"] == "2026-10-02"
    assert report["previous_end"] == "2026-10-31"
    assert dec(report["previous_total_expenses_net"]) == Decimal("8000.00")
    assert report["total_change_pct"] == 12.5

    by_name = {row["name"]: row for row in report["categories"]}
    assert set(by_name) == {"Groceries", "Rent"}
    assert dec(by_name["Groceries"]["amount"]) == Decimal("5000.00")
    assert by_name["Groceries"]["previous_amount"] is None or dec(
        by_name["Groceries"]["previous_amount"]
    ) == Decimal("0.00")
    assert by_name["Groceries"]["change_pct"] is None
    assert dec(by_name["Rent"]["previous_amount"]) == Decimal("8000.00")
    assert by_name["Rent"]["change_pct"] == -50.0

    assert len(report["monthly_trend"]) == 1
    trend = report["monthly_trend"][0]
    assert trend["month"] == "2026-11"
    assert dec(trend["total"]) == Decimal("9000.00")
    assert dec(trend["categories"][str(categories["Rent"])]) == Decimal("4000.00")

    monthly = _monthly(client)
    monthly_by_name = {row["name"]: dec(row["amount"]) for row in monthly["categories"]}
    assert monthly_by_name == {"Groceries": Decimal("5000.00"), "Rent": Decimal("4000.00")}
    assert sum(monthly_by_name.values(), Decimal("0.00")) == dec(monthly["expenses_net"])


def test_account_report_reconciles_opening_and_closing(
    client: TestClient, accounts, categories, make_transaction, make_transfer
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="10000.00",
        description="Income",
        transaction_date="2026-11-02",
    )
    expense = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="2000.00",
        description="Expense",
        transaction_date="2026-11-03",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        transaction_type="refund",
        amount="500.00",
        description="Refund",
        related_transaction_id=expense["id"],
        transaction_date="2026-11-04",
    )
    make_transfer(
        from_account_id=accounts["salary-M"],
        to_account_id=accounts["savings"],
        amount="3000.00",
        transfer_date="2026-11-05",
    )

    params = {"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()}
    response = client.get(
        f"{API}/reports/accounts/{accounts['salary-M']}", params=params
    )
    assert response.status_code == 200, response.text
    report = response.json()

    assert report["account_name"] == "salary-M"
    assert dec(report["opening_balance"]) == Decimal("27000.00")
    assert dec(report["income"]) == Decimal("10000.00")
    assert dec(report["expenses_gross"]) == Decimal("2000.00")
    assert dec(report["refunds"]) == Decimal("500.00")
    assert dec(report["expenses_net"]) == Decimal("1500.00")
    assert dec(report["transfers_out"]) == Decimal("3000.00")
    assert dec(report["transfers_in"]) == Decimal("0.00")
    assert dec(report["net_movement"]) == Decimal("5500.00")
    assert dec(report["closing_balance"]) == Decimal("32500.00")
    assert dec(report["current_balance"]) == Decimal("32500.00")
    assert dec(report["opening_balance"]) + dec(report["net_movement"]) == dec(
        report["closing_balance"]
    )
    assert len(report["history"]) == 4
    assert {row["entry_kind"] for row in report["history"]} == {"transaction", "transfer"}
    assert dec(report["categories"][0]["amount"]) == Decimal("1500.00")
    assert dec(report["income_sources"][0]["amount"]) == Decimal("10000.00")

    savings = client.get(f"{API}/reports/accounts/{accounts['savings']}", params=params).json()
    assert dec(savings["opening_balance"]) == Decimal("105000.00")
    assert dec(savings["closing_balance"]) == Decimal("108000.00")
    assert dec(savings["transfers_in"]) == Decimal("3000.00")
    assert dec(savings["transfers_out"]) == Decimal("0.00")


def test_analytics_savings_rate_essential_and_income_sources(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="100000.00",
        description="Salary",
        transaction_date="2026-11-02",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Rent"],
        transaction_type="expense",
        amount="30000.00",
        description="Rent",
        transaction_date="2026-11-03",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Transport"],
        transaction_type="expense",
        amount="10000.00",
        description="Transport",
        transaction_date="2026-11-04",
    )

    response = client.get(
        f"{API}/reports/analytics",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    )
    assert response.status_code == 200, response.text
    report = response.json()

    assert report["savings_rate_pct"] == 60.0
    assert dec(report["income"]) == Decimal("100000.00")
    assert dec(report["expenses_net"]) == Decimal("40000.00")
    assert dec(report["fixed_expenses"]) == Decimal("30000.00")
    assert dec(report["variable_expenses"]) == Decimal("10000.00")
    assert dec(report["essential_expenses"]) == Decimal("30000.00")
    assert dec(report["discretionary_expenses"]) == Decimal("10000.00")
    assert report["top_category_share_pct"] == 75.0
    assert len(report["category_concentration"]) == 2

    sources = report["income_sources"]
    assert len(sources) == 1
    assert sources[0]["name"] == "Salary"
    assert dec(sources[0]["amount"]) == Decimal("100000.00")
    assert sources[0]["percentage"] == 100.0
    assert sources[0]["transaction_count"] == 1

    assert report["large_expenses"] == []
    assert report["large_expense_threshold"] is None
    assert len(report["spending_trend"]) == 1


def test_report_invalid_ranges_are_rejected(client: TestClient) -> None:
    reversed_range = client.get(
        f"{API}/reports/monthly",
        params={"start_date": "2026-11-30", "end_date": "2026-11-01"},
    )
    assert reversed_range.status_code == 422
    assert reversed_range.json()["error"]["code"] == "validation_error"

    bad_month = client.get(f"{API}/reports/monthly", params={"year": 2026, "month": 13})
    assert bad_month.status_code == 422
    assert bad_month.json()["error"]["code"] == "validation_error"

    long_annual = client.get(
        f"{API}/reports/annual",
        params={"start_date": "2024-01-01", "end_date": "2026-01-01"},
    )
    assert long_annual.status_code == 422

    too_wide = client.get(
        f"{API}/reports/categories",
        params={"start_date": "2019-01-01", "end_date": "2026-01-01"},
    )
    assert too_wide.status_code == 422


def test_reports_exclude_soft_deleted_rows(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    expense = make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="5000.00",
        description="Deleted expense",
        transaction_date="2026-11-04",
    )
    assert client.delete(
        f"{API}/transactions/{expense['id']}", params={"reason": "Remove from reports"}
    ).status_code == 200

    report = _monthly(client)
    assert dec(report["income"]) == Decimal("0.00")
    assert dec(report["expenses_gross"]) == Decimal("0.00")
    assert dec(report["expenses_net"]) == Decimal("0.00")
    assert report["categories"] == []
    assert report["transaction_count"] == 0
    assert dec(report["closing_balance"]) == Decimal("132000.00")

    categories_report = client.get(
        f"{API}/reports/categories",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    ).json()
    assert dec(categories_report["total_expenses_net"]) == Decimal("0.00")

    analytics = client.get(
        f"{API}/reports/analytics",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    ).json()
    assert dec(analytics["expenses_net"]) == Decimal("0.00")

    account_report = client.get(
        f"{API}/reports/accounts/{accounts['salary-M']}",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    ).json()
    assert dec(account_report["expenses_net"]) == Decimal("0.00")
    assert dec(account_report["closing_balance"]) == Decimal("27000.00")
