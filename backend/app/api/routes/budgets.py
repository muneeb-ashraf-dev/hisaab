from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.budget import (
    BudgetCreate,
    BudgetProgress,
    BudgetRead,
    BudgetUpdate,
)
from app.schemas.common import Message
from app.services import budgets as budget_service

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetRead | BudgetProgress])
def list_budgets(
    db: DbSession,
    period_start: date | None = None,
    include_progress: bool = False,
) -> list[BudgetRead | BudgetProgress]:
    return budget_service.list_budgets(
        db, period_start=period_start, include_progress=include_progress
    )


@router.get("/progress", response_model=list[BudgetProgress])
def budget_progress(db: DbSession, period_start: date | None = None) -> list[BudgetProgress]:
    period = period_start or date.today().replace(day=1)
    return budget_service.budget_progress_for_period(db, period_start=period)


@router.post("", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
def create_budget(db: DbSession, payload: BudgetCreate) -> BudgetRead:
    budget = budget_service.create_budget(db, payload)
    return budget_service.serialize_budget(budget)


@router.patch("/{budget_id}", response_model=BudgetRead)
def update_budget(
    db: DbSession, budget_id: uuid.UUID, payload: BudgetUpdate
) -> BudgetRead:
    budget = budget_service.update_budget(db, budget_id, payload)
    return budget_service.serialize_budget(budget)


@router.delete("/{budget_id}", response_model=Message)
def delete_budget(db: DbSession, budget_id: uuid.UUID) -> Message:
    budget_service.delete_budget(db, budget_id)
    return Message(message="Budget deleted.")
