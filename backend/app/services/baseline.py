from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.account import Account
from app.models.baseline import BaselineAccount, BaselineSnapshot, BaselineUsageItem
from app.models.enums import AuditAction
from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.schemas.baseline import (
    BaselineAccountInput,
    BaselineAccountRead,
    BaselineRead,
    BaselineUpdate,
    BaselineUsageItemRead,
)
from app.services.audit import record_audit

ZERO = Decimal("0.00")


def get_baseline(db: Session) -> BaselineSnapshot:
    snapshot = db.scalar(
        select(BaselineSnapshot).order_by(BaselineSnapshot.baseline_date.asc())
    )
    if snapshot is None:
        raise NotFoundError("No baseline is configured. Run the seed command first.")
    return snapshot


def serialize_baseline(snapshot: BaselineSnapshot) -> BaselineRead:
    accounts = []
    for entry in sorted(snapshot.accounts, key=lambda row: row.account.name):
        itemized = sum((item.amount for item in entry.usage_items), ZERO)
        accounts.append(
            BaselineAccountRead(
                id=entry.id,
                account_id=entry.account_id,
                account_name=entry.account.name,
                currency=entry.currency,
                original_funds=entry.original_funds,
                historical_usage=entry.historical_usage,
                opening_balance=entry.opening_balance,
                itemized_usage=itemized.quantize(Decimal("0.01")),
                unclassified_usage=(entry.historical_usage - itemized).quantize(Decimal("0.01")),
                usage_items=[
                    BaselineUsageItemRead(
                        id=item.id,
                        description=item.description,
                        amount=item.amount,
                        occurred_on=item.occurred_on,
                        notes=item.notes,
                    )
                    for item in sorted(entry.usage_items, key=lambda row: row.created_at)
                ],
            )
        )
    return BaselineRead(
        id=snapshot.id,
        name=snapshot.name,
        baseline_date=snapshot.baseline_date,
        notes=snapshot.notes,
        total_original_funds=sum((entry.original_funds for entry in snapshot.accounts), ZERO),
        total_historical_usage=sum((entry.historical_usage for entry in snapshot.accounts), ZERO),
        total_opening_balance=sum((entry.opening_balance for entry in snapshot.accounts), ZERO),
        accounts=accounts,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def update_baseline(db: Session, payload: BaselineUpdate) -> BaselineRead:
    snapshot = get_baseline(db)
    new_date = payload.baseline_date or snapshot.baseline_date

    existing = {entry.account_id: entry for entry in snapshot.accounts}
    input_ids = [entry.account_id for entry in payload.accounts]
    if len(input_ids) != len(set(input_ids)):
        raise ValidationError("Each account may appear only once in the baseline.")
    unknown = [account_id for account_id in input_ids if account_id not in existing]
    if unknown:
        raise ValidationError("Baseline update contains accounts that are not in the baseline.")

    if new_date != snapshot.baseline_date:
        earliest_txn = db.scalar(
            select(func.min(Transaction.transaction_date)).where(Transaction.deleted_at.is_(None))
        )
        earliest_transfer = db.scalar(
            select(func.min(Transfer.transfer_date)).where(Transfer.deleted_at.is_(None))
        )
        earliest = min(
            [value for value in (earliest_txn, earliest_transfer) if value is not None],
            default=None,
        )
        if earliest is not None and earliest < new_date:
            raise ConflictError(
                "Cannot move the baseline date after recorded transactions. "
                "Delete or move those transactions first."
            )

    before = {
        "name": snapshot.name,
        "baseline_date": snapshot.baseline_date,
        "notes": snapshot.notes,
        "accounts": {
            str(entry.account_id): {
                "original_funds": entry.original_funds,
                "historical_usage": entry.historical_usage,
                "opening_balance": entry.opening_balance,
            }
            for entry in snapshot.accounts
        },
    }

    if payload.name is not None:
        snapshot.name = payload.name.strip()
    snapshot.baseline_date = new_date
    if payload.notes is not None:
        if not payload.notes.strip():
            raise ValidationError("Baseline notes are required for auditability.")
        snapshot.notes = payload.notes.strip()

    for entry_input in payload.accounts:
        _apply_account_entry(db, snapshot, existing[entry_input.account_id], entry_input, new_date)

    after = {
        "name": snapshot.name,
        "baseline_date": snapshot.baseline_date,
        "notes": snapshot.notes,
        "accounts": {
            str(entry.account_id): {
                "original_funds": entry.original_funds,
                "historical_usage": entry.historical_usage,
                "opening_balance": entry.opening_balance,
            }
            for entry in snapshot.accounts
        },
    }
    record_audit(
        db,
        entity_type="baseline",
        entity_id=snapshot.id,
        action=AuditAction.UPDATE,
        summary="Updated historical baseline",
        changes={"before": before, "after": after},
    )
    db.commit()
    db.refresh(snapshot)
    return serialize_baseline(snapshot)


def _apply_account_entry(
    db: Session,
    snapshot: BaselineSnapshot,
    entry: BaselineAccount,
    payload: BaselineAccountInput,
    baseline_date: date,
) -> None:
    if payload.original_funds != payload.historical_usage + payload.opening_balance:
        raise ValidationError(
            "Original funds must equal historical usage plus opening balance."
        )
    itemized = sum((item.amount for item in payload.usage_items), ZERO)
    if itemized > payload.historical_usage:
        raise ValidationError("Itemized historical usage cannot exceed total historical usage.")

    entry.original_funds = payload.original_funds
    entry.historical_usage = payload.historical_usage
    entry.opening_balance = payload.opening_balance
    entry.usage_items.clear()
    for item in payload.usage_items:
        entry.usage_items.append(
            BaselineUsageItem(
                description=item.description.strip(),
                amount=item.amount,
                occurred_on=item.occurred_on,
                notes=item.notes,
            )
        )

    account = db.get(Account, entry.account_id)
    if account is None:
        raise ValidationError("Baseline references an account that no longer exists.")
    account.opening_balance = payload.opening_balance
    account.opening_date = baseline_date


def baseline_summary(db: Session) -> dict:
    snapshot = get_baseline(db)
    data = serialize_baseline(snapshot)
    return {
        "baseline": data,
        "opening_total": data.total_opening_balance,
        "historical_usage_total": data.total_historical_usage,
        "original_funds_total": data.total_original_funds,
        "note": (
            "Historical usage is shown for context only. It is not counted as "
            "income or expenses in any monthly report."
        ),
    }


def baseline_id_for_account(db: Session, account_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(
        select(BaselineAccount.id).where(BaselineAccount.account_id == account_id)
    )
