from __future__ import annotations

import math
import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession, PageDep, optional_range
from app.schemas.common import Message, Page, PageMeta
from app.schemas.transaction import TransferCreate, TransferRead, TransferUpdate
from app.services import transfers as transfer_service

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("", response_model=Page[TransferRead])
def list_transfers(
    db: DbSession,
    page: PageDep,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: uuid.UUID | None = None,
    include_deleted: bool = False,
) -> Page[TransferRead]:
    start, end = optional_range(start_date, end_date)
    items, total = transfer_service.list_transfers(
        db,
        page=page.page,
        page_size=page.page_size,
        start_date=start,
        end_date=end,
        account_id=account_id,
        include_deleted=include_deleted,
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


@router.post("", response_model=TransferRead, status_code=status.HTTP_201_CREATED)
def create_transfer(db: DbSession, payload: TransferCreate) -> TransferRead:
    transfer = transfer_service.create_transfer(db, payload)
    return transfer_service.serialize_transfer(transfer)


@router.get("/{transfer_id}", response_model=TransferRead)
def get_transfer(db: DbSession, transfer_id: uuid.UUID) -> TransferRead:
    return transfer_service.serialize_transfer(
        transfer_service.get_transfer(db, transfer_id)
    )


@router.patch("/{transfer_id}", response_model=TransferRead)
def update_transfer(
    db: DbSession, transfer_id: uuid.UUID, payload: TransferUpdate
) -> TransferRead:
    transfer = transfer_service.update_transfer(db, transfer_id, payload)
    return transfer_service.serialize_transfer(transfer)


@router.delete("/{transfer_id}", response_model=Message)
def delete_transfer(
    db: DbSession,
    transfer_id: uuid.UUID,
    reason: str = Query(default="Deleted by user", min_length=3, max_length=255),
) -> Message:
    transfer_service.delete_transfer(db, transfer_id, reason=reason)
    return Message(message="Transfer deleted. Both account balances were reversed.")
