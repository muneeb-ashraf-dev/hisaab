from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    String,
    case,
    cast,
    func,
    literal,
    null,
    or_,
    select,
    union_all,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, aliased

from app.models.account import Account
from app.models.category import Category
from app.models.committee import Committee
from app.models.enums import LedgerEntryKind, TransactionType
from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.schemas.transaction import LedgerEntry

INFLOW_TYPES = (
    TransactionType.INCOME,
    TransactionType.REFUND,
    TransactionType.ADJUSTMENT_INCREASE,
)


def ledger_subquery(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    transaction_type: TransactionType | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
):
    transfer_direction = literal("transfer", String(20))
    if account_id is not None:
        transfer_direction = case(
            (Transfer.from_account_id == account_id, literal("out", String(20))),
            else_=literal("in", String(20)),
        )

    txn_stmt = (
        select(
            Transaction.id.label("id"),
            literal(LedgerEntryKind.TRANSACTION.value, String(20)).label("entry_kind"),
            Transaction.transaction_date.label("entry_date"),
            Transaction.amount.label("amount"),
            cast(Transaction.transaction_type, String(30)).label("transaction_type"),
            Transaction.description.label("description"),
            Transaction.account_id.label("account_id"),
            Account.name.label("account_name"),
            cast(null(), UUID(as_uuid=True)).label("from_account_id"),
            cast(null(), String(80)).label("from_account_name"),
            cast(null(), UUID(as_uuid=True)).label("to_account_id"),
            cast(null(), String(80)).label("to_account_name"),
            Transaction.category_id.label("category_id"),
            Category.name.label("category_name"),
            Category.color.label("category_color"),
            Transaction.committee_id.label("committee_id"),
            Committee.name.label("committee_name"),
            Transaction.merchant_or_payee.label("merchant_or_payee"),
            Transaction.payment_method.label("payment_method"),
            Transaction.notes.label("notes"),
            Transaction.related_transaction_id.label("related_transaction_id"),
            Transaction.created_at.label("created_at"),
            case((Transaction.transaction_type.in_(INFLOW_TYPES), "in"), else_="out").label(
                "direction"
            ),
        )
        .select_from(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .outerjoin(Committee, Committee.id == Transaction.committee_id)
        .where(Transaction.deleted_at.is_(None))
    )

    from_account = aliased(Account)
    to_account = aliased(Account)
    transfer_stmt = (
        select(
            Transfer.id.label("id"),
            literal(LedgerEntryKind.TRANSFER.value, String(20)).label("entry_kind"),
            Transfer.transfer_date.label("entry_date"),
            Transfer.amount.label("amount"),
            cast(null(), String(30)).label("transaction_type"),
            Transfer.description.label("description"),
            cast(null(), UUID(as_uuid=True)).label("account_id"),
            cast(null(), String(80)).label("account_name"),
            Transfer.from_account_id.label("from_account_id"),
            from_account.name.label("from_account_name"),
            Transfer.to_account_id.label("to_account_id"),
            to_account.name.label("to_account_name"),
            cast(null(), UUID(as_uuid=True)).label("category_id"),
            cast(null(), String(80)).label("category_name"),
            cast(null(), String(7)).label("category_color"),
            cast(null(), UUID(as_uuid=True)).label("committee_id"),
            cast(null(), String(120)).label("committee_name"),
            cast(null(), String(160)).label("merchant_or_payee"),
            cast(null(), String(60)).label("payment_method"),
            Transfer.notes.label("notes"),
            cast(null(), UUID(as_uuid=True)).label("related_transaction_id"),
            Transfer.created_at.label("created_at"),
            transfer_direction.label("direction"),
        )
        .select_from(Transfer)
        .join(from_account, from_account.id == Transfer.from_account_id)
        .join(to_account, to_account.id == Transfer.to_account_id)
        .where(Transfer.deleted_at.is_(None))
    )

    if start_date:
        txn_stmt = txn_stmt.where(Transaction.transaction_date >= start_date)
        transfer_stmt = transfer_stmt.where(Transfer.transfer_date >= start_date)
    if end_date:
        txn_stmt = txn_stmt.where(Transaction.transaction_date <= end_date)
        transfer_stmt = transfer_stmt.where(Transfer.transfer_date <= end_date)
    if category_id:
        txn_stmt = txn_stmt.where(Transaction.category_id == category_id)
        transfer_stmt = transfer_stmt.where(literal(False))
    if transaction_type is not None:
        txn_stmt = txn_stmt.where(Transaction.transaction_type == transaction_type)
        transfer_stmt = transfer_stmt.where(literal(False))
    if account_id:
        txn_stmt = txn_stmt.where(Transaction.account_id == account_id)
        transfer_stmt = transfer_stmt.where(
            or_(Transfer.from_account_id == account_id, Transfer.to_account_id == account_id)
        )
    if amount_min is not None:
        txn_stmt = txn_stmt.where(Transaction.amount >= amount_min)
        transfer_stmt = transfer_stmt.where(Transfer.amount >= amount_min)
    if amount_max is not None:
        txn_stmt = txn_stmt.where(Transaction.amount <= amount_max)
        transfer_stmt = transfer_stmt.where(Transfer.amount <= amount_max)

    return union_all(txn_stmt, transfer_stmt).subquery("ledger")


def query_ledger(
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
    sort_by: str = "entry_date",
    sort_dir: str = "desc",
) -> tuple[list[LedgerEntry], int]:
    ledger = ledger_subquery(
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
        amount_min=amount_min,
        amount_max=amount_max,
    )
    conditions = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                ledger.c.description.ilike(pattern),
                ledger.c.merchant_or_payee.ilike(pattern),
                ledger.c.notes.ilike(pattern),
                ledger.c.category_name.ilike(pattern),
                ledger.c.account_name.ilike(pattern),
                ledger.c.from_account_name.ilike(pattern),
                ledger.c.to_account_name.ilike(pattern),
            )
        )
    total = db.scalar(select(func.count()).select_from(ledger).where(*conditions)) or 0
    sort_columns = {
        "entry_date": ledger.c.entry_date,
        "amount": ledger.c.amount,
        "description": ledger.c.description,
        "created_at": ledger.c.created_at,
    }
    sort_column = sort_columns.get(sort_by, ledger.c.entry_date)
    order = sort_column.desc() if sort_dir.lower() == "desc" else sort_column.asc()
    stmt = (
        select(ledger)
        .where(*conditions)
        .order_by(order, ledger.c.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [_to_entry(row) for row in db.execute(stmt).mappings()], total


def _to_entry(row) -> LedgerEntry:  # type: ignore[no-untyped-def]
    return LedgerEntry(
        id=row["id"],
        entry_kind=LedgerEntryKind(row["entry_kind"]),
        entry_date=row["entry_date"],
        amount=row["amount"],
        direction=row["direction"] or "out",
        transaction_type=TransactionType(row["transaction_type"])
        if row["transaction_type"]
        else None,
        description=row["description"],
        account_id=row["account_id"],
        account_name=row["account_name"],
        from_account_id=row["from_account_id"],
        from_account_name=row["from_account_name"],
        to_account_id=row["to_account_id"],
        to_account_name=row["to_account_name"],
        category_id=row["category_id"],
        category_name=row["category_name"],
        category_color=row["category_color"],
        committee_id=row["committee_id"],
        committee_name=row["committee_name"],
        merchant_or_payee=row["merchant_or_payee"],
        payment_method=row["payment_method"],
        notes=row["notes"],
        related_transaction_id=row["related_transaction_id"],
        created_at=row["created_at"],
    )


def recent_ledger(db: Session, *, limit: int = 8) -> list[LedgerEntry]:
    entries, _ = query_ledger(db, page=1, page_size=limit, sort_by="entry_date", sort_dir="desc")
    return entries


__all__ = ["ledger_subquery", "query_ledger", "recent_ledger"]
