from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession
from app.schemas.committee import CommitteeCreate, CommitteeRead, CommitteeUpdate
from app.schemas.common import Message
from app.services import committees as committee_service

router = APIRouter(prefix="/committees", tags=["committees"])


@router.get("", response_model=list[CommitteeRead])
def list_committees(
    db: DbSession,
    as_of: date | None = Query(
        default=None,
        description="Month used to calculate paid and remaining installments. Defaults to today.",
    ),
) -> list[CommitteeRead]:
    return committee_service.list_committees(db, as_of=as_of)


@router.post("", response_model=CommitteeRead, status_code=status.HTTP_201_CREATED)
def create_committee(db: DbSession, payload: CommitteeCreate) -> CommitteeRead:
    return committee_service.create_committee(db, payload)


@router.get("/{committee_id}", response_model=CommitteeRead)
def get_committee(db: DbSession, committee_id: uuid.UUID) -> CommitteeRead:
    return committee_service.serialize_committee(
        db, committee_service.get_committee(db, committee_id)
    )


@router.patch("/{committee_id}", response_model=CommitteeRead)
def update_committee(
    db: DbSession, committee_id: uuid.UUID, payload: CommitteeUpdate
) -> CommitteeRead:
    return committee_service.update_committee(db, committee_id, payload)


@router.delete("/{committee_id}", response_model=Message)
def delete_committee(db: DbSession, committee_id: uuid.UUID) -> Message:
    committee_service.delete_committee(db, committee_id)
    return Message(message="Committee deleted.")
