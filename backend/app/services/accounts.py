from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.account import Account
from app.models.enums import AuditAction, TransactionType
from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.schemas.account import (
    AccountActivity,
    AccountCreate,
    AccountUpdate,
    AccountWithBalance,
)
from app.services.audit import diff_changes, record_audit

ZERO = Decimal("0.00")
INCOME_TYPES = (TransactionType.INCOME,)
EXPENSE_TYPES = (TransactionType.EXPENSE,)
REFUND_TYPES = (TransactionType.REFUND,)


def get_account(db: Session, account_id: uuid.UUID) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found.")
    return account


def list_accounts(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    include_inactive: bool = True,
) -> list[AccountWithBalance]:
    stmt = select(Account).order_by(Account.name)
    if not include_inactive:
        stmt = stmt.where(Account.is_active.is_(True))
    accounts = list(db.scalars(stmt))
    balances = aggregate_balances(db)
    period = aggregate_period_totals(db, start_date=start_date, end_date=end_date)
    recent = recent_activity_by_account(db, limit=5)

    result: list[AccountWithBalance] = []
    for account in accounts:
        current, projected = balances.get(account.id, (ZERO, ZERO))
        income, expenses = period.get(account.id, (ZERO, ZERO))
        result.append(
            AccountWithBalance(
                **{
                    **{key: getattr(account, key) for key in (
                        "id",
                        "name",
                        "account_type",
                        "currency",
                        "opening_balance",
                        "opening_date",
                        "is_active",
                        "notes",
                        "created_at",
                        "updated_at",
                    )},
                    "current_balance": current,
                    "projected_balance": projected,
                    "period_income": income,
                    "period_expenses": expenses,
                    "recent_activity": recent.get(account.id, []),
                }
            )
        )
    return result


def aggregate_balances(
    db: Session, *, as_of: date | None = None
) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
    """Return {account_id: (current_balance, projected_balance)}.

    The ledger's current balance is opening balance plus every non-deleted
    recorded entry. Future-dated planned entries are included because the
    product is explicitly a forward-looking ledger; reports and reminders make
    the timing of those entries clear. ``as_of`` is retained for API
    compatibility and returns the historical balance when provided.
    """
    accounts = list(db.scalars(select(Account)))
    current_map = _net_movements(db, end_date=as_of)
    projected_map = _net_movements(db, end_date=None)

    result: dict[uuid.UUID, tuple[Decimal, Decimal]] = {}
    for account in accounts:
        opening = Decimal(account.opening_balance or 0)
        result[account.id] = (
            (opening + current_map.get(account.id, ZERO)).quantize(Decimal("0.01")),
            (opening + projected_map.get(account.id, ZERO)).quantize(Decimal("0.01")),
        )
    return result


def _net_movements(
    db: Session,
    *,
    end_date: date | None,
) -> dict[uuid.UUID, Decimal]:
    income = func.coalesce(
        func.sum(
            case(
                (
                    Transaction.transaction_type.in_(
                        [
                            TransactionType.INCOME,
                            TransactionType.REFUND,
                            TransactionType.ADJUSTMENT_INCREASE,
                        ]
                    ),
                    Transaction.amount,
                ),
                else_=ZERO,
            )
        ),
        ZERO,
    )
    outflow = func.coalesce(
        func.sum(
            case(
                (
                    Transaction.transaction_type.in_(
                        [TransactionType.EXPENSE, TransactionType.ADJUSTMENT_DECREASE]
                    ),
                    Transaction.amount,
                ),
                else_=ZERO,
            )
        ),
        ZERO,
    )

    txn_stmt = (
        select(Transaction.account_id, income.label("inflow"), outflow.label("outflow"))
        .where(Transaction.deleted_at.is_(None))
        .group_by(Transaction.account_id)
    )
    if end_date is not None:
        txn_stmt = txn_stmt.where(Transaction.transaction_date <= end_date)

    movements: dict[uuid.UUID, Decimal] = {}
    for account_id, inflow, outflow in db.execute(txn_stmt):
        movements[account_id] = Decimal(inflow or 0) - Decimal(outflow or 0)

    transfer_in = func.coalesce(func.sum(Transfer.amount), ZERO)
    stmt_in = (
        select(Transfer.to_account_id, transfer_in)
        .where(Transfer.deleted_at.is_(None))
        .group_by(Transfer.to_account_id)
    )
    stmt_out = (
        select(Transfer.from_account_id, func.coalesce(func.sum(Transfer.amount), ZERO))
        .where(Transfer.deleted_at.is_(None))
        .group_by(Transfer.from_account_id)
    )
    if end_date is not None:
        stmt_in = stmt_in.where(Transfer.transfer_date <= end_date)
        stmt_out = stmt_out.where(Transfer.transfer_date <= end_date)

    for account_id, amount in db.execute(stmt_in):
        movements[account_id] = movements.get(account_id, ZERO) + Decimal(amount or 0)
    for account_id, amount in db.execute(stmt_out):
        movements[account_id] = movements.get(account_id, ZERO) - Decimal(amount or 0)
    return movements


def aggregate_period_totals(
    db: Session, *, start_date: date, end_date: date
) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
    """Return {account_id: (income, net_expenses)} for the inclusive period."""
    income = func.coalesce(
        func.sum(
            case(
                (Transaction.transaction_type == TransactionType.INCOME, Transaction.amount),
                else_=ZERO,
            )
        ),
        ZERO,
    )
    expenses = func.coalesce(
        func.sum(
            case(
                (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                else_=ZERO,
            )
        ),
        ZERO,
    )
    refunds = func.coalesce(
        func.sum(
            case(
                (Transaction.transaction_type == TransactionType.REFUND, Transaction.amount),
                else_=ZERO,
            )
        ),
        ZERO,
    )
    stmt = (
        select(
            Transaction.account_id,
            income.label("income"),
            expenses.label("expenses"),
            refunds.label("refunds"),
        )
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
        .group_by(Transaction.account_id)
    )
    result: dict[uuid.UUID, tuple[Decimal, Decimal]] = {}
    for account_id, inc, exp, ref in db.execute(stmt):
        result[account_id] = (
            Decimal(inc or 0).quantize(Decimal("0.01")),
            (Decimal(exp or 0) - Decimal(ref or 0)).quantize(Decimal("0.01")),
        )
    return result


def recent_activity_by_account(
    db: Session, *, limit: int = 5
) -> dict[uuid.UUID, list[AccountActivity]]:
    txn_stmt = (
        select(Transaction)
        .where(Transaction.deleted_at.is_(None))
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
    )
    entries: dict[uuid.UUID, list[tuple[date, object, AccountActivity]]] = {}
    for txn in db.scalars(txn_stmt):
        direction = (
            "in"
            if txn.transaction_type
            in (
                TransactionType.INCOME,
                TransactionType.REFUND,
                TransactionType.ADJUSTMENT_INCREASE,
            )
            else "out"
        )
        activity = AccountActivity(
            id=txn.id,
            entry_kind="transaction",
            entry_date=txn.transaction_date,
            description=txn.description,
            amount=txn.amount,
            direction=direction,
            category_name=txn.category.name if txn.category else None,
        )
        entries.setdefault(txn.account_id, []).append(
            (txn.transaction_date, txn.created_at, activity)
        )

    transfer_stmt = select(Transfer).where(Transfer.deleted_at.is_(None))
    for transfer in db.scalars(transfer_stmt):
        entries.setdefault(transfer.from_account_id, []).append(
            (
                transfer.transfer_date,
                transfer.created_at,
                AccountActivity(
                    id=transfer.id,
                    entry_kind="transfer",
                    entry_date=transfer.transfer_date,
                    description=transfer.description,
                    amount=transfer.amount,
                    direction="out",
                    counterparty_account=transfer.to_account.name,
                ),
            )
        )
        entries.setdefault(transfer.to_account_id, []).append(
            (
                transfer.transfer_date,
                transfer.created_at,
                AccountActivity(
                    id=transfer.id,
                    entry_kind="transfer",
                    entry_date=transfer.transfer_date,
                    description=transfer.description,
                    amount=transfer.amount,
                    direction="in",
                    counterparty_account=transfer.from_account.name,
                ),
            )
        )

    result: dict[uuid.UUID, list[AccountActivity]] = {}
    for account_id, rows in entries.items():
        rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
        result[account_id] = [row[2] for row in rows[:limit]]
    return result


def create_account(db: Session, payload: AccountCreate) -> Account:
    _ensure_unique_name(db, payload.name)
    account = Account(**payload.model_dump())
    db.add(account)
    db.flush()
    record_audit(
        db,
        entity_type="account",
        entity_id=account.id,
        action=AuditAction.CREATE,
        summary=f"Created account {account.name}",
        changes=payload.model_dump(),
    )
    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, account_id: uuid.UUID, payload: AccountUpdate) -> Account:
    account = get_account(db, account_id)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != account.name:
        _ensure_unique_name(db, updates["name"], exclude_id=account.id)
        updates["name"] = updates["name"].strip()
    if "currency" in updates and updates["currency"]:
        updates["currency"] = updates["currency"].upper()

    before = {key: getattr(account, key) for key in updates}
    for key, value in updates.items():
        setattr(account, key, value)
    changes = diff_changes(before, {key: getattr(account, key) for key in updates})
    if changes:
        record_audit(
            db,
            entity_type="account",
            entity_id=account.id,
            action=AuditAction.UPDATE,
            summary=f"Updated account {account.name}",
            changes=changes,
        )
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account_id: uuid.UUID) -> None:
    account = get_account(db, account_id)
    has_transactions = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.account_id == account_id)
    )
    has_transfers = db.scalar(
        select(func.count())
        .select_from(Transfer)
        .where(or_(Transfer.from_account_id == account_id, Transfer.to_account_id == account_id))
    )
    if has_transactions or has_transfers:
        raise ConflictError(
            "This account has ledger history and cannot be deleted. Deactivate it instead."
        )
    record_audit(
        db,
        entity_type="account",
        entity_id=account.id,
        action=AuditAction.DELETE,
        summary=f"Deleted account {account.name}",
        changes={"name": account.name, "opening_balance": account.opening_balance},
    )
    db.delete(account)
    db.commit()


def _ensure_unique_name(db: Session, name: str, *, exclude_id: uuid.UUID | None = None) -> None:
    normalized = name.strip().lower()
    stmt = select(Account.id).where(func.lower(Account.name) == normalized)
    if exclude_id is not None:
        stmt = stmt.where(Account.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("An account with this name already exists.")


def to_account_with_balance(
    account: Account, *, start_date: date, end_date: date, db: Session
) -> AccountWithBalance:
    balances = aggregate_balances(db)
    current, projected = balances.get(account.id, (ZERO, ZERO))
    period = aggregate_period_totals(db, start_date=start_date, end_date=end_date)
    income, expenses = period.get(account.id, (ZERO, ZERO))
    recent = recent_activity_by_account(db, limit=5).get(account.id, [])
    base = {
        key: getattr(account, key)
        for key in (
            "id",
            "name",
            "account_type",
            "currency",
            "opening_balance",
            "opening_date",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        )
    }
    return AccountWithBalance(
        **base,
        current_balance=current,
        projected_balance=projected,
        period_income=income,
        period_expenses=expenses,
        recent_activity=recent,
    )


def safe_commit(db: Session, *, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValidationError(message) from exc
