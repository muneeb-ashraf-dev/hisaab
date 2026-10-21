from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Personal Finance API"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/personal_finance"
    )
    test_database_url: str | None = None
    # Local PostgreSQL target used by the manual backup button. Keep this
    # separate from DATABASE_URL when DATABASE_URL points at Supabase.
    local_database_url: str | None = None
    # Optional directory containing pg_dump/pg_restore. When unset the backend
    # searches PATH and the standard PostgreSQL installation folders.
    pg_bin: str | None = None
    backup_dir: str = str(PROJECT_ROOT / "backups")
    backup_keep: int = Field(default=30, ge=1, le=3650)
    api_auth_token: str | None = None
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    log_level: str = "INFO"
    currency: str = "PKR"
    # Baseline used by the idempotent seed command.
    baseline_date: str = "2026-11-01"

    @field_validator("api_auth_token", "local_database_url", "pg_bin", mode="before")
    @classmethod
    def empty_optional_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_auth_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
