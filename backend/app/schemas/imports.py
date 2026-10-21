from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import TransactionType


class ImportRowResult(BaseModel):
    row_number: int
    values: dict[str, str]
    normalized: dict[str, str | None] | None = None
    errors: list[str] = []
    is_duplicate: bool = False
    duplicate_reason: str | None = None
    is_valid: bool = False


class ImportPreview(BaseModel):
    filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    rows: list[ImportRowResult]
    detected_columns: list[str]
    expected_columns: list[str]


class ImportCommitResult(BaseModel):
    import_batch_id: str
    filename: str
    total_rows: int
    created_count: int
    skipped_count: int
    rejected_count: int
    errors: list[dict]


class SampleCsvRow(BaseModel):
    transaction_date: date
    transaction_type: TransactionType
    amount: Decimal
    account: str
    category: str | None
    description: str
    merchant_or_payee: str | None = None
    payment_method: str | None = None
    notes: str | None = None
