from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import GoalStatus
from app.schemas.common import Money, ORMModel, PositiveMoney


class GoalBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: PositiveMoney
    target_date: date | None = None
    status: GoalStatus = GoalStatus.ACTIVE
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class GoalCreate(GoalBase):
    pass


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    target_amount: PositiveMoney | None = None
    target_date: date | None = None
    status: GoalStatus | None = None
    notes: str | None = None


class ContributionCreate(BaseModel):
    amount: PositiveMoney
    contribution_date: date
    note: str | None = Field(default=None, max_length=255)


class ContributionRead(ORMModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    amount: Money
    contribution_date: date
    note: str | None
    created_at: datetime


class GoalRead(ORMModel):
    id: uuid.UUID
    name: str
    target_amount: Money
    current_amount: Money | None = None
    remaining_amount: Money | None = None
    progress_pct: float = 0
    target_date: date | None
    status: GoalStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    contributions: list[ContributionRead] = []
