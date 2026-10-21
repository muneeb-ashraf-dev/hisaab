from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import LedgerEntryKind, TransactionType
from app.schemas.common import Money, ORMModel, PositiveMoney


class TransactionBase(BaseModel):
    transaction_date: date
    transaction_type: TransactionType
    amount: PositiveMoney
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=255)
    merchant_or_payee: str | None = Field(default=None, max_length=160)
    payment_method: str | None = Field(default=None, max_length=60)
    notes: str | None = None
    related_transaction_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_type_fields(self) -> TransactionBase:
        if self.transaction_type in (TransactionType.INCOME, TransactionType.EXPENSE):
            if self.category_id is None:
                raise ValueError("category_id is required for income and expenses")
        if self.transaction_type in (
            TransactionType.ADJUSTMENT_INCREASE,
            TransactionType.ADJUSTMENT_DECREASE,
        ):
            if self.category_id is not None:
                raise ValueError("adjustments must not have a category")
        if self.transaction_type == TransactionType.REFUND and self.related_transaction_id is None:
            raise ValueError("refunds must reference the original expense")
        if (
            self.transaction_type != TransactionType.REFUND
            and self.related_transaction_id is not None
        ):
            raise ValueError("only refunds may reference another transaction")
        return self

    @model_validator(mode="after")
    def strip_text(self) -> TransactionBase:
        self.description = self.description.strip()
        if self.merchant_or_payee is not None:
            self.merchant_or_payee = self.merchant_or_payee.strip() or None
        if self.payment_method is not None:
            self.payment_method = self.payment_method.strip() or None
        return self


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    transaction_date: date | None = None
    transaction_type: TransactionType | None = None
    amount: PositiveMoney | None = None
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    merchant_or_payee: str | None = Field(default=None, max_length=160)
    payment_method: str | None = Field(default=None, max_length=60)
    notes: str | None = None
    related_transaction_id: uuid.UUID | None = None


class TransactionRead(ORMModel):
    id: uuid.UUID
    transaction_date: date
    transaction_type: TransactionType
    amount: Money
    account_id: uuid.UUID
    account_name: str | None = None
    category_id: uuid.UUID | None
    category_name: str | None = None
    category_color: str | None = None
    description: str
    merchant_or_payee: str | None
    payment_method: str | None
    notes: str | None
    related_transaction_id: uuid.UUID | None
    source: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    refunded_amount: Money | None = None
    net_amount: Money | None = None


class TransactionDetail(BaseModel):
    transaction: TransactionRead
    refunds: list[TransactionRead] = []
    original_transaction: TransactionRead | None = None
    refundable_remaining: Money = Decimal("0.00")


class TransferCreate(BaseModel):
    transfer_date: date
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: PositiveMoney
    description: str = Field(min_length=1, max_length=255)
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def accounts_must_differ(self) -> TransferCreate:
        if self.from_account_id == self.to_account_id:
            raise ValueError("source and destination accounts must differ")
        self.description = self.description.strip()
        return self


class TransferUpdate(BaseModel):
    transfer_date: date | None = None
    from_account_id: uuid.UUID | None = None
    to_account_id: uuid.UUID | None = None
    amount: PositiveMoney | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None

    @model_validator(mode="after")
    def accounts_must_differ(self) -> TransferUpdate:
        if (
            self.from_account_id is not None
            and self.to_account_id is not None
            and self.from_account_id == self.to_account_id
        ):
            raise ValueError("source and destination accounts must differ")
        return self


class TransferRead(ORMModel):
    id: uuid.UUID
    transfer_date: date
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    from_account_name: str | None = None
    to_account_name: str | None = None
    amount: Money
    description: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class LedgerEntry(BaseModel):
    id: uuid.UUID
    entry_kind: LedgerEntryKind
    entry_date: date
    amount: Money
    direction: str
    transaction_type: TransactionType | None = None
    description: str
    account_id: uuid.UUID | None = None
    account_name: str | None = None
    from_account_id: uuid.UUID | None = None
    from_account_name: str | None = None
    to_account_id: uuid.UUID | None = None
    to_account_name: str | None = None
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    category_color: str | None = None
    merchant_or_payee: str | None = None
    payment_method: str | None = None
    notes: str | None = None
    related_transaction_id: uuid.UUID | None = None
    created_at: datetime | None = None
