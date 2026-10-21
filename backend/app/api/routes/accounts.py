from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DbSession, resolve_range
from app.schemas.account import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    AccountWithBalance,
)
from app.schemas.common import Message
from app.services import accounts as account_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountWithBalance])
def list_accounts(
    db: DbSession,
    start_date: date | None = None,
    end_date: date | None = None,
    include_inactive: bool = Query(True),
) -> list[AccountWithBalance]:
    start, end = resolve_range(start_date, end_date)
    return account_service.list_accounts(
        db, start_date=start, end_date=end, include_inactive=include_inactive
    )


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(db: DbSession, payload: AccountCreate) -> AccountRead:
    account = account_service.create_account(db, payload)
    return AccountRead.model_validate(account)


@router.get("/{account_id}", response_model=AccountWithBalance)
def get_account(
    db: DbSession,
    account_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AccountWithBalance:
    start, end = resolve_range(start_date, end_date)
    account = account_service.get_account(db, account_id)
    return account_service.to_account_with_balance(
        account, start_date=start, end_date=end, db=db
    )


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    db: DbSession, account_id: uuid.UUID, payload: AccountUpdate
) -> AccountRead:
    account = account_service.update_account(db, account_id, payload)
    return AccountRead.model_validate(account)


@router.delete("/{account_id}", response_model=Message)
def delete_account(
    db: DbSession, account_id: uuid.UUID, response: Response
) -> Message:
    account_service.delete_account(db, account_id)
    response.status_code = status.HTTP_200_OK
    return Message(message="Account deleted.")
