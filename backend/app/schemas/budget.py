from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import BudgetPeriodType
from app.schemas.common import Money, ORMModel, PositiveMoney


class BudgetBase(BaseModel):
    category_id: uuid.UUID | None = None
    period_type: BudgetPeriodType = BudgetPeriodType.MONTHLY
    period_start: date
    amount: PositiveMoney
    warning_threshold: int = Field(default=80, ge=1, le=100)
    notes: str | None = None

    @field_validator("period_start")
    @classmethod
    def first_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("period_start must be the first day of the month")
        return value


class BudgetCreate(BudgetBase):
    pass


class BudgetUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    period_start: date | None = None
    amount: PositiveMoney | None = None
    warning_threshold: int | None = Field(default=None, ge=1, le=100)
    notes: str | None = None


class BudgetRead(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID | None
    category_name: str | None = None
    category_color: str | None = None
    period_type: BudgetPeriodType
    period_start: date
    amount: Money
    warning_threshold: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


class BudgetProgress(BaseModel):
    budget_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    amount: Money
    spent: Money
    remaining: Money
    utilization_pct: float
    warning_threshold: int
    status: str
    notes: str | None = None
