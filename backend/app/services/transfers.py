from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.account import Account
from app.models.enums import AuditAction
from app.models.transfer import Transfer
from app.schemas.transaction import TransferCreate, TransferRead, TransferUpdate
from app.services.audit import diff_changes, record_audit


def get_transfer(db: Session, transfer_id: uuid.UUID) -> Transfer:
    transfer = db.get(Transfer, transfer_id)
    if transfer is None:
        raise NotFoundError("Transfer not found.")
    return transfer


def serialize_transfer(transfer: Transfer) -> TransferRead:
    return TransferRead(
        id=transfer.id,
        transfer_date=transfer.transfer_date,
        from_account_id=transfer.from_account_id,
        to_account_id=transfer.to_account_id,
        from_account_name=transfer.from_account.name if transfer.from_account else None,
        to_account_name=transfer.to_account.name if transfer.to_account else None,
        amount=transfer.amount,
        description=transfer.description,
        notes=transfer.notes,
        created_at=transfer.created_at,
        updated_at=transfer.updated_at,
    )


def create_transfer(db: Session, payload: TransferCreate) -> Transfer:
    if payload.idempotency_key:
        existing = db.scalar(
            select(Transfer).where(Transfer.idempotency_key == payload.idempotency_key)
        )
        if existing is not None:
            return existing
    _validate_accounts(db, payload.from_account_id, payload.to_account_id)

    data = payload.model_dump()
    data["amount"] = Decimal(data["amount"]).quantize(Decimal("0.01"))
    data["description"] = data["description"].strip()
    transfer = Transfer(**data)
    db.add(transfer)
    db.flush()
    record_audit(
        db,
        entity_type="transfer",
        entity_id=transfer.id,
        action=AuditAction.CREATE,
        summary=f"Transferred {transfer.amount} between accounts",
        changes={
            "from_account_id": transfer.from_account_id,
            "to_account_id": transfer.to_account_id,
            "amount": transfer.amount,
            "transfer_date": transfer.transfer_date,
        },
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        if payload.idempotency_key:
            existing = db.scalar(
                select(Transfer).where(Transfer.idempotency_key == payload.idempotency_key)
            )
            if existing is not None:
                return existing
        raise
    db.refresh(transfer)
    return transfer


def update_transfer(
    db: Session, transfer_id: uuid.UUID, payload: TransferUpdate
) -> Transfer:
    transfer = get_transfer(db, transfer_id)
    if transfer.deleted_at is not None:
        raise ConflictError("Deleted transfers cannot be edited.")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return transfer
    merged = {
        "from_account_id": transfer.from_account_id,
        "to_account_id": transfer.to_account_id,
        **updates,
    }
    _validate_accounts(db, merged["from_account_id"], merged["to_account_id"])
    if "amount" in updates:
        updates["amount"] = Decimal(updates["amount"]).quantize(Decimal("0.01"))

    before = {key: getattr(transfer, key) for key in updates}
    for key, value in updates.items():
        setattr(transfer, key, value)
    transfer.updated_at = datetime.now(UTC)
    changes = diff_changes(before, {key: getattr(transfer, key) for key in updates})
    if changes:
        record_audit(
            db,
            entity_type="transfer",
            entity_id=transfer.id,
            action=AuditAction.UPDATE,
            summary="Updated transfer",
            changes=changes,
        )
    db.commit()
    db.refresh(transfer)
    return transfer


def delete_transfer(db: Session, transfer_id: uuid.UUID, *, reason: str) -> None:
    transfer = get_transfer(db, transfer_id)
    if transfer.deleted_at is not None:
        raise ConflictError("Transfer is already deleted.")
    transfer.deleted_at = datetime.now(UTC)
    transfer.deleted_reason = reason.strip() or "Deleted by user"
    record_audit(
        db,
        entity_type="transfer",
        entity_id=transfer.id,
        action=AuditAction.DELETE,
        summary="Deleted transfer; both sides reversed",
        changes={
            "amount": transfer.amount,
            "from_account_id": transfer.from_account_id,
            "to_account_id": transfer.to_account_id,
        },
    )
    db.commit()


def list_transfers(
    db: Session,
    *,
    page: int,
    page_size: int,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: uuid.UUID | None = None,
    include_deleted: bool = False,
) -> tuple[list[TransferRead], int]:
    conditions = []
    if not include_deleted:
        conditions.append(Transfer.deleted_at.is_(None))
    if start_date:
        conditions.append(Transfer.transfer_date >= start_date)
    if end_date:
        conditions.append(Transfer.transfer_date <= end_date)
    if account_id:
        conditions.append(
            or_(
                Transfer.from_account_id == account_id,
                Transfer.to_account_id == account_id,
            )
        )
    total = db.scalar(select(func.count()).select_from(Transfer).where(*conditions)) or 0
    stmt = (
        select(Transfer)
        .where(*conditions)
        .order_by(Transfer.transfer_date.desc(), Transfer.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [serialize_transfer(row) for row in db.scalars(stmt)], total


def _validate_accounts(
    db: Session, from_account_id: uuid.UUID, to_account_id: uuid.UUID
) -> None:
    if from_account_id == to_account_id:
        raise ValidationError("Source and destination accounts must differ.")
    source = db.get(Account, from_account_id)
    destination = db.get(Account, to_account_id)
    if source is None or destination is None:
        raise ValidationError("Both accounts must exist.")
    if not source.is_active or not destination.is_active:
        raise ValidationError("Transfers require active accounts.")
