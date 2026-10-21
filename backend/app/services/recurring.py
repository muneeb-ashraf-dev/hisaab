from __future__ import annotations

import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.category import Category
from app.models.enums import (
    AuditAction,
    CategoryType,
    OccurrenceStatus,
    RecurringFrequency,
    TransactionType,
)
from app.models.recurring import RecurringOccurrence, RecurringTemplate
from app.schemas.recurring import (
    OccurrenceRead,
    PostDueResult,
    RecurringCreate,
    RecurringRead,
    RecurringUpdate,
    UpcomingRecurring,
)
from app.schemas.transaction import TransactionCreate
from app.services.audit import diff_changes, record_audit
from app.services.transactions import create_transaction

ZERO = Decimal("0.00")


def get_template(db: Session, template_id: uuid.UUID) -> RecurringTemplate:
    template = db.get(RecurringTemplate, template_id)
    if template is None:
        raise NotFoundError("Recurring template not found.")
    return template


def serialize_template(template: RecurringTemplate) -> RecurringRead:
    today = date.today()
    return RecurringRead(
        id=template.id,
        name=template.name,
        transaction_type=template.transaction_type,
        amount=template.amount,
        account_id=template.account_id,
        account_name=template.account.name if template.account else None,
        category_id=template.category_id,
        category_name=template.category.name if template.category else None,
        category_color=template.category.color if template.category else None,
        description=template.description,
        merchant_or_payee=template.merchant_or_payee,
        payment_method=template.payment_method,
        notes=template.notes,
        frequency=template.frequency,
        interval_count=template.interval_count,
        start_date=template.start_date,
        next_due_date=template.next_due_date,
        end_date=template.end_date,
        is_active=template.is_active,
        auto_post=template.auto_post,
        created_at=template.created_at,
        updated_at=template.updated_at,
        days_until_due=(template.next_due_date - today).days,
    )


def list_templates(db: Session) -> list[RecurringRead]:
    templates = list(
        db.scalars(
            select(RecurringTemplate).order_by(
                RecurringTemplate.is_active.desc(), RecurringTemplate.next_due_date
            )
        )
    )
    return [serialize_template(template) for template in templates]


def create_template(db: Session, payload: RecurringCreate) -> RecurringRead:
    _validate_category(db, payload.category_id, payload.transaction_type)
    template = RecurringTemplate(**payload.model_dump())
    db.add(template)
    db.flush()
    record_audit(
        db,
        entity_type="recurring_template",
        entity_id=template.id,
        action=AuditAction.CREATE,
        summary=f"Created recurring template {template.name}",
        changes=payload.model_dump(),
    )
    db.commit()
    db.refresh(template)
    return serialize_template(template)


def update_template(
    db: Session, template_id: uuid.UUID, payload: RecurringUpdate
) -> RecurringRead:
    template = get_template(db, template_id)
    updates = payload.model_dump(exclude_unset=True)
    tx_type = updates.get("transaction_type", template.transaction_type)
    category_id = updates.get("category_id", template.category_id)
    if tx_type not in (TransactionType.INCOME, TransactionType.EXPENSE):
        raise ValidationError("Recurring templates must be income or expense.")
    _validate_category(db, category_id, tx_type)
    if "end_date" in updates and updates["end_date"] is not None:
        start = updates.get("start_date", template.start_date)
        if updates["end_date"] < start:
            raise ValidationError("end_date must be on or after start_date.")
    before = {key: getattr(template, key) for key in updates}
    for key, value in updates.items():
        setattr(template, key, value)
    changes = diff_changes(before, {key: getattr(template, key) for key in updates})
    if changes:
        record_audit(
            db,
            entity_type="recurring_template",
            entity_id=template.id,
            action=AuditAction.UPDATE,
            summary=f"Updated recurring template {template.name}",
            changes=changes,
        )
    db.commit()
    db.refresh(template)
    return serialize_template(template)


def delete_template(db: Session, template_id: uuid.UUID) -> None:
    template = get_template(db, template_id)
    record_audit(
        db,
        entity_type="recurring_template",
        entity_id=template.id,
        action=AuditAction.DELETE,
        summary=f"Deleted recurring template {template.name}",
    )
    db.delete(template)
    db.commit()


def upcoming(
    db: Session, *, horizon_days: int = 45, include_overdue: bool = True
) -> list[UpcomingRecurring]:
    today = date.today()
    horizon = today + timedelta(days=horizon_days)
    templates = list(
        db.scalars(
            select(RecurringTemplate)
            .where(RecurringTemplate.is_active.is_(True))
            .order_by(RecurringTemplate.next_due_date)
        )
    )
    occurrences = {
        (row.template_id, row.due_date): row
        for row in db.scalars(select(RecurringOccurrence))
    }
    results: list[UpcomingRecurring] = []
    for template in templates:
        due = template.next_due_date
        guard = 0
        while due <= horizon and (template.end_date is None or due <= template.end_date):
            guard += 1
            if guard > 120:
                break
            if include_overdue or due >= today:
                occurrence = occurrences.get((template.id, due))
                status = occurrence.status.value if occurrence else OccurrenceStatus.PENDING.value
                if status == OccurrenceStatus.PENDING.value:
                    results.append(
                        UpcomingRecurring(
                            template_id=template.id,
                            name=template.name,
                            description=template.description,
                            amount=template.amount,
                            transaction_type=template.transaction_type,
                            due_date=due,
                            account_id=template.account_id,
                            account_name=template.account.name,
                            category_name=template.category.name
                            if template.category
                            else None,
                            is_overdue=due < today,
                            occurrence_status=status,
                        )
                    )
            due = next_occurrence(due, template.frequency, template.interval_count)
    results.sort(key=lambda item: item.due_date)
    return results[:50]


def post_due(
    db: Session, *, template_id: uuid.UUID | None = None, through: date | None = None
) -> PostDueResult:
    """Post every due occurrence exactly once.

    Idempotency is enforced twice: a unique (template_id, due_date) occurrence
    row and a deterministic transaction idempotency key. Re-running is safe.
    """
    through = through or date.today()
    if template_id is not None:
        templates = [get_template(db, template_id)]
    else:
        templates = list(
            db.scalars(
                select(RecurringTemplate).where(RecurringTemplate.is_active.is_(True))
            )
        )

    created_ids: list[uuid.UUID] = []
    skipped = 0
    for template in templates:
        due = template.next_due_date
        guard = 0
        last_posted: date | None = None
        while due <= through and (template.end_date is None or due <= template.end_date):
            guard += 1
            if guard > 120:
                break
            existing = db.scalar(
                select(RecurringOccurrence).where(
                    RecurringOccurrence.template_id == template.id,
                    RecurringOccurrence.due_date == due,
                )
            )
            if existing is not None:
                skipped += 1
                last_posted = due
                due = next_occurrence(due, template.frequency, template.interval_count)
                continue

            occurrence = RecurringOccurrence(
                template_id=template.id,
                due_date=due,
                status=OccurrenceStatus.PENDING,
            )
            savepoint = db.begin_nested()
            try:
                db.add(occurrence)
                db.flush()
                savepoint.commit()
            except IntegrityError:
                savepoint.rollback()
                skipped += 1
                last_posted = due
                due = next_occurrence(due, template.frequency, template.interval_count)
                continue

            payload = TransactionCreate(
                transaction_date=due,
                transaction_type=template.transaction_type,
                amount=template.amount,
                account_id=template.account_id,
                category_id=template.category_id,
                description=template.description,
                merchant_or_payee=template.merchant_or_payee,
                payment_method=template.payment_method,
                notes=template.notes,
                idempotency_key=f"recurring:{template.id}:{due.isoformat()}",
            )
            txn = create_transaction(db, payload, source="recurring", commit=False)
            occurrence.status = OccurrenceStatus.POSTED
            occurrence.transaction_id = txn.id
            created_ids.append(txn.id)
            last_posted = due
            due = next_occurrence(due, template.frequency, template.interval_count)

        if last_posted is not None:
            template.next_due_date = due
        template.updated_at = func.now()

    if created_ids:
        record_audit(
            db,
            entity_type="recurring_run",
            entity_id=None,
            action=AuditAction.CREATE,
            summary=f"Posted {len(created_ids)} recurring transaction(s)",
            changes={"transaction_ids": created_ids},
        )
    db.commit()
    return PostDueResult(
        created_count=len(created_ids),
        skipped_count=skipped,
        transactions=created_ids,
        message=(
            f"Posted {len(created_ids)} transaction(s). "
            f"Skipped {skipped} already-processed occurrence(s)."
        ),
    )


def skip_occurrence(
    db: Session, template_id: uuid.UUID, due_date: date
) -> RecurringRead:
    template = get_template(db, template_id)
    if due_date != template.next_due_date:
        raise ValidationError("Only the next due occurrence can be skipped.")
    existing = db.scalar(
        select(RecurringOccurrence).where(
            RecurringOccurrence.template_id == template.id,
            RecurringOccurrence.due_date == due_date,
        )
    )
    if existing is not None:
        raise ConflictError("This occurrence has already been processed.")
    db.add(
        RecurringOccurrence(
            template_id=template.id,
            due_date=due_date,
            status=OccurrenceStatus.SKIPPED,
        )
    )
    template.next_due_date = next_occurrence(
        due_date, template.frequency, template.interval_count
    )
    record_audit(
        db,
        entity_type="recurring_template",
        entity_id=template.id,
        action=AuditAction.UPDATE,
        summary=f"Skipped recurring occurrence on {due_date}",
    )
    db.commit()
    db.refresh(template)
    return serialize_template(template)


def occurrences(db: Session, template_id: uuid.UUID) -> list[OccurrenceRead]:
    get_template(db, template_id)
    rows = db.scalars(
        select(RecurringOccurrence)
        .where(RecurringOccurrence.template_id == template_id)
        .order_by(RecurringOccurrence.due_date.desc())
    )
    return [OccurrenceRead.model_validate(row) for row in rows]


def next_occurrence(due: date, frequency: RecurringFrequency, interval: int) -> date:
    if frequency == RecurringFrequency.WEEKLY:
        return due + timedelta(days=7 * interval)
    if frequency == RecurringFrequency.MONTHLY:
        return add_months(due, interval)
    if frequency == RecurringFrequency.QUARTERLY:
        return add_months(due, 3 * interval)
    return add_months(due, 12 * interval)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _validate_category(
    db: Session, category_id: uuid.UUID, transaction_type: TransactionType
) -> None:
    category = db.get(Category, category_id)
    if category is None:
        raise ValidationError("Category not found.")
    expected = (
        CategoryType.INCOME if transaction_type == TransactionType.INCOME else CategoryType.EXPENSE
    )
    if category.category_type != expected:
        raise ValidationError(f"Category must be an {expected.value} category.")
    if not category.is_active:
        raise ValidationError("Category is inactive.")


def due_count(db: Session) -> int:
    return len(upcoming(db, horizon_days=0, include_overdue=True))


def reminder_summary(db: Session) -> dict:
    items = upcoming(db, horizon_days=14)
    overdue = [item for item in items if item.is_overdue]
    return {
        "upcoming": items,
        "overdue_count": len(overdue),
        "due_count": len([item for item in items if item.due_date == date.today()]),
    }
