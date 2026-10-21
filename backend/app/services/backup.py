from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError, ConflictError, ValidationError
from app.models.audit import AuditLog
from app.schemas.system import BackupResult, BackupStatus

logger = logging.getLogger("personal_finance.backup")

BACKUP_LOCK = threading.Lock()
DUMP_PREFIX = "supabase-public-"
STATE_FILE = "backup-state.json"
COUNTED_TABLES = (
    "accounts",
    "categories",
    "baseline_snapshots",
    "baseline_accounts",
    "baseline_usage_items",
    "transactions",
    "transfers",
    "budgets",
    "financial_goals",
    "goal_contributions",
    "recurring_templates",
    "recurring_occurrences",
    "import_batches",
    "audit_logs",
)


def _resolve_backup_dir() -> Path:
    return Path(settings.backup_dir).expanduser().resolve()


def _parse_url(value: str | None, label: str) -> URL | None:
    if not value:
        return None
    try:
        url = make_url(value)
    except Exception as exc:  # pragma: no cover - defensive for malformed env
        raise ValidationError(f"{label} is not a valid database URL.") from exc
    if not url.drivername.startswith("postgresql"):
        raise ValidationError(f"{label} must be a PostgreSQL URL.")
    return url


def _source_url() -> URL:
    url = _parse_url(settings.database_url, "DATABASE_URL")
    if url is None:  # pragma: no cover - settings always has a default
        raise ValidationError("DATABASE_URL is not configured.")
    return url


def _target_url() -> URL | None:
    return _parse_url(settings.local_database_url, "LOCAL_DATABASE_URL")


def _same_database(source: URL, target: URL) -> bool:
    return (
        (source.host or "").lower() == (target.host or "").lower()
        and (source.port or 5432) == (target.port or 5432)
        and (source.database or "") == (target.database or "")
    )


def _validate_target(target: URL) -> None:
    database = target.database or ""
    if not database:
        raise ValidationError("LOCAL_DATABASE_URL must include a database name.")
    if database.endswith("_test"):
        raise ValidationError("Refusing to restore a backup into a test database.")
    if database in {"postgres", "template0", "template1"}:
        raise ValidationError("Choose a normal application database as the local backup target.")


def _connection_args(url: URL) -> list[str]:
    if not url.host or not url.username or not url.database:
        raise ValidationError(
            "LOCAL_DATABASE_URL and DATABASE_URL must include a host, username and database."
        )
    return [
        "-h",
        url.host,
        "-p",
        str(url.port or 5432),
        "-U",
        url.username,
        "-d",
        url.database,
    ]


def _pg_env(url: URL) -> dict[str, str]:
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = str(url.password)
    sslmode = url.query.get("sslmode")
    if sslmode:
        env["PGSSLMODE"] = str(sslmode)
    env["PGCONNECT_TIMEOUT"] = "15"
    return env


def _find_pg_tool(name: str) -> str | None:
    executable = f"{name}.exe" if os.name == "nt" else name
    if settings.pg_bin:
        candidate = Path(settings.pg_bin).expanduser() / executable
        if candidate.is_file():
            return str(candidate)

    found = shutil.which(name) or (shutil.which(executable) if os.name == "nt" else None)
    if found:
        return found

    if os.name == "nt":
        for version in ("18", "17", "16", "15", "14"):
            candidate = Path(rf"C:\Program Files\PostgreSQL\{version}\bin") / executable
            if candidate.is_file():
                return str(candidate)
    return None


def _run_pg_tool(
    tool: str,
    args: list[str],
    url: URL,
    *,
    timeout: int,
) -> None:
    command = [tool, "-w", *args]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=_pg_env(url),
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(
            f"{Path(tool).name} timed out after {timeout} seconds.",
            status_code=504,
            code="backup_timeout",
        ) from exc
    except OSError as exc:
        raise AppError(
            f"Could not start {Path(tool).name}: {exc}",
            status_code=503,
            code="backup_unavailable",
        ) from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if len(detail) > 800:
            detail = f"{detail[:800]}â€¦"
        raise AppError(
            f"{Path(tool).name} failed. {detail or 'No error output was returned.'}",
            status_code=500,
            code="backup_failed",
        )


def _ensure_database(url: URL) -> None:
    _validate_target(url)
    admin = url.set(drivername="postgresql", database="postgres")
    dsn = admin.render_as_string(hide_password=False)
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=15) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (url.database,),
            ).fetchone()
            if not exists:
                connection.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database or ""))
                )
    except psycopg.Error as exc:
        raise AppError(
            f"The local PostgreSQL database could not be prepared: {exc}",
            status_code=503,
            code="backup_unavailable",
        ) from exc


def _read_state(backup_dir: Path) -> dict[str, Any] | None:
    path = backup_dir / STATE_FILE
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_state(backup_dir: Path, payload: dict[str, Any]) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / STATE_FILE
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _latest_dump(backup_dir: Path) -> Path | None:
    if not backup_dir.is_dir():
        return None
    dumps = sorted(
        backup_dir.glob(f"{DUMP_PREFIX}*.dump"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return dumps[0] if dumps else None


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _latest_change(db: Session) -> datetime | None:
    value = db.scalar(select(func.max(AuditLog.created_at)))
    return _as_utc(value)


def _count_rows(target: URL) -> dict[str, int]:
    engine = create_engine(
        target.set(drivername="postgresql+psycopg"),
        pool_pre_ping=True,
        future=True,
    )
    try:
        with engine.connect() as connection:
            return {
                table: int(
                    connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
                )
                for table in COUNTED_TABLES
            }
    finally:
        engine.dispose()


def get_backup_status(db: Session) -> BackupStatus:
    source = _source_url()
    target = _target_url()
    backup_dir = _resolve_backup_dir()
    latest = _latest_dump(backup_dir)
    state = _read_state(backup_dir)
    pg_dump = _find_pg_tool("pg_dump")
    pg_restore = _find_pg_tool("pg_restore")
    pg_tools_available = bool(pg_dump and pg_restore)

    configured = bool(target and not _same_database(source, target))
    last_backup_at: datetime | None = None
    last_backup_file: str | None = None
    last_backup_size_bytes: int | None = None
    covered_through: datetime | None = None

    if latest is not None:
        info = latest.stat()
        last_backup_at = datetime.fromtimestamp(info.st_mtime, tz=UTC)
        last_backup_file = latest.name
        last_backup_size_bytes = info.st_size
        covered_through = last_backup_at

        if state and state.get("backup_file") == latest.name:
            state_backup_at = _parse_datetime(state.get("backup_at"))
            if state_backup_at:
                last_backup_at = state_backup_at
            covered_through = _parse_datetime(state.get("covered_through")) or covered_through

    last_change_at = _latest_change(db)
    if latest is None:
        backup_needed = True
    elif last_change_at is not None and (
        covered_through is None or last_change_at > covered_through
    ):
        backup_needed = True
    else:
        backup_needed = False

    running = BACKUP_LOCK.locked()
    can_backup = configured and pg_tools_available
    if target is None:
        message = (
            "Local backup is not configured. Set LOCAL_DATABASE_URL in backend/.env "
            "to this machine's PostgreSQL database."
        )
    elif _same_database(source, target):
        message = (
            "The app is already using the local database; no separate local backup "
            "target is needed."
        )
    elif not pg_tools_available:
        message = (
            "PostgreSQL client tools were not found. Install PostgreSQL or set PG_BIN "
            "to the folder containing pg_dump and pg_restore."
        )
    elif running:
        message = "A local backup is currently running."
    elif latest is None:
        message = "No local backup has been created yet."
    elif backup_needed:
        message = "Changes have been made since the last local backup."
    else:
        message = "The local backup is up to date."

    return BackupStatus(
        configured=configured,
        pg_tools_available=pg_tools_available,
        can_backup=can_backup,
        backup_needed=backup_needed,
        backup_running=running,
        source_host=source.host,
        source_database=source.database,
        target_host=target.host if target else None,
        target_database=target.database if target else None,
        last_backup_at=last_backup_at,
        last_backup_file=last_backup_file,
        last_backup_size_bytes=last_backup_size_bytes,
        last_change_at=last_change_at,
        covered_through=covered_through,
        message=message,
    )


def create_backup(db: Session) -> BackupResult:
    source = _source_url()
    target = _target_url()
    if target is None:
        raise ValidationError(
            "Local backup is not configured. Set LOCAL_DATABASE_URL in backend/.env."
        )
    if _same_database(source, target):
        raise ValidationError(
            "LOCAL_DATABASE_URL points at the same database as DATABASE_URL. "
            "Set it to this machine's local PostgreSQL database."
        )
    _validate_target(target)

    pg_dump = _find_pg_tool("pg_dump")
    pg_restore = _find_pg_tool("pg_restore")
    if not pg_dump or not pg_restore:
        raise AppError(
            "pg_dump and pg_restore are required for local backups. Install PostgreSQL "
            "or set PG_BIN in backend/.env.",
            status_code=503,
            code="backup_unavailable",
        )

    if not BACKUP_LOCK.acquire(blocking=False):
        raise ConflictError("A local backup is already running.")

    backup_dir = _resolve_backup_dir()
    temporary: Path | None = None
    started = time.perf_counter()
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        covered_through = _latest_change(db)
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        final = backup_dir / f"{DUMP_PREFIX}{timestamp}.dump"
        counter = 1
        while final.exists():
            final = backup_dir / f"{DUMP_PREFIX}{timestamp}-{counter}.dump"
            counter += 1
        temporary = final.with_name(f"{final.name}.part")

        _run_pg_tool(
            pg_dump,
            [
                *_connection_args(source),
                "--schema=public",
                "--format=custom",
                "--file",
                str(temporary),
            ],
            source,
            timeout=300,
        )
        _ensure_database(target)
        _run_pg_tool(
            pg_restore,
            [
                *_connection_args(target),
                "--no-owner",
                "--no-privileges",
                "--clean",
                "--if-exists",
                "--single-transaction",
                str(temporary),
            ],
            target,
            timeout=600,
        )
        temporary.replace(final)

        completed_at = datetime.now(UTC)
        counts = _count_rows(target)
        _write_state(
            backup_dir,
            {
                "backup_at": completed_at.isoformat(),
                "backup_file": final.name,
                "covered_through": covered_through.isoformat() if covered_through else None,
                "source_host": source.host,
                "source_database": source.database,
                "target_host": target.host,
                "target_database": target.database,
                "counts": counts,
            },
        )

        old_dumps = sorted(
            backup_dir.glob(f"{DUMP_PREFIX}*.dump"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[settings.backup_keep :]
        for old_dump in old_dumps:
            old_dump.unlink(missing_ok=True)

        size_bytes = final.stat().st_size
        duration = time.perf_counter() - started
        logger.info(
            "Local backup completed: %s (%s bytes, %.1fs, %s)",
            final.name,
            size_bytes,
            duration,
            target.database,
        )
        return BackupResult(
            backup_at=completed_at,
            backup_file=final.name,
            size_bytes=size_bytes,
            duration_seconds=round(duration, 2),
            covered_through=covered_through,
            target_database=target.database or "",
            counts=counts,
        )
    except Exception:
        if temporary is not None and temporary.exists():
            temporary.unlink(missing_ok=True)
        raise
    finally:
        BACKUP_LOCK.release()
