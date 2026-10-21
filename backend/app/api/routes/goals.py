from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.common import Message
from app.schemas.goal import (
    ContributionCreate,
    GoalCreate,
    GoalRead,
    GoalUpdate,
)
from app.services import goals as goal_service

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalRead])
def list_goals(db: DbSession) -> list[GoalRead]:
    return goal_service.list_goals(db)


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(db: DbSession, payload: GoalCreate) -> GoalRead:
    return goal_service.create_goal(db, payload)


@router.get("/{goal_id}", response_model=GoalRead)
def get_goal(db: DbSession, goal_id: uuid.UUID) -> GoalRead:
    return goal_service.serialize_goal(db, goal_service.get_goal(db, goal_id))


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(db: DbSession, goal_id: uuid.UUID, payload: GoalUpdate) -> GoalRead:
    return goal_service.update_goal(db, goal_id, payload)


@router.delete("/{goal_id}", response_model=Message)
def delete_goal(db: DbSession, goal_id: uuid.UUID) -> Message:
    goal_service.delete_goal(db, goal_id)
    return Message(message="Goal deleted.")


@router.post("/{goal_id}/contributions", response_model=GoalRead)
def add_contribution(
    db: DbSession, goal_id: uuid.UUID, payload: ContributionCreate
) -> GoalRead:
    return goal_service.add_contribution(db, goal_id, payload)


@router.delete("/{goal_id}/contributions/{contribution_id}", response_model=GoalRead)
def delete_contribution(
    db: DbSession, goal_id: uuid.UUID, contribution_id: uuid.UUID
) -> GoalRead:
    return goal_service.delete_contribution(db, goal_id, contribution_id)
