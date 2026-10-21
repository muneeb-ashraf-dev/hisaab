from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.baseline import BaselineRead, BaselineUpdate
from app.services import baseline as baseline_service

router = APIRouter(prefix="/baseline", tags=["baseline"])


@router.get("", response_model=BaselineRead)
def get_baseline(db: DbSession) -> BaselineRead:
    return baseline_service.serialize_baseline(baseline_service.get_baseline(db))


@router.put("", response_model=BaselineRead)
def update_baseline(db: DbSession, payload: BaselineUpdate) -> BaselineRead:
    return baseline_service.update_baseline(db, payload)


@router.get("/summary")
def get_baseline_summary(db: DbSession) -> dict:
    return baseline_service.baseline_summary(db)
