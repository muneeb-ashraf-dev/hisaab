from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.account import Account
from app.models.category import Category
from app.models.committee import Committee
from app.models.enums import AuditAction, CategoryType, LedgerEntryKind, TransactionType
from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionCreate,
    TransactionRead,
    TransactionUpdate,
)
from app.services.audit import diff_changes, record_audit

ZERO = Decimal("0.00")
EDITABLE_FIELDS = (
    "transaction_date",
    "transaction_type",
    "amount",
    "account_id",
    "category_id",
    "committee_id",
    "description",
    "merchant_or_payee",
    "payment_method",
    "notes",
    "related_transaction_id",
)


def get_transaction(db: Session, transaction_id: uuid.UUID) -> Transaction:
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise NotFoundError("Transaction not found.")
    return txn


def refunded_amounts(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    if not ids:
        return {}
    stmt = (
        select(Transaction.related_transaction_id, func.sum(Transaction.amount))
        .where(
            Transaction.related_transaction_id.in_(ids),
            Transaction.transaction_type == TransactionType.REFUND,
            Transaction.deleted_at.is_(None),
        )
        .group_by(Transaction.related_transaction_id)
    )
    return {
        related_id: Decimal(total or 0).quantize(Decimal("0.01"))
        for related_id, total in db.execute(stmt)
        if related_id is not None
    }


def serialize_transaction(txn: Transaction, refunded: Decimal | None = None) -> TransactionRead:
    refunded = (refunded or ZERO).quantize(Decimal("0.01"))
    net_amount = txn.amount
    if txn.transaction_type == TransactionType.EXPENSE:
        net_amount = (txn.amount - refunded).quantize(Decimal("0.01"))
    return TransactionRead(
        id=txn.id,
        transaction_date=txn.transaction_date,
        transaction_type=txn.transaction_type,
        amount=txn.amount,
        account_id=txn.account_id,
        account_name=txn.account.name if txn.account else None,
        category_id=txn.category_id,
        category_name=txn.category.name if txn.category else None,
        category_color=txn.category.color if txn.category else None,
        committee_id=txn.committee_id,
        committee_name=txn.committee.name if txn.committee else None,
        description=txn.description,
        merchant_or_payee=txn.merchant_or_payee,
        payment_method=txn.payment_method,
        notes=txn.notes,
        related_transaction_id=txn.related_transaction_id,
        source=txn.source,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
        deleted_at=txn.deleted_at,
        refunded_amount=refunded if txn.transaction_type == TransactionType.EXPENSE else None,
        net_amount=net_amount,
    )


def create_transaction(
    db: Session, payload: TransactionCreate, *, source: str = "manual", commit: bool = True
) -> Transaction:
    if payload.idempotency_key:
        existing = db.scalar(
            select(Transaction).where(Transaction.idempotency_key == payload.idempotency_key)
        )
        if existing is not None:
            return existing

    _validate_references(db, payload)
    _validate_refund(db, payload)
    data = payload.model_dump()
    data["amount"] = _money(data["amount"])
    data["description"] = data["description"].strip()
    if data["transaction_type"] == TransactionType.REFUND and data["category_id"] is None:
        original = db.get(Transaction, data["related_transaction_id"])
        if original is not None:
            data["category_id"] = original.category_id
    txn = Transaction(**data, source=source)
    db.add(txn)
    db.flush()
    record_audit(
        db,
        entity_type="transaction",
        entity_id=txn.id,
        action=AuditAction.CREATE,
        summary=f"Recorded {txn.transaction_type.value} of {txn.amount}",
        changes={key: getattr(txn, key) for key in EDITABLE_FIELDS},
    )
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            if payload.idempotency_key:
                existing = db.scalar(
                    select(Transaction).where(
                        Transaction.idempotency_key == payload.idempotency_key
                    )
                )
                if existing is not None:
                    return existing
            raise
        db.refresh(txn)
    return txn


def update_transaction(
    db: Session, transaction_id: uuid.UUID, payload: TransactionUpdate
) -> Transaction:
    txn = get_transaction(db, transaction_id)
    if txn.deleted_at is not None:
        raise ConflictError("Deleted transactions cannot be edited. Restore it first.")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return txn

    merged = {key: getattr(txn, key) for key in EDITABLE_FIELDS}
    merged.update(updates)
    if "amount" in merged:
        merged["amount"] = _money(merged["amount"])
    if merged.get("description"):
        merged["description"] = str(merged["description"]).strip()

    refunds_total = _active_refund_total(db, txn.id)
    if (
        txn.transaction_type == TransactionType.EXPENSE
        and merged["transaction_type"] != TransactionType.EXPENSE
        and refunds_total > ZERO
    ):
        raise ConflictError("An expense with refunds cannot change type. Remove refunds first.")
    if (
        txn.transaction_type == TransactionType.EXPENSE
        and Decimal(merged["amount"]) < refunds_total
    ):
        raise ValidationError(
            f"Expense amount cannot be lower than its refunded total ({refunds_total})."
        )

    validate_merged(db, merged, txn_id=txn.id)
    if merged["transaction_type"] == TransactionType.REFUND:
        _validate_refund_link(
            db,
            refund_id=txn.id,
            related_id=merged.get("related_transaction_id"),
            amount=Decimal(merged["amount"]),
            refund_date=merged["transaction_date"],
        )
        if merged.get("category_id") is None and merged.get("related_transaction_id"):
            original = db.get(Transaction, merged["related_transaction_id"])
            if original is not None:
                merged["category_id"] = original.category_id
                updates["category_id"] = original.category_id

    before = {key: getattr(txn, key) for key in updates}
    for key, value in updates.items():
        setattr(txn, key, value)
    txn.updated_at = datetime.now(UTC)
    changes = diff_changes(before, {key: getattr(txn, key) for key in updates})
    if changes:
        record_audit(
            db,
            entity_type="transaction",
            entity_id=txn.id,
            action=AuditAction.UPDATE,
            summary=f"Updated {txn.transaction_type.value} transaction",
            changes=changes,
        )
    db.commit()
    db.refresh(txn)
    return txn


def validate_merged(
    db: Session,
    merged: dict,
    *,
    txn_id: uuid.UUID | None = None,
) -> None:
    txn_type = merged["transaction_type"]
    category_id = merged.get("category_id")
    account_id = merged.get("account_id")
    amount = merged.get("amount")
    if amount is None or Decimal(amount) <= 0:
        raise ValidationError("Amount must be greater than zero.")

    account = db.get(Account, account_id) if account_id else None
    if account is None:
        raise ValidationError("Account not found.")
    if not account.is_active and txn_id is None:
        raise ValidationError("Cannot post transactions to an inactive account.")

    category = db.get(Category, category_id) if category_id else None

    if txn_type in (TransactionType.INCOME, TransactionType.EXPENSE):
        if category is None:
            raise ValidationError("A category is required for income and expenses.")
        expected = (
            CategoryType.INCOME
            if txn_type == TransactionType.INCOME
            else CategoryType.EXPENSE
        )
        if category.category_type != expected:
            raise ValidationError(
                f"Selected category is not an {expected.value} category."
            )
    elif txn_type in (
        TransactionType.ADJUSTMENT_INCREASE,
        TransactionType.ADJUSTMENT_DECREASE,
    ):
        if category_id is not None:
            raise ValidationError("Adjustments cannot have a category.")
    elif txn_type == TransactionType.REFUND:
        if merged.get("related_transaction_id") is None:
            raise ValidationError("Refunds must reference the original expense.")
        if category is not None and category.category_type != CategoryType.EXPENSE:
            raise ValidationError("A refund category must be an expense category.")

    committee_id = merged.get("committee_id")
    if committee_id is not None:
        if txn_type != TransactionType.EXPENSE:
            raise ValidationError("Only expenses can be linked to a committee.")
        committee = db.get(Committee, committee_id)
        if committee is None:
            raise ValidationError("Committee not found.")
        transaction_date = merged.get("transaction_date")
        if (
            transaction_date is None
            or transaction_date < committee.start_month
            or transaction_date > committee.end_month
        ):
            raise ValidationError(
                "The transaction date must be within the committee plan period "
                f"({committee.start_month:%b %Y} to {committee.end_month:%b %Y})."
            )


def _validate_references(db: Session, payload: TransactionCreate) -> None:
    validate_merged(db, payload.model_dump())


def _validate_refund(db: Session, payload: TransactionCreate) -> None:
    if payload.transaction_type != TransactionType.REFUND:
        return
    _validate_refund_link(
        db,
        refund_id=None,
        related_id=payload.related_transaction_id,
        amount=_money(payload.amount),
        refund_date=payload.transaction_date,
    )


def _validate_refund_link(
    db: Session,
    *,
    refund_id: uuid.UUID | None,
    related_id: uuid.UUID | None,
    amount: Decimal,
    refund_date: date,
) -> None:
    if related_id is None:
        raise ValidationError("Refunds must reference the original expense.")
    original = db.get(Transaction, related_id)
    if original is None or original.deleted_at is not None:
        raise NotFoundError("Original expense not found.")
    if original.transaction_type != TransactionType.EXPENSE:
        raise ValidationError("Refunds can only be linked to an expense.")
    if refund_date < original.transaction_date:
        raise ValidationError("Refund date cannot be before the original expense date.")
    already = _active_refund_total(db, original.id, exclude_id=refund_id)
    if already + amount > original.amount:
        raise ValidationError(
            f"Refund exceeds the original expense. Remaining refundable amount is "
            f"{_money(original.amount - already)}."
        )


def _active_refund_total(
    db: Session, expense_id: uuid.UUID, *, exclude_id: uuid.UUID | None = None
) -> Decimal:
    stmt = select(func.coalesce(func.sum(Transaction.amount), ZERO)).where(
        Transaction.related_transaction_id == expense_id,
        Transaction.transaction_type == TransactionType.REFUND,
        Transaction.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(Transaction.id != exclude_id)
    return _money(db.scalar(stmt) or ZERO)


def delete_transaction(db: Session, transaction_id: uuid.UUID, *, reason: str) -> None:
    txn = get_transaction(db, transaction_id)
    if txn.deleted_at is not None:
        raise ConflictError("Transaction is already deleted.")
    if txn.transaction_type == TransactionType.EXPENSE:
        refunds = _active_refund_total(db, txn.id)
        if refunds > ZERO:
            raise ConflictError(
                "This expense has linked refunds. Delete the refunds before deleting the expense."
            )
    txn.deleted_at = datetime.now(UTC)
    txn.deleted_reason = reason.strip() or "Deleted by user"
    record_audit(
        db,
        entity_type="transaction",
        entity_id=txn.id,
        action=AuditAction.DELETE,
        summary=f"Deleted {txn.transaction_type.value} transaction",
        changes={"reason": txn.deleted_reason, "amount": txn.amount, "date": txn.transaction_date},
    )
    db.commit()


def restore_transaction(db: Session, transaction_id: uuid.UUID) -> Transaction:
    txn = get_transaction(db, transaction_id)
    if txn.deleted_at is None:
        return txn
    if txn.transaction_type == TransactionType.REFUND and txn.related_transaction_id:
        original = db.get(Transaction, txn.related_transaction_id)
        if original is None or original.deleted_at is not None:
            raise ConflictError("Restore the original expense first.")
    txn.deleted_at = None
    txn.deleted_reason = None
    record_audit(
        db,
        entity_type="transaction",
        entity_id=txn.id,
        action=AuditAction.RESTORE,
        summary="Restored transaction",
    )
    db.commit()
    db.refresh(txn)
    return txn


def list_transactions(
    db: Session,
    *,
    page: int,
    page_size: int,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    transaction_type: TransactionType | None = None,
    search: str | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    include_deleted: bool = False,
    sort_by: str = "transaction_date",
    sort_dir: str = "desc",
) -> tuple[list[TransactionRead], int]:
    conditions = []
    if not include_deleted:
        conditions.append(Transaction.deleted_at.is_(None))
    if start_date:
        conditions.append(Transaction.transaction_date >= start_date)
    if end_date:
        conditions.append(Transaction.transaction_date <= end_date)
    if account_id:
        conditions.append(Transaction.account_id == account_id)
    if category_id:
        conditions.append(Transaction.category_id == category_id)
    if transaction_type:
        conditions.append(Transaction.transaction_type == transaction_type)
    if amount_min is not None:
        conditions.append(Transaction.amount >= amount_min)
    if amount_max is not None:
        conditions.append(Transaction.amount <= amount_max)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Transaction.description.ilike(pattern),
                Transaction.merchant_or_payee.ilike(pattern),
                Transaction.notes.ilike(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(Transaction).where(*conditions)) or 0
    sort_columns = {
        "transaction_date": Transaction.transaction_date,
        "amount": Transaction.amount,
        "created_at": Transaction.created_at,
        "description": Transaction.description,
        "updated_at": Transaction.updated_at,
    }
    sort_column = sort_columns.get(sort_by, Transaction.transaction_date)
    order = sort_column.desc() if sort_dir.lower() == "desc" else sort_column.asc()
    stmt = (
        select(Transaction)
        .where(*conditions)
        .order_by(order, Transaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list(db.scalars(stmt))
    refunds = refunded_amounts(db, [row.id for row in rows])
    return [serialize_transaction(row, refunds.get(row.id)) for row in rows], total


def transaction_detail(db: Session, transaction_id: uuid.UUID) -> dict:
    txn = get_transaction(db, transaction_id)
    refunds = list(
        db.scalars(
            select(Transaction)
            .where(
                Transaction.related_transaction_id == txn.id,
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.transaction_date)
        )
    )
    refunded = sum((refund.amount for refund in refunds), ZERO)
    original = None
    if txn.related_transaction_id:
        original_txn = db.get(Transaction, txn.related_transaction_id)
        if original_txn is not None:
            original = serialize_transaction(original_txn)
    return {
        "transaction": serialize_transaction(txn, refunded),
        "refunds": [serialize_transaction(refund) for refund in refunds],
        "original_transaction": original,
        "refundable_remaining": _money(txn.amount - refunded)
        if txn.transaction_type == TransactionType.EXPENSE
        else ZERO,
    }


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


# Exposed for CSV import and recurring services.
def create_imported_transaction(
    db: Session,
    *,
    transaction_date: date,
    transaction_type: TransactionType,
    amount: Decimal,
    account_id: uuid.UUID,
    category_id: uuid.UUID | None,
    description: str,
    merchant_or_payee: str | None = None,
    payment_method: str | None = None,
    notes: str | None = None,
    import_batch_id: uuid.UUID | None = None,
) -> Transaction:
    payload = TransactionCreate(
        transaction_date=transaction_date,
        transaction_type=transaction_type,
        amount=_money(amount),
        account_id=account_id,
        category_id=category_id,
        description=description,
        merchant_or_payee=merchant_or_payee,
        payment_method=payment_method,
        notes=notes,
    )
    txn = create_transaction(db, payload, source="import")
    if import_batch_id is not None:
        txn.import_batch_id = import_batch_id
        db.commit()
    return txn


__all__ = [
    "LedgerEntryKind",
    "create_imported_transaction",
    "create_transaction",
    "delete_transaction",
    "get_transaction",
    "list_transactions",
    "restore_transaction",
    "serialize_transaction",
    "transaction_detail",
    "update_transaction",
    "validate_merged",
]
