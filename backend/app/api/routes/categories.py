from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession
from app.schemas.category import (
    CategoryCreate,
    CategoryDeleteResult,
    CategoryRead,
    CategoryUpdate,
)
from app.services import categories as category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
def list_categories(
    db: DbSession,
    include_inactive: bool = Query(False),
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[CategoryRead]:
    return category_service.list_categories(
        db,
        include_inactive=include_inactive,
        start_date=start_date,
        end_date=end_date,
    )


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(db: DbSession, payload: CategoryCreate) -> CategoryRead:
    category = category_service.create_category(db, payload)
    return CategoryRead.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    db: DbSession, category_id: uuid.UUID, payload: CategoryUpdate
) -> CategoryRead:
    category = category_service.update_category(db, category_id, payload)
    return CategoryRead.model_validate(category)


@router.delete("/{category_id}", response_model=CategoryDeleteResult)
def delete_category(db: DbSession, category_id: uuid.UUID) -> CategoryDeleteResult:
    deactivated, message = category_service.delete_category(db, category_id)
    return CategoryDeleteResult(
        id=category_id, deactivated=deactivated, message=message
    )
