"""CSV import preview/commit and CSV exports."""

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from tests.helpers import API, NOV_END, NOV_START, csv_bytes, dec, parse_csv

EXPORT_HEADER = [
    "entry_kind",
    "date",
    "transaction_type",
    "amount",
    "account",
    "from_account",
    "to_account",
    "category",
    "description",
    "merchant_or_payee",
    "payment_method",
    "notes",
    "related_transaction_id",
]

VALID_ROWS = [
    {
        "transaction_date": "2026-11-02",
        "transaction_type": "income",
        "amount": "95000.00",
        "account": "salary-M",
        "category": "Salary",
        "description": "November salary",
        "merchant_or_payee": "Employer",
        "payment_method": "Bank transfer",
    },
    {
        "transaction_date": "2026-11-03",
        "transaction_type": "expense",
        "amount": "2450.50",
        "account": "salary-M",
        "category": "Groceries",
        "description": "Weekly groceries",
        "merchant_or_payee": "Metro Cash & Carry",
        "payment_method": "Debit card",
    },
]


def _upload(
    client: TestClient,
    content: bytes,
    *,
    filename: str = "transactions.csv",
    commit: bool = False,
    **form: str,
) -> object:
    endpoint = "imports/commit" if commit else "imports/preview"
    return client.post(
        f"{API}/{endpoint}",
        files={"file": (filename, content, "text/csv")},
        data=form,
    )


def test_sample_csv_download(client: TestClient) -> None:
    response = client.get(f"{API}/imports/sample.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="transactions-template.csv"'
    )
    lines = response.text.strip().splitlines()
    assert lines[0] == (
        "transaction_date,transaction_type,amount,account,category,description,"
        "merchant_or_payee,payment_method,notes"
    )
    assert len(lines) == 5


def test_preview_valid_csv(client: TestClient) -> None:
    content = csv_bytes(VALID_ROWS)
    response = _upload(client, content)
    assert response.status_code == 200, response.text
    preview = response.json()

    assert preview["filename"] == "transactions.csv"
    assert preview["total_rows"] == 2
    assert preview["valid_rows"] == 2
    assert preview["invalid_rows"] == 0
    assert preview["duplicate_rows"] == 0
    assert all(row["is_valid"] and not row["is_duplicate"] for row in preview["rows"])
    assert "transaction_date" in preview["detected_columns"]
    assert preview["expected_columns"][:5] == [
        "transaction_date",
        "transaction_type",
        "amount",
        "account",
        "category",
    ]
    assert preview["rows"][0]["row_number"] == 2
    assert preview["rows"][0]["normalized"]["account"] == "salary-M"


def test_preview_flags_duplicates_after_import(client: TestClient) -> None:
    content = csv_bytes(VALID_ROWS)
    committed = _upload(client, content, commit=True)
    assert committed.status_code == 200, committed.text
    assert committed.json()["created_count"] == 2

    preview = _upload(client, content)
    assert preview.status_code == 200
    data = preview.json()
    assert data["duplicate_rows"] == 2
    assert data["valid_rows"] == 0
    assert all(row["is_duplicate"] for row in data["rows"])
    assert all("existing transaction" in row["duplicate_reason"] for row in data["rows"])


def test_commit_is_idempotent_and_skips_duplicates(client: TestClient) -> None:
    content = csv_bytes(VALID_ROWS)
    first = _upload(client, content, commit=True)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["total_rows"] == 2
    assert result["created_count"] == 2
    assert result["skipped_count"] == 0
    assert result["rejected_count"] == 0
    assert result["errors"] == []
    assert client.get(f"{API}/transactions").json()["meta"]["total"] == 2

    # Omitting skip_duplicates must apply the documented default (true).
    second = _upload(client, content, commit=True)
    assert second.status_code == 200, second.text
    again = second.json()
    assert again["created_count"] == 0
    assert again["skipped_count"] == 2
    assert again["rejected_count"] == 0
    assert client.get(f"{API}/transactions").json()["meta"]["total"] == 2


def test_commit_can_report_duplicates_when_skipping_is_disabled(
    client: TestClient,
) -> None:
    content = csv_bytes(VALID_ROWS)
    assert _upload(client, content, commit=True).status_code == 200

    response = _upload(client, content, commit=True, skip_duplicates="false")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created_count"] == 0
    assert result["skipped_count"] == 0
    assert result["rejected_count"] == 2
    assert len(result["errors"]) == 2


def test_preview_flags_duplicate_rows_within_file(client: TestClient) -> None:
    duplicate = [VALID_ROWS[0], dict(VALID_ROWS[0])]
    preview = _upload(client, csv_bytes(duplicate)).json()
    assert preview["total_rows"] == 2
    assert preview["duplicate_rows"] == 1
    assert preview["valid_rows"] == 1
    assert preview["rows"][1]["is_duplicate"] is True
    assert "row 2" in preview["rows"][1]["duplicate_reason"]


def test_invalid_rows_are_reported_with_errors(client: TestClient) -> None:
    rows = [
        {
            "transaction_date": "not-a-date",
            "transaction_type": "income",
            "amount": "100.00",
            "account": "salary-M",
            "category": "Salary",
            "description": "Bad date",
        },
        {
            "transaction_date": "2026-11-02",
            "transaction_type": "expense",
            "amount": "100.00",
            "account": "unknown-account",
            "category": "Groceries",
            "description": "Bad account",
        },
        {
            "transaction_date": "2026-11-02",
            "transaction_type": "expense",
            "amount": "100.00",
            "account": "salary-M",
            "category": "Unknown Category",
            "description": "Bad category",
        },
        {
            "transaction_date": "2026-11-02",
            "transaction_type": "expense",
            "amount": "0.00",
            "account": "salary-M",
            "category": "Groceries",
            "description": "Zero amount",
        },
        {
            "transaction_date": "2026-11-02",
            "transaction_type": "adjustment_increase",
            "amount": "50.00",
            "account": "salary-M",
            "category": "Groceries",
            "description": "Adjustment with category",
        },
        {
            "transaction_date": "2026-11-02",
            "transaction_type": "expense",
            "amount": "50.00",
            "account": "salary-M",
            "category": "Groceries",
            "description": "",
        },
    ]
    response = _upload(client, csv_bytes(rows))
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["total_rows"] == 6
    assert preview["invalid_rows"] == 6
    assert preview["valid_rows"] == 0
    for row in preview["rows"]:
        assert row["errors"]
        assert row["is_valid"] is False

    commit = _upload(client, csv_bytes(rows), commit=True)
    assert commit.status_code == 200, commit.text
    result = commit.json()
    assert result["created_count"] == 0
    assert result["rejected_count"] == 6
    assert client.get(f"{API}/transactions").json()["meta"]["total"] == 0


def test_import_rejects_missing_required_columns(client: TestClient) -> None:
    response = _upload(client, b"transaction_date,amount\n2026-11-02,100.00\n")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "missing required columns" in body["error"]["message"].lower()


def test_import_creates_missing_categories_when_requested(client: TestClient) -> None:
    row = {
        "transaction_date": "2026-11-04",
        "transaction_type": "expense",
        "amount": "500.00",
        "account": "salary-M",
        "category": "Pet Care",
        "description": "Cat food",
    }
    content = csv_bytes([row])

    without_flag = _upload(client, content, commit=True)
    assert without_flag.status_code == 200, without_flag.text
    assert without_flag.json()["created_count"] == 0
    assert without_flag.json()["rejected_count"] == 1
    names = {category["name"] for category in client.get(f"{API}/categories").json()}
    assert "Pet Care" not in names

    with_flag = _upload(
        client, content, commit=True, create_missing_categories="true"
    )
    assert with_flag.status_code == 200, with_flag.text
    assert with_flag.json()["created_count"] == 1

    categories = client.get(f"{API}/categories").json()
    created = next(category for category in categories if category["name"] == "Pet Care")
    assert created["category_type"] == "expense"
    assert created["is_active"] is True


def test_export_transactions_csv(
    client: TestClient, accounts, categories, make_transaction, make_transfer
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="1000.00",
        description="Export salary",
        transaction_date="2026-11-05",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="200.00",
        description="Export groceries",
        transaction_date="2026-11-06",
    )
    make_transfer(
        from_account_id=accounts["salary-M"],
        to_account_id=accounts["savings"],
        amount="500.00",
        description="Export transfer",
        transfer_date="2026-11-07",
    )
    params = {"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()}

    response = client.get(f"{API}/exports/transactions.csv", params=params)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="transactions-export.csv"'
    )
    rows = parse_csv(response.text)
    assert list(rows[0].keys()) == EXPORT_HEADER
    assert len(rows) == 3
    kinds = {row["entry_kind"] for row in rows}
    assert kinds == {"transaction", "transfer"}
    transfer_row = next(row for row in rows if row["entry_kind"] == "transfer")
    assert transfer_row["from_account"] == "salary-M"
    assert transfer_row["to_account"] == "savings"
    assert transfer_row["amount"] == "500.00"
    salary_row = next(row for row in rows if row["description"] == "Export salary")
    assert salary_row["amount"] == "1000.00"
    assert salary_row["category"] == "Salary"

    without_transfers = client.get(
        f"{API}/exports/transactions.csv",
        params={**params, "include_transfers": "false"},
    )
    assert without_transfers.status_code == 200
    rows_without = parse_csv(without_transfers.text)
    assert len(rows_without) == 2
    assert all(row["entry_kind"] == "transaction" for row in rows_without)


def test_export_monthly_report_csv(
    client: TestClient, accounts, categories, make_transaction
) -> None:
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Salary"],
        amount="100000.00",
        description="Report salary",
        transaction_date="2026-11-02",
    )
    make_transaction(
        account_id=accounts["salary-M"],
        category_id=categories["Groceries"],
        transaction_type="expense",
        amount="4000.00",
        description="Report groceries",
        transaction_date="2026-11-03",
    )

    response = client.get(
        f"{API}/exports/monthly-report.csv",
        params={"start_date": NOV_START.isoformat(), "end_date": NOV_END.isoformat()},
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="monthly-report-2026-11.csv"'
    )
    assert response.headers["content-type"].startswith("text/csv")

    text = response.text
    assert "summary,Opening balance,132000.00" in text
    assert "summary,Income,100000.00" in text
    assert "summary,Net expenses,4000.00" in text
    assert "summary,Closing balance,228000.00" in text
    assert "category,Groceries,4000.00" in text

    parsed = list(csv.reader(io.StringIO(text)))
    assert parsed[0] == ["section", "label", "value"]
    assert dec(next(row[2] for row in parsed if row[:2] == ["summary", "Income"])) == dec(
        "100000.00"
    )
