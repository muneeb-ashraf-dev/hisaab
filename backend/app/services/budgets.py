from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.budget import Budget
from app.models.category import Category
from app.models.enums import AuditAction, CategoryType, TransactionType
from app.models.transaction import Transaction
from app.schemas.budget import BudgetCreate, BudgetProgress, BudgetRead, BudgetUpdate
from app.services.audit import diff_changes, record_audit

ZERO = Decimal("0.00")


def get_budget(db: Session, budget_id: uuid.UUID) -> Budget:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise NotFoundError("Budget not found.")
    return budget


def month_bounds(period_start: date) -> tuple[date, date]:
    if period_start.month == 12:
        next_month = date(period_start.year + 1, 1, 1)
    else:
        next_month = date(period_start.year, period_start.month + 1, 1)
    return period_start, date.fromordinal(next_month.toordinal() - 1)


def spending_by_category(
    db: Session, *, start_date: date, end_date: date
) -> dict[uuid.UUID | None, Decimal]:
    """Net expense per category (gross expenses minus linked refunds)."""
    stmt = select(
        Transaction.category_id,
        Transaction.transaction_type,
        func.coalesce(func.sum(Transaction.amount), ZERO),
    ).where(
        Transaction.deleted_at.is_(None),
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date,
        Transaction.transaction_type.in_(
            [TransactionType.EXPENSE, TransactionType.REFUND]
        ),
    )
    stmt = stmt.group_by(Transaction.category_id, Transaction.transaction_type)
    totals: dict[uuid.UUID | None, Decimal] = {}
    for category_id, txn_type, amount in db.execute(stmt):
        signed = (
            Decimal(amount or 0)
            if txn_type == TransactionType.EXPENSE
            else -Decimal(amount or 0)
        )
        totals[category_id] = totals.get(category_id, ZERO) + signed
    return {key: value.quantize(Decimal("0.01")) for key, value in totals.items()}


def list_budgets(
    db: Session,
    *,
    period_start: date | None = None,
    include_progress: bool = True,
) -> list[BudgetRead | BudgetProgress]:
    stmt = select(Budget).order_by(Budget.period_start.desc(), Budget.category_id.nullsfirst())
    if period_start is not None:
        stmt = stmt.where(Budget.period_start == period_start)
    budgets = list(db.scalars(stmt))
    if not include_progress:
        return [serialize_budget(budget) for budget in budgets]
    return [_progress_for(db, budget) for budget in budgets]


def budget_progress_for_period(
    db: Session, *, period_start: date
) -> list[BudgetProgress]:
    budgets = list(
        db.scalars(
            select(Budget)
            .where(Budget.period_start == period_start)
            .order_by(Budget.category_id.nullsfirst())
        )
    )
    return [_progress_for(db, budget) for budget in budgets]


def overall_budget_progress(
    db: Session, *, period_start: date
) -> BudgetProgress | None:
    budget = db.scalar(
        select(Budget).where(
            Budget.period_start == period_start, Budget.category_id.is_(None)
        )
    )
    if budget is None:
        return None
    return _progress_for(db, budget)


def _progress_for(db: Session, budget: Budget) -> BudgetProgress:
    start_date, end_date = month_bounds(budget.period_start)
    totals = spending_by_category(db, start_date=start_date, end_date=end_date)
    if budget.category_id is None:
        spent = sum(totals.values(), ZERO).quantize(Decimal("0.01"))
    else:
        spent = totals.get(budget.category_id, ZERO)
    spent = max(spent, ZERO)
    remaining = (budget.amount - spent).quantize(Decimal("0.01"))
    utilization = (
        float((spent / budget.amount * 100).quantize(Decimal("0.1"))) if budget.amount else 0.0
    )
    if utilization > 100:
        status = "over"
    elif utilization >= budget.warning_threshold:
        status = "warning"
    else:
        status = "on_track"
    return BudgetProgress(
        budget_id=budget.id,
        category_id=budget.category_id,
        category_name=budget.category.name if budget.category else "Overall budget",
        amount=budget.amount,
        spent=spent,
        remaining=remaining,
        utilization_pct=utilization,
        warning_threshold=budget.warning_threshold,
        status=status,
        notes=budget.notes,
    )


def serialize_budget(budget: Budget) -> BudgetRead:
    return BudgetRead(
        id=budget.id,
        category_id=budget.category_id,
        category_name=budget.category.name if budget.category else "Overall budget",
        category_color=budget.category.color if budget.category else "#6366F1",
        period_type=budget.period_type,
        period_start=budget.period_start,
        amount=budget.amount,
        warning_threshold=budget.warning_threshold,
        notes=budget.notes,
        created_at=budget.created_at,
        updated_at=budget.updated_at,
    )


def create_budget(db: Session, payload: BudgetCreate) -> Budget:
    _validate_category(db, payload.category_id)
    budget = Budget(**payload.model_dump())
    db.add(budget)
    db.flush()
    record_audit(
        db,
        entity_type="budget",
        entity_id=budget.id,
        action=AuditAction.CREATE,
        summary=f"Created budget for {budget.period_start:%B %Y}",
        changes=payload.model_dump(),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "A budget for this category and month already exists. Edit the existing budget."
        ) from exc
    db.refresh(budget)
    return budget


def update_budget(db: Session, budget_id: uuid.UUID, payload: BudgetUpdate) -> Budget:
    budget = get_budget(db, budget_id)
    updates = payload.model_dump(exclude_unset=True)
    if "period_start" in updates and updates["period_start"].day != 1:
        raise ValidationError("period_start must be the first day of the month.")
    if "category_id" in updates:
        _validate_category(db, updates["category_id"])
    before = {key: getattr(budget, key) for key in updates}
    for key, value in updates.items():
        setattr(budget, key, value)
    changes = diff_changes(before, {key: getattr(budget, key) for key in updates})
    if changes:
        record_audit(
            db,
            entity_type="budget",
            entity_id=budget.id,
            action=AuditAction.UPDATE,
            summary="Updated budget",
            changes=changes,
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "A budget for this category and month already exists."
        ) from exc
    db.refresh(budget)
    return budget


def delete_budget(db: Session, budget_id: uuid.UUID) -> None:
    budget = get_budget(db, budget_id)
    record_audit(
        db,
        entity_type="budget",
        entity_id=budget.id,
        action=AuditAction.DELETE,
        summary="Deleted budget",
        changes={"amount": budget.amount, "period_start": budget.period_start},
    )
    db.delete(budget)
    db.commit()


def _validate_category(db: Session, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    category = db.get(Category, category_id)
    if category is None:
        raise ValidationError("Category not found.")
    if category.category_type != CategoryType.EXPENSE:
        raise ValidationError("Budgets can only target expense categories.")


def budget_adherence(db: Session, *, start_date: date, end_date: date) -> float | None:
    """Percentage of period budget used, or None when no budget covers the period."""
    period_start = start_date.replace(day=1)
    budget = db.scalar(
        select(Budget).where(Budget.period_start == period_start, Budget.category_id.is_(None))
    )
    if budget is None:
        return None
    spent = overall_budget_progress(db, period_start=period_start)
    if spent is None:
        return None
    return spent.utilization_pct
