from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.audit import AuditLog
from app.models.enums import AuditAction
from app.services.backup import _validate_target
from tests.helpers import API


def test_backup_status_is_disabled_without_supabase_target(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(settings, "backup_database_url", None)
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))

    response = client.get(f"{API}/system/backup/status")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["configured"] is False
    assert body["can_backup"] is False
    assert "BACKUP_DATABASE_URL" in body["message"]


def test_backup_status_detects_changes_after_last_backup(
    client: TestClient, db: Session, monkeypatch, tmp_path
) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    dump = backup_dir / "supabase-public-20260101-000000.dump"
    dump.write_bytes(b"test dump")
    (backup_dir / "backup-state.json").write_text(
        json.dumps(
            {
                "backup_file": dump.name,
                "backup_at": "2026-01-01T00:00:00+00:00",
                "covered_through": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    db.add(
        AuditLog(
            entity_type="transaction",
            entity_id=None,
            action=AuditAction.CREATE,
            summary="Test change after backup",
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    db.commit()

    monkeypatch.setattr(
        settings,
        "backup_database_url",
        "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/personal_finance_backup",
    )
    monkeypatch.setattr(settings, "backup_dir", str(backup_dir))

    response = client.get(f"{API}/system/backup/status")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["configured"] is True
    assert body["backup_needed"] is True
    assert body["last_backup_file"] == dump.name
    assert body["last_change_at"].startswith("2026-01-02")
    assert "Changes have been made" in body["message"]


def test_backup_post_requires_supabase_target(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(settings, "backup_database_url", None)
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))

    response = client.post(f"{API}/system/backup")

    assert response.status_code == 422, response.text
    assert "BACKUP_DATABASE_URL" in response.json()["error"]["message"]


def test_backup_post_rejects_source_database(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(settings, "backup_database_url", settings.database_url)
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))

    response = client.post(f"{API}/system/backup")

    assert response.status_code == 422, response.text
    assert "same database" in response.json()["error"]["message"].lower()


def test_backup_target_allows_remote_postgres_database() -> None:
    _validate_target(
        make_url(
            "postgresql://postgres.project:secret@aws-0-region.pooler.supabase.com:5432/"
            "postgres?sslmode=require"
        )
    )


def test_backup_target_rejects_local_postgres_database() -> None:
    with pytest.raises(ValidationError, match="maintenance database"):
        _validate_target(
            make_url("postgresql://postgres:postgres123@127.0.0.1:5432/postgres")
        )
