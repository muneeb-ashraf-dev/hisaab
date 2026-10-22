from __future__ import annotations

import math

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DbSession, PageDep
from app.core.config import settings
from app.models.audit import AuditLog
from app.schemas.common import Page, PageMeta
from app.schemas.system import AuditLogRead, BackupResult, BackupStatus, SettingsStatus
from app.services import backup as backup_service

router = APIRouter(tags=["system"])


@router.get("/system/status", response_model=SettingsStatus)
def system_status(db: DbSession) -> SettingsStatus:
    connected = True
    try:
        db.execute(select(1))
    except Exception:
        connected = False
    from app.services.baseline import get_baseline

    baseline_date = settings.baseline_date
    try:
        baseline_date = get_baseline(db).baseline_date.isoformat()
    except Exception:
        pass
    return SettingsStatus(
        app_name=settings.app_name,
        app_env=settings.app_env,
        currency=settings.currency,
        auth_enabled=settings.auth_enabled,
        baseline_date=baseline_date,
        database_connected=connected,
    )


@router.get("/system/backup/status", response_model=BackupStatus)
def backup_status(db: DbSession) -> BackupStatus:
    return backup_service.get_backup_status(db)


@router.post("/system/backup", response_model=BackupResult)
def create_supabase_backup(db: DbSession) -> BackupResult:
    return backup_service.create_backup(db)


@router.get("/audit-logs", response_model=Page[AuditLogRead])
def list_audit_logs(
    db: DbSession,
    page: PageDep,
    entity_type: str | None = Query(default=None, max_length=50),
) -> Page[AuditLogRead]:
    conditions = []
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
    logs = list(
        db.scalars(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset((page.page - 1) * page.page_size)
            .limit(page.page_size)
        )
    )
    return Page(
        items=[AuditLogRead.model_validate(log) for log in logs],
        meta=PageMeta(
            page=page.page,
            page_size=page.page_size,
            total=total,
            total_pages=max(math.ceil(total / page.page_size), 1),
        ),
    )
