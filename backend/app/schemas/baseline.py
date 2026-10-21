from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import Money, NonNegativeMoney, ORMModel


class BaselineUsageItemInput(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: NonNegativeMoney
    occurred_on: date | None = None
    notes: str | None = None


class BaselineUsageItemRead(ORMModel):
    id: uuid.UUID
    description: str
    amount: Money
    occurred_on: date | None
    notes: str | None


class BaselineAccountInput(BaseModel):
    account_id: uuid.UUID
    original_funds: NonNegativeMoney
    historical_usage: NonNegativeMoney
    opening_balance: NonNegativeMoney
    usage_items: list[BaselineUsageItemInput] = []

    @model_validator(mode="after")
    def reconciles(self) -> BaselineAccountInput:
        if self.original_funds != self.historical_usage + self.opening_balance:
            raise ValueError(
                "original_funds must equal historical_usage + opening_balance"
            )
        itemized = sum((item.amount for item in self.usage_items), Decimal("0"))
        if itemized > self.historical_usage:
            raise ValueError("itemized usage exceeds total historical usage")
        return self


class BaselineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    baseline_date: date | None = None
    notes: str | None = None
    accounts: list[BaselineAccountInput]


class BaselineAccountRead(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID
    account_name: str
    currency: str
    original_funds: Money
    historical_usage: Money
    opening_balance: Money
    itemized_usage: Money
    unclassified_usage: Money
    usage_items: list[BaselineUsageItemRead]


class BaselineRead(BaseModel):
    id: uuid.UUID
    name: str
    baseline_date: date
    notes: str
    total_original_funds: Money
    total_historical_usage: Money
    total_opening_balance: Money
    accounts: list[BaselineAccountRead]
    created_at: datetime
    updated_at: datetime
