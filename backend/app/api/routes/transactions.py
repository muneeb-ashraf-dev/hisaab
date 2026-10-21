from __future__ import annotations

import math
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession, PageDep, optional_range
from app.models.enums import TransactionType
from app.schemas.common import Message, Page, PageMeta
from app.schemas.transaction import (
    LedgerEntry,
    TransactionCreate,
    TransactionDetail,
    TransactionRead,
    TransactionUpdate,
)
from app.services import ledger as ledger_service
from app.services import transactions as transaction_service

router = APIRouter(tags=["transactions"])


@router.get("/transactions", response_model=Page[TransactionRead])
def list_transactions(
    db: DbSession,
    page: PageDep,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    transaction_type: TransactionType | None = None,
    search: str | None = Query(default=None, max_length=120),
    amount_min: Decimal | None = Query(default=None, ge=0),
    amount_max: Decimal | None = Query(default=None, ge=0),
    include_deleted: bool = False,
    sort_by: str = "transaction_date",
    sort_dir: str = "desc",
) -> Page[TransactionRead]:
    start, end = optional_range(start_date, end_date)
    items, total = transaction_service.list_transactions(
        db,
        page=page.page,
        page_size=page.page_size,
        start_date=start,
        end_date=end,
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
        search=search,
        amount_min=amount_min,
        amount_max=amount_max,
        include_deleted=include_deleted,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page(
        items=items,
        meta=PageMeta(
            page=page.page,
            page_size=page.page_size,
            total=total,
            total_pages=max(math.ceil(total / page.page_size), 1),
        ),
    )


@router.post("/transactions", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(db: DbSession, payload: TransactionCreate) -> TransactionRead:
    txn = transaction_service.create_transaction(db, payload)
    return transaction_service.serialize_transaction(txn)


@router.get("/transactions/{transaction_id}", response_model=TransactionDetail)
def get_transaction(db: DbSession, transaction_id: uuid.UUID) -> TransactionDetail:
    detail = transaction_service.transaction_detail(db, transaction_id)
    return TransactionDetail(**detail)


@router.patch("/transactions/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    db: DbSession, transaction_id: uuid.UUID, payload: TransactionUpdate
) -> TransactionRead:
    txn = transaction_service.update_transaction(db, transaction_id, payload)
    from app.services.transactions import refunded_amounts

    refunded = refunded_amounts(db, [txn.id]).get(txn.id)
    return transaction_service.serialize_transaction(txn, refunded)


@router.delete("/transactions/{transaction_id}", response_model=Message)
def delete_transaction(
    db: DbSession,
    transaction_id: uuid.UUID,
    reason: str = Query(default="Deleted by user", min_length=3, max_length=255),
) -> Message:
    transaction_service.delete_transaction(db, transaction_id, reason=reason)
    return Message(message="Transaction deleted. Its balance effect was reversed.")


@router.post("/transactions/{transaction_id}/restore", response_model=TransactionRead)
def restore_transaction(db: DbSession, transaction_id: uuid.UUID) -> TransactionRead:
    txn = transaction_service.restore_transaction(db, transaction_id)
    return transaction_service.serialize_transaction(txn)


@router.get("/ledger", response_model=Page[LedgerEntry])
def get_ledger(
    db: DbSession,
    page: PageDep,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    transaction_type: TransactionType | None = None,
    search: str | None = Query(default=None, max_length=120),
    amount_min: Decimal | None = Query(default=None, ge=0),
    amount_max: Decimal | None = Query(default=None, ge=0),
    sort_by: str = "entry_date",
    sort_dir: str = "desc",
) -> Page[LedgerEntry]:
    start, end = optional_range(start_date, end_date)
    items, total = ledger_service.query_ledger(
        db,
        page=page.page,
        page_size=page.page_size,
        start_date=start,
        end_date=end,
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
        search=search,
        amount_min=amount_min,
        amount_max=amount_max,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page(
        items=items,
        meta=PageMeta(
            page=page.page,
            page_size=page.page_size,
            total=total,
            total_pages=max(math.ceil(total / page.page_size), 1),
        ),
    )
