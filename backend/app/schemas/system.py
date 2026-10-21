from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AuditAction
from app.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID | None
    action: AuditAction
    summary: str
    changes: dict | None
    notes: str | None
    created_at: datetime


class SettingsStatus(BaseModel):
    app_name: str
    app_env: str
    currency: str
    auth_enabled: bool
    baseline_date: str
    database_connected: bool
    version: str = "1.0.0"


class BackupStatus(BaseModel):
    configured: bool
    pg_tools_available: bool
    can_backup: bool
    backup_needed: bool
    backup_running: bool
    source_host: str | None = None
    source_database: str | None = None
    target_host: str | None = None
    target_database: str | None = None
    last_backup_at: datetime | None = None
    last_backup_file: str | None = None
    last_backup_size_bytes: int | None = None
    last_change_at: datetime | None = None
    covered_through: datetime | None = None
    message: str


class BackupResult(BaseModel):
    backup_at: datetime
    backup_file: str
    size_bytes: int
    duration_seconds: float
    covered_through: datetime | None = None
    target_database: str
    counts: dict[str, int]
