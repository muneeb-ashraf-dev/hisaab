from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.common import Message
from app.schemas.recurring import (
    OccurrenceRead,
    PostDueResult,
    RecurringCreate,
    RecurringRead,
    RecurringUpdate,
    UpcomingRecurring,
)
from app.services import recurring as recurring_service

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.get("", response_model=list[RecurringRead])
def list_recurring(db: DbSession) -> list[RecurringRead]:
    return recurring_service.list_templates(db)


@router.post("", response_model=RecurringRead, status_code=status.HTTP_201_CREATED)
def create_recurring(db: DbSession, payload: RecurringCreate) -> RecurringRead:
    return recurring_service.create_template(db, payload)


@router.get("/upcoming", response_model=list[UpcomingRecurring])
def get_upcoming(db: DbSession, horizon_days: int = 45) -> list[UpcomingRecurring]:
    return recurring_service.upcoming(db, horizon_days=max(0, min(horizon_days, 365)))


@router.get("/reminders")
def get_reminders(db: DbSession) -> dict:
    return recurring_service.reminder_summary(db)


@router.post("/run", response_model=PostDueResult)
def run_recurring(db: DbSession, through: date | None = None) -> PostDueResult:
    return recurring_service.post_due(db, through=through)


@router.get("/{template_id}", response_model=RecurringRead)
def get_recurring(db: DbSession, template_id: uuid.UUID) -> RecurringRead:
    return recurring_service.serialize_template(
        recurring_service.get_template(db, template_id)
    )


@router.patch("/{template_id}", response_model=RecurringRead)
def update_recurring(
    db: DbSession, template_id: uuid.UUID, payload: RecurringUpdate
) -> RecurringRead:
    return recurring_service.update_template(db, template_id, payload)


@router.delete("/{template_id}", response_model=Message)
def delete_recurring(db: DbSession, template_id: uuid.UUID) -> Message:
    recurring_service.delete_template(db, template_id)
    return Message(message="Recurring template deleted. Posted transactions are kept.")


@router.post("/{template_id}/post", response_model=PostDueResult)
def post_recurring(
    db: DbSession, template_id: uuid.UUID, through: date | None = None
) -> PostDueResult:
    return recurring_service.post_due(db, template_id=template_id, through=through)


@router.post("/{template_id}/skip", response_model=RecurringRead)
def skip_occurrence(
    db: DbSession, template_id: uuid.UUID, due_date: date
) -> RecurringRead:
    return recurring_service.skip_occurrence(db, template_id, due_date)


@router.get("/{template_id}/occurrences", response_model=list[OccurrenceRead])
def list_occurrences(db: DbSession, template_id: uuid.UUID) -> list[OccurrenceRead]:
    return recurring_service.occurrences(db, template_id)
