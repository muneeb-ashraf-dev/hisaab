from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.api.deps import DbSession, resolve_range
from app.schemas.dashboard import DashboardOverview
from app.services.dashboard import dashboard_overview

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOverview)
def get_dashboard(
    db: DbSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> DashboardOverview:
    start, end = resolve_range(start_date, end_date)
    return dashboard_overview(db, start_date=start, end_date=end)
