from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import Money, ORMModel, PositiveMoney


def _first_of_month(value: date) -> date:
    return value.replace(day=1)


def _month_count(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


class CommitteeBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    monthly_amount: PositiveMoney
    start_month: date
    end_month: date
    prior_paid_installments: int = Field(default=0, ge=0)
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("start_month", "end_month")
    @classmethod
    def normalize_month(cls, value: date) -> date:
        return _first_of_month(value)

    @model_validator(mode="after")
    def validate_period(self) -> CommitteeBase:
        if self.end_month < self.start_month:
            raise ValueError("end_month must be on or after start_month")
        total = _month_count(self.start_month, self.end_month)
        if total > 600:
            raise ValueError("committee period cannot exceed 600 months")
        if self.prior_paid_installments > total:
            raise ValueError("prior_paid_installments cannot exceed the plan length")
        return self


class CommitteeCreate(CommitteeBase):
    pass


class CommitteeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    monthly_amount: PositiveMoney | None = None
    start_month: date | None = None
    end_month: date | None = None
    prior_paid_installments: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("start_month", "end_month")
    @classmethod
    def normalize_month(cls, value: date | None) -> date | None:
        return _first_of_month(value) if value is not None else None


class CommitteeScheduleItem(BaseModel):
    month: date
    installment_number: int
    amount: Money
    paid_amount: Money
    status: Literal["paid", "upcoming"]
    source: Literal["prior", "transaction"] | None = None
    is_current: bool = False


class CommitteeRead(ORMModel):
    id: uuid.UUID
    name: str
    monthly_amount: Money
    start_month: date
    end_month: date
    prior_paid_installments: int
    notes: str | None
    total_installments: int
    total_amount: Money
    paid_installments: int
    linked_paid_installments: int
    total_paid: Money
    remaining_installments: int
    remaining_amount: Money
    current_month: date
    progress_pct: float
    schedule: list[CommitteeScheduleItem] = []
    created_at: datetime
    updated_at: datetime
