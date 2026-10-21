from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.budget import Budget
from app.models.category import Category
from app.models.enums import AuditAction
from app.models.recurring import RecurringTemplate
from app.models.transaction import Transaction
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services.audit import diff_changes, record_audit


def get_category(db: Session, category_id: uuid.UUID) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Category not found.")
    return category


def list_categories(
    db: Session,
    *,
    include_inactive: bool = True,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[CategoryRead]:
    stmt = select(Category).order_by(Category.category_type, Category.sort_order, Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    categories = list(db.scalars(stmt))

    count_conditions = [Transaction.deleted_at.is_(None)]
    if start_date:
        count_conditions.append(Transaction.transaction_date >= start_date)
    if end_date:
        count_conditions.append(Transaction.transaction_date <= end_date)
    counts = dict(
        db.execute(
            select(Transaction.category_id, func.count())
            .where(*count_conditions)
            .group_by(Transaction.category_id)
        ).all()
    )
    parent_names = {category.id: category.name for category in categories}
    return [
        CategoryRead(
            **{
                key: getattr(category, key)
                for key in (
                    "id",
                    "name",
                    "category_type",
                    "parent_category_id",
                    "icon",
                    "color",
                    "is_active",
                    "is_essential",
                    "expense_nature",
                    "sort_order",
                    "notes",
                    "created_at",
                    "updated_at",
                )
            },
            parent_name=parent_names.get(category.parent_category_id),
            transaction_count=counts.get(category.id, 0),
        )
        for category in categories
    ]


def create_category(db: Session, payload: CategoryCreate) -> Category:
    _ensure_unique_name(db, payload.name)
    if payload.parent_category_id:
        parent = get_category(db, payload.parent_category_id)
        if parent.category_type != payload.category_type:
            raise ValidationError("Parent category must have the same category type.")
    category = Category(**payload.model_dump())
    db.add(category)
    db.flush()
    record_audit(
        db,
        entity_type="category",
        entity_id=category.id,
        action=AuditAction.CREATE,
        summary=f"Created category {category.name}",
        changes=payload.model_dump(),
    )
    db.commit()
    db.refresh(category)
    return category


def update_category(
    db: Session, category_id: uuid.UUID, payload: CategoryUpdate
) -> Category:
    category = get_category(db, category_id)
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] != category.name:
        _ensure_unique_name(db, updates["name"], exclude_id=category.id)
        updates["name"] = updates["name"].strip()

    new_type = updates.get("category_type", category.category_type)
    if new_type != category.category_type:
        used = db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.category_id == category.id)
        )
        if used:
            raise ConflictError(
                "Category type cannot change while transactions reference this category."
            )

    parent_id = updates.get("parent_category_id", category.parent_category_id)
    if parent_id == category.id:
        raise ValidationError("A category cannot be its own parent.")
    if parent_id is not None:
        parent = get_category(db, parent_id)
        if parent.category_type != new_type:
            raise ValidationError("Parent category must have the same category type.")
        if _creates_cycle(db, category.id, parent_id):
            raise ValidationError("Category hierarchy cannot contain a cycle.")

    before = {key: getattr(category, key) for key in updates}
    for key, value in updates.items():
        setattr(category, key, value)
    changes = diff_changes(before, {key: getattr(category, key) for key in updates})
    if changes:
        record_audit(
            db,
            entity_type="category",
            entity_id=category.id,
            action=AuditAction.UPDATE,
            summary=f"Updated category {category.name}",
            changes=changes,
        )
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: uuid.UUID) -> tuple[bool, str]:
    category = get_category(db, category_id)
    used = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.category_id == category_id)
    )
    budgeted = db.scalar(
        select(func.count()).select_from(Budget).where(Budget.category_id == category_id)
    )
    recurring = db.scalar(
        select(func.count())
        .select_from(RecurringTemplate)
        .where(RecurringTemplate.category_id == category_id)
    )
    children = db.scalar(
        select(func.count())
        .select_from(Category)
        .where(Category.parent_category_id == category_id)
    )
    if used or budgeted or recurring or children:
        category.is_active = False
        record_audit(
            db,
            entity_type="category",
            entity_id=category.id,
            action=AuditAction.UPDATE,
            summary=f"Deactivated category {category.name} (in use)",
        )
        db.commit()
        return True, "Category is in use, so it was deactivated instead of deleted."

    record_audit(
        db,
        entity_type="category",
        entity_id=category.id,
        action=AuditAction.DELETE,
        summary=f"Deleted category {category.name}",
    )
    db.delete(category)
    db.commit()
    return False, "Category deleted."


def _creates_cycle(db: Session, category_id: uuid.UUID, parent_id: uuid.UUID) -> bool:
    seen: set[uuid.UUID] = set()
    current: uuid.UUID | None = parent_id
    while current is not None:
        if current == category_id:
            return True
        if current in seen:
            return True
        seen.add(current)
        parent = db.get(Category, current)
        current = parent.parent_category_id if parent else None
    return False


def _ensure_unique_name(
    db: Session, name: str, *, exclude_id: uuid.UUID | None = None
) -> None:
    stmt = select(Category.id).where(func.lower(Category.name) == name.strip().lower())
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("A category with this name already exists.")
