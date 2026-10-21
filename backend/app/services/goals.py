from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import AuditAction, GoalStatus
from app.models.goal import FinancialGoal, GoalContribution
from app.schemas.goal import (
    ContributionCreate,
    ContributionRead,
    GoalCreate,
    GoalRead,
    GoalUpdate,
)
from app.services.audit import diff_changes, record_audit

ZERO = Decimal("0.00")


def get_goal(db: Session, goal_id: uuid.UUID) -> FinancialGoal:
    goal = db.get(FinancialGoal, goal_id)
    if goal is None:
        raise NotFoundError("Financial goal not found.")
    return goal


def _contribution_total(db: Session, goal_id: uuid.UUID) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(GoalContribution.amount), ZERO)).where(
            GoalContribution.goal_id == goal_id
        )
    )
    return Decimal(total or 0).quantize(Decimal("0.01"))


def serialize_goal(db: Session, goal: FinancialGoal) -> GoalRead:
    current = _contribution_total(db, goal.id)
    remaining = max(goal.target_amount - current, ZERO).quantize(Decimal("0.01"))
    progress = (
        float((current / goal.target_amount * 100).quantize(Decimal("0.1")))
        if goal.target_amount
        else 0.0
    )
    return GoalRead(
        id=goal.id,
        name=goal.name,
        target_amount=goal.target_amount,
        current_amount=current,
        remaining_amount=remaining,
        progress_pct=progress,
        target_date=goal.target_date,
        status=goal.status,
        notes=goal.notes,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
        contributions=[
            ContributionRead.model_validate(contribution)
            for contribution in sorted(
                goal.contributions, key=lambda item: item.contribution_date, reverse=True
            )
        ],
    )


def list_goals(db: Session) -> list[GoalRead]:
    goals = list(db.scalars(select(FinancialGoal).order_by(FinancialGoal.created_at.desc())))
    return [serialize_goal(db, goal) for goal in goals]


def create_goal(db: Session, payload: GoalCreate) -> GoalRead:
    _ensure_unique_name(db, payload.name)
    goal = FinancialGoal(**payload.model_dump())
    db.add(goal)
    db.flush()
    record_audit(
        db,
        entity_type="financial_goal",
        entity_id=goal.id,
        action=AuditAction.CREATE,
        summary=f"Created goal {goal.name}",
        changes=payload.model_dump(),
    )
    db.commit()
    db.refresh(goal)
    return serialize_goal(db, goal)


def update_goal(db: Session, goal_id: uuid.UUID, payload: GoalUpdate) -> GoalRead:
    goal = get_goal(db, goal_id)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != goal.name:
        _ensure_unique_name(db, updates["name"], exclude_id=goal.id)
    before = {key: getattr(goal, key) for key in updates}
    for key, value in updates.items():
        setattr(goal, key, value)
    changes = diff_changes(before, {key: getattr(goal, key) for key in updates})
    if changes:
        record_audit(
            db,
            entity_type="financial_goal",
            entity_id=goal.id,
            action=AuditAction.UPDATE,
            summary=f"Updated goal {goal.name}",
            changes=changes,
        )
    db.commit()
    db.refresh(goal)
    return serialize_goal(db, goal)


def delete_goal(db: Session, goal_id: uuid.UUID) -> None:
    goal = get_goal(db, goal_id)
    record_audit(
        db,
        entity_type="financial_goal",
        entity_id=goal.id,
        action=AuditAction.DELETE,
        summary=f"Deleted goal {goal.name}",
    )
    db.delete(goal)
    db.commit()


def add_contribution(
    db: Session, goal_id: uuid.UUID, payload: ContributionCreate
) -> GoalRead:
    goal = get_goal(db, goal_id)
    if goal.status == GoalStatus.CANCELLED:
        raise ValidationError("Cannot contribute to a cancelled goal.")
    contribution = GoalContribution(goal_id=goal.id, **payload.model_dump())
    db.add(contribution)
    db.flush()
    total = _contribution_total(db, goal.id)
    if total >= goal.target_amount:
        goal.status = GoalStatus.COMPLETED
    record_audit(
        db,
        entity_type="financial_goal",
        entity_id=goal.id,
        action=AuditAction.UPDATE,
        summary=f"Added {contribution.amount} to goal {goal.name}",
        changes={"contribution_id": contribution.id, "amount": contribution.amount},
    )
    db.commit()
    db.refresh(goal)
    return serialize_goal(db, goal)


def delete_contribution(db: Session, goal_id: uuid.UUID, contribution_id: uuid.UUID) -> GoalRead:
    goal = get_goal(db, goal_id)
    contribution = db.get(GoalContribution, contribution_id)
    if contribution is None or contribution.goal_id != goal.id:
        raise NotFoundError("Contribution not found.")
    db.delete(contribution)
    db.flush()
    total = _contribution_total(db, goal.id)
    if goal.status == GoalStatus.COMPLETED and total < goal.target_amount:
        goal.status = GoalStatus.ACTIVE
    record_audit(
        db,
        entity_type="financial_goal",
        entity_id=goal.id,
        action=AuditAction.UPDATE,
        summary=f"Removed contribution from goal {goal.name}",
        changes={"contribution_id": contribution.id, "amount": contribution.amount},
    )
    db.commit()
    db.refresh(goal)
    return serialize_goal(db, goal)


def _ensure_unique_name(
    db: Session, name: str, *, exclude_id: uuid.UUID | None = None
) -> None:
    from app.core.exceptions import ConflictError

    stmt = select(FinancialGoal.id).where(func.lower(FinancialGoal.name) == name.strip().lower())
    if exclude_id is not None:
        stmt = stmt.where(FinancialGoal.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("A goal with this name already exists.")


def goal_summary(db: Session) -> dict:
    goals = list_goals(db)
    active = [goal for goal in goals if goal.status == GoalStatus.ACTIVE]
    return {
        "total_goals": len(goals),
        "active_goals": len(active),
        "total_saved": sum((goal.current_amount or ZERO for goal in goals), ZERO),
        "total_target": sum((goal.target_amount for goal in goals), ZERO),
        "goals": goals,
        "as_of": datetime.now(UTC).isoformat(),
    }
