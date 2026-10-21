# Personal Finance API

FastAPI backend for the Hisaab personal finance workspace. See the
[root README](../README.md) for the full setup, baseline figures, CSV format,
authentication and backup instructions.

## Run

```bash
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- OpenAPI: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>
- Readiness: <http://127.0.0.1:8000/health/ready>

## Test

```bash
uv run pytest -q
uv run ruff check .
```

The suite requires PostgreSQL and the `personal_finance_test` database. It refuses
to run against any database whose name does not end in `_test`. See
[`tests/README.md`](tests/README.md) for fixtures and behaviour notes.

## Configuration

Settings are read from the environment and `.env` files (backend directory, then
repository root). The most important values are `DATABASE_URL`,
`API_AUTH_TOKEN`, `CORS_ORIGINS` and `BASELINE_DATE`. Defaults target local
PostgreSQL on `127.0.0.1:5432` with role `postgres` and password `postgres123`.

For the shared setup, set `DATABASE_URL` to Supabase's Session Pooler URL (keep
the local `TEST_DATABASE_URL`), run migrations and seed once against that shared
database, and do not run them again from each person's machine. See the root
README's "Shared Supabase database" section.

Set `LOCAL_DATABASE_URL` to this PC's local `personal_finance` database to enable
Settings → **System** → **Local backup**. That button writes a public-schema dump
to `../backups/` and restores it into the local target with `pg_restore`. It needs
`pg_dump` and `pg_restore` on `PATH`, in a standard PostgreSQL install folder, or
in `PG_BIN`. The status endpoint compares the newest dump with the newest audit
log, which drives the global backup reminder. `BACKUP_KEEP` controls retention
(default 30).

## Design notes

- Money is `Decimal` end to end and `NUMERIC(14,2)` in the database.
- Transactions carry an explicit type; refunds link to the original expense.
- Transfers are a single row applied atomically to both accounts.
- Historical baseline usage is excluded from every income/expense report.
- Deletes are soft deletes; an audit log records every mutation.
