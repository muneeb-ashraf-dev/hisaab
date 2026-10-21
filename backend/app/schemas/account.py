from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AccountType
from app.schemas.common import Money, NonNegativeMoney, ORMModel


class AccountBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    account_type: AccountType = AccountType.CHECKING
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    opening_balance: NonNegativeMoney = Decimal("0")
    opening_date: date
    is_active: bool = True
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        value = value.upper()
        if not value.isalpha():
            raise ValueError("currency must be a 3-letter ISO code")
        return value


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    account_type: AccountType | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    opening_balance: NonNegativeMoney | None = None
    opening_date: date | None = None
    is_active: bool | None = None
    notes: str | None = None


class AccountRead(ORMModel):
    id: uuid.UUID
    name: str
    account_type: AccountType
    currency: str
    opening_balance: NonNegativeMoney
    opening_date: date
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AccountWithBalance(AccountRead):
    current_balance: Money
    projected_balance: Money
    period_income: NonNegativeMoney
    period_expenses: NonNegativeMoney
    recent_activity: list[AccountActivity] = []


class AccountActivity(BaseModel):
    id: uuid.UUID
    entry_kind: str
    entry_date: date
    description: str
    amount: NonNegativeMoney
    direction: str
    category_name: str | None = None
    counterparty_account: str | None = None


AccountWithBalance.model_rebuild()
