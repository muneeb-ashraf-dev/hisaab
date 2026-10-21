from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CategoryType, ExpenseNature
from app.schemas.common import ORMModel


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category_type: CategoryType
    parent_category_id: uuid.UUID | None = None
    icon: str = Field(default="Circle", max_length=50)
    color: str = Field(default="#6366F1", pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: bool = True
    is_essential: bool = True
    expense_nature: ExpenseNature = ExpenseNature.VARIABLE
    sort_order: int = 0
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    category_type: CategoryType | None = None
    parent_category_id: uuid.UUID | None = None
    icon: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: bool | None = None
    is_essential: bool | None = None
    expense_nature: ExpenseNature | None = None
    sort_order: int | None = None
    notes: str | None = None


class CategoryRead(ORMModel):
    id: uuid.UUID
    name: str
    category_type: CategoryType
    parent_category_id: uuid.UUID | None
    parent_name: str | None = None
    icon: str
    color: str
    is_active: bool
    is_essential: bool
    expense_nature: ExpenseNature
    sort_order: int
    notes: str | None
    created_at: datetime
    updated_at: datetime
    transaction_count: int = 0


class CategoryDeleteResult(BaseModel):
    id: uuid.UUID
    deactivated: bool
    message: str
