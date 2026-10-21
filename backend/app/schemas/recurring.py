from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import RecurringFrequency, TransactionType
from app.schemas.common import Money, ORMModel, PositiveMoney


class RecurringBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    transaction_type: TransactionType
    amount: PositiveMoney
    account_id: uuid.UUID
    category_id: uuid.UUID
    description: str = Field(min_length=1, max_length=255)
    merchant_or_payee: str | None = Field(default=None, max_length=160)
    payment_method: str | None = Field(default=None, max_length=60)
    notes: str | None = None
    frequency: RecurringFrequency = RecurringFrequency.MONTHLY
    interval_count: int = Field(default=1, ge=1, le=12)
    start_date: date
    next_due_date: date
    end_date: date | None = None
    is_active: bool = True
    auto_post: bool = False

    @model_validator(mode="after")
    def valid_type_and_dates(self) -> RecurringBase:
        if self.transaction_type not in (TransactionType.INCOME, TransactionType.EXPENSE):
            raise ValueError("recurring templates must be income or expense")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.next_due_date < self.start_date:
            raise ValueError("next_due_date must be on or after start_date")
        return self


class RecurringCreate(RecurringBase):
    pass


class RecurringUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    transaction_type: TransactionType | None = None
    amount: PositiveMoney | None = None
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    merchant_or_payee: str | None = Field(default=None, max_length=160)
    payment_method: str | None = Field(default=None, max_length=60)
    notes: str | None = None
    frequency: RecurringFrequency | None = None
    interval_count: int | None = Field(default=None, ge=1, le=12)
    start_date: date | None = None
    next_due_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None
    auto_post: bool | None = None


class RecurringRead(ORMModel):
    id: uuid.UUID
    name: str
    transaction_type: TransactionType
    amount: Money
    account_id: uuid.UUID
    account_name: str | None = None
    category_id: uuid.UUID
    category_name: str | None = None
    category_color: str | None = None
    description: str
    merchant_or_payee: str | None
    payment_method: str | None
    notes: str | None
    frequency: RecurringFrequency
    interval_count: int
    start_date: date
    next_due_date: date
    end_date: date | None
    is_active: bool
    auto_post: bool
    created_at: datetime
    updated_at: datetime
    days_until_due: int | None = None


class UpcomingRecurring(BaseModel):
    template_id: uuid.UUID
    name: str
    description: str
    amount: Money
    transaction_type: TransactionType
    due_date: date
    account_id: uuid.UUID
    account_name: str
    category_name: str | None = None
    is_overdue: bool
    occurrence_status: str


class PostDueResult(BaseModel):
    created_count: int
    skipped_count: int
    transactions: list[uuid.UUID]
    message: str


class OccurrenceRead(ORMModel):
    id: uuid.UUID
    template_id: uuid.UUID
    due_date: date
    status: str
    transaction_id: uuid.UUID | None
    created_at: datetime
