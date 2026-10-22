from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.committee import Committee
from app.models.enums import AuditAction, TransactionType
from app.models.transaction import Transaction
from app.schemas.committee import (
    CommitteeCreate,
    CommitteeRead,
    CommitteeScheduleItem,
    CommitteeUpdate,
)
from app.services.audit import diff_changes, record_audit

ZERO = Decimal("0.00")


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, months: int) -> date:
    total = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(total, 12)
    return date(year, month_index + 1, 1)


def _month_end(value: date) -> date:
    return _add_months(_month_start(value), 1) - timedelta(days=1)


def month_count(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def get_committee(db: Session, committee_id: uuid.UUID) -> Committee:
    committee = db.get(Committee, committee_id)
    if committee is None:
        raise NotFoundError("Committee not found.")
    return committee


def _linked_payments(
    db: Session, committee: Committee, through: date
) -> dict[date, Decimal]:
    """Return linked expense totals keyed by the first day of their month."""
    if through < committee.start_month:
        return {}
    rows = db.execute(
        select(Transaction.transaction_date, Transaction.amount).where(
            Transaction.committee_id == committee.id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.deleted_at.is_(None),
            Transaction.transaction_date >= committee.start_month,
            Transaction.transaction_date <= min(through, committee.end_month),
        )
    ).all()
    totals: dict[date, Decimal] = {}
    for transaction_date, amount in rows:
        month = _month_start(transaction_date)
        totals[month] = _money(totals.get(month, ZERO) + Decimal(amount))
    return totals


def serialize_committee(
    db: Session, committee: Committee, as_of: date | None = None
) -> CommitteeRead:
    current_month = _month_start(as_of or date.today())
    total = month_count(committee.start_month, committee.end_month)
    prior_paid = min(committee.prior_paid_installments, total)
    prior_months = {_add_months(committee.start_month, index) for index in range(prior_paid)}

    linked_by_month = _linked_payments(
        db, committee, through=min(_month_end(current_month), committee.end_month)
    )
    linked_paid = {
        month: amount for month, amount in linked_by_month.items() if month not in prior_months
    }
    paid_months = prior_months | set(linked_paid)
    paid = min(len(paid_months), total)

    total_amount = _money(committee.monthly_amount * total)
    linked_amount = _money(sum(linked_paid.values(), ZERO))
    total_paid = _money(committee.monthly_amount * prior_paid + linked_amount)
    remaining = max(total - paid, 0)
    remaining_amount = max(_money(total_amount - total_paid), ZERO)
    progress = float((Decimal(paid) / Decimal(total) * 100).quantize(Decimal("0.1")))

    schedule: list[CommitteeScheduleItem] = []
    for index in range(total):
        month = _add_months(committee.start_month, index)
        if month in prior_months:
            source: Literal["prior", "transaction"] | None = "prior"
            paid_amount = committee.monthly_amount
        elif month in linked_paid:
            source = "transaction"
            paid_amount = linked_paid[month]
        else:
            source = None
            paid_amount = ZERO
        schedule.append(
            CommitteeScheduleItem(
                month=month,
                installment_number=index + 1,
                amount=committee.monthly_amount,
                paid_amount=_money(paid_amount),
                status="paid" if source else "upcoming",
                source=source,
                is_current=month == current_month,
            )
        )

    return CommitteeRead(
        id=committee.id,
        name=committee.name,
        monthly_amount=committee.monthly_amount,
        start_month=committee.start_month,
        end_month=committee.end_month,
        prior_paid_installments=committee.prior_paid_installments,
        notes=committee.notes,
        total_installments=total,
        total_amount=total_amount,
        paid_installments=paid,
        linked_paid_installments=len(linked_paid),
        total_paid=total_paid,
        remaining_installments=remaining,
        remaining_amount=remaining_amount,
        current_month=current_month,
        progress_pct=progress,
        schedule=schedule,
        created_at=committee.created_at,
        updated_at=committee.updated_at,
    )


def list_committees(db: Session, as_of: date | None = None) -> list[CommitteeRead]:
    committees = list(
        db.scalars(
            select(Committee).order_by(
                Committee.start_month.desc(), Committee.created_at.desc()
            )
        )
    )
    return [serialize_committee(db, committee, as_of=as_of) for committee in committees]


def create_committee(db: Session, payload: CommitteeCreate) -> CommitteeRead:
    committee = Committee(**payload.model_dump())
    db.add(committee)
    db.flush()
    record_audit(
        db,
        entity_type="committee",
        entity_id=committee.id,
        action=AuditAction.CREATE,
        summary=f"Created committee {committee.name}",
        changes=payload.model_dump(),
    )
    db.commit()
    db.refresh(committee)
    return serialize_committee(db, committee)


def update_committee(
    db: Session, committee_id: uuid.UUID, payload: CommitteeUpdate
) -> CommitteeRead:
    committee = get_committee(db, committee_id)
    updates = payload.model_dump(exclude_unset=True)
    for field in (
        "name",
        "monthly_amount",
        "start_month",
        "end_month",
        "prior_paid_installments",
    ):
        if field in updates and updates[field] is None:
            raise ValidationError(f"{field} cannot be null.")

    start = updates.get("start_month", committee.start_month)
    end = updates.get("end_month", committee.end_month)
    if end < start:
        raise ValidationError("end_month must be on or after start_month.")
    total = month_count(start, end)
    if total > 600:
        raise ValidationError("committee period cannot exceed 600 months.")
    prior_paid = updates.get("prior_paid_installments", committee.prior_paid_installments)
    if prior_paid > total:
        raise ValidationError("prior_paid_installments cannot exceed the plan length.")

    before = {key: getattr(committee, key) for key in updates}
    for key, value in updates.items():
        setattr(committee, key, value)
    changes = diff_changes(before, {key: getattr(committee, key) for key in updates})
    if changes:
        record_audit(
            db,
            entity_type="committee",
            entity_id=committee.id,
            action=AuditAction.UPDATE,
            summary=f"Updated committee {committee.name}",
            changes=changes,
        )
    db.commit()
    db.refresh(committee)
    return serialize_committee(db, committee)


def delete_committee(db: Session, committee_id: uuid.UUID) -> None:
    committee = get_committee(db, committee_id)
    record_audit(
        db,
        entity_type="committee",
        entity_id=committee.id,
        action=AuditAction.DELETE,
        summary=f"Deleted committee {committee.name}",
    )
    db.delete(committee)
    db.commit()
