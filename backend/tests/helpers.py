"""Shared constants and small helpers for the API test-suite."""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

API = "/api/v1"

BASELINE_DATE = date(2026, 11, 1)
NOV_START = date(2026, 11, 1)
NOV_END = date(2026, 11, 30)
OCT_START = date(2026, 10, 1)
OCT_END = date(2026, 10, 31)

OPENING_TOTAL = Decimal("132000.00")

CSV_COLUMNS = [
    "transaction_date",
    "transaction_type",
    "amount",
    "account",
    "category",
    "description",
    "merchant_or_payee",
    "payment_method",
    "notes",
]


def dec(value: object) -> Decimal:
    """Convert an API decimal (string or number) to a 2dp Decimal."""
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(Decimal("0.01"))


def iso(value: date) -> str:
    return value.isoformat()


def date_range(start: date = NOV_START, end: date = NOV_END) -> dict[str, str]:
    return {"start_date": iso(start), "end_date": iso(end)}


def csv_bytes(rows: list[dict[str, str]], columns: list[str] | None = None) -> bytes:
    """Build a UTF-8 CSV with the expected import header."""
    fieldnames = columns or CSV_COLUMNS
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    return output.getvalue().encode("utf-8")


def parse_csv(content: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content)))
