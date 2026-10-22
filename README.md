# Hisaab — Personal Finance & Expense Intelligence

A single-user personal finance workspace for three PKR accounts. It tracks income,
expenses, refunds, adjustments, internal transfers, budgets, savings goals and
recurring payments, then turns them into monthly, annual, category and account
reports.

The starting position is treated as an explicit **baseline**: original funds,
historical usage and the resulting opening balance. Historical usage is shown for
context but is never counted as income or spending in any report.

- **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4,
  shadcn/ui (Base UI), Recharts, Lucide, React Hook Form, Zod
- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- **Database:** PostgreSQL 18
- **Money:** `Decimal` in Python and `NUMERIC(14,2)` in PostgreSQL — never floats

---

## Contents

- [What is included](#what-is-included)
- [Baseline snapshot](#baseline-snapshot)
- [Local development](#local-development)
- [Local PostgreSQL and Supabase backup](#local-postgresql-and-supabase-backup)
- [Environment variables](#environment-variables)
- [Data model and invariants](#data-model-and-invariants)
- [CSV import and export](#csv-import-and-export)
- [Authentication](#authentication)
- [Testing](#testing)
- [Backup and restore](#backup-and-restore)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)

---

## What is included

| Area | Capabilities |
| --- | --- |
| Dashboard | KPIs (balance, income, spending, net cashflow, savings rate), cashflow chart, category split, account balances, recent activity, budgets, upcoming recurring payments. Date-range and account filters. |
| Transactions | Search, type/account/category filters, sorting, pagination, create/edit/delete/restore, soft-deleted view, CSV export. Refunds are created from the original expense and reduce net spending. |
| Transfers | Atomic movement between any two accounts in either direction, edit and delete with balance reversal. Never treated as income or expense; combined balance never changes. |
| Reports | Monthly summary, annual overview with per-account opening/closing balances, category breakdown and drill-down, per-account reports, analytics (trends, fixed vs variable, largest expenses, period comparison), CSV monthly report export. |
| Budgets | Overall and per-category envelopes, monthly/quarterly/yearly periods, warning thresholds, progress net of refunds. |
| Goals | Savings targets with dated contributions, progress and status. Contributions are planning records and do not move account balances. |
| Committees | Monthly committee plans with start/end month, installment amount, month-by-month schedule, already-paid installments and linked committee expenses. The plan itself is planning-only; linked expense transactions update paid months and appear in reports. |
| Recurring | Templates for weekly/monthly/quarterly/yearly payments, due reminders, post one or post all due, skip occurrence, optional auto-post. Posting is idempotent per due date. |
| Import / export | CSV preview with per-row validation and duplicate detection, commit of valid rows, missing-category creation, ledger export including transfers, monthly report export. |
| Settings | Account and category CRUD with deactivation/soft delete, baseline editor with reconciliation checks and itemized historical usage, audit log with filtering, system status, Supabase backup card and global backup reminder. |

Money is stored as `NUMERIC(14,2)` and serialized as decimal strings. The API uses
explicit lowercase enum values (`income`, `expense`, `adjustment_increase`, …) and
enforces them with database `CHECK` constraints.

---

## Baseline snapshot

Seeded by `python -m app.seed`, idempotently. The seed only creates missing
accounts, categories and the baseline; it never invents transactions.

The ledger starts from a clean position with no historical usage:

| Account | Original funds | Historical usage | Opening balance |
| --- | ---: | ---: | ---: |
| `salary-M` | 27,000.00 | 0.00 | 27,000.00 |
| `salary-A` | 0.00 | 0.00 | 0.00 |
| `savings` | 300,000.00 | 0.00 | 300,000.00 |
| **Total** | **327,000.00** | **0.00** | **327,000.00** |

The baseline date defaults to the day the seed runs (today unless
`BASELINE_DATE` is set) and is also each account's opening date. The Dashboard
always opens on the current month; the baseline date does not lock the reporting
period.

The Settings → Baseline editor still enforces `original funds = historical usage
+ opening balance` for every account. Opening balances appear only in baseline
context and never in monthly income, expense, category or account activity
reports.

---

## Local development

Requirements:

- Python **3.12+** and [`uv`](https://docs.astral.sh/uv/)
- Node.js **20.9+** and npm
- PostgreSQL **16+** (18 recommended), running on `127.0.0.1:5432`

### 1. Create the databases

Using the PostgreSQL superuser (`postgres` / `postgres123`):

```bash
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres
```

```sql
CREATE DATABASE personal_finance;
CREATE DATABASE personal_finance_test;
```

Both databases are required: the app uses `personal_finance`, and the pytest
suite uses `personal_finance_test`.

### 2. Configure the backend

```bash
cp .env.example .env
```

The defaults are already set up for the local PostgreSQL instance:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/personal_finance
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/personal_finance_test
APP_ENV=development
```

The backend reads `.env` from `backend/` and then the repository root, so either
location works. Change the credentials or port there if your PostgreSQL setup
differs.

The main database is always the local `DATABASE_URL`. Supabase is optional and is
used only as an off-site backup target. Add `BACKUP_DATABASE_URL` with the
Supabase Session Pooler URL when you want the **Back up now** button; see
[Local PostgreSQL and Supabase backup](#local-postgresql-and-supabase-backup).

### 3. Install, migrate and seed

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The seed is safe to run repeatedly and prints the reconciled opening total.

### 4. Run the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

On Windows PowerShell, use `npm.cmd run dev` if script execution policy blocks
`npm.ps1`. Open <http://localhost:3000>.

The Next.js server proxies `/api/proxy/*` to the backend. The browser never
receives the API token.

### Windows launchers

After the database is created, migrations have been applied and dependencies are
installed, Windows users can start the app by double-clicking:

- `start-app.bat` — opens the backend and frontend in separate windows, then
  opens <http://localhost:3000>.
- `start-backend.bat` — starts only the FastAPI server.
- `start-frontend.bat` — starts only the Next.js app; it runs `npm install` on the
  first launch if `node_modules` is missing.

Keep the `.bat` files in the project root next to `backend/` and `frontend/`.
The configured PostgreSQL database must already be running and reachable.

### Useful commands

```bash
# Backend
cd backend
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe change"
uv run python -m app.seed
uv run pytest -q
uv run ruff check .

# Frontend
cd frontend
npm run lint
npm run build
npm start
```

---

## Local PostgreSQL and Supabase backup

The local PostgreSQL database is the **main read/write database**. Supabase is
optional and is used only as an off-site recovery copy. This keeps normal
reads/writes fast because they never cross the network.

In `backend/.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/personal_finance
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/personal_finance_test
BACKUP_DATABASE_URL=postgresql+psycopg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

- `DATABASE_URL` must stay local. Run migrations and seed against it.
- `TEST_DATABASE_URL` must stay local. The test suite refuses to run against a
  database whose name does not end in `_test`.
- `BACKUP_DATABASE_URL` is the optional Supabase **Session Pooler** URL. Keep
  `?sslmode=require` and the `postgresql+psycopg://` prefix for the backend.
- `pg_dump`, `psql` and `pg_restore` need the native `postgresql://` form.
- Direct Supabase connections are IPv6-only by default; the Session Pooler is
  IPv4-compatible and works with this setup.

### Initial setup

```bash
cd backend
uv run alembic upgrade head
uv run python -m app.seed
```

Migrations change the local schema only. They do not copy data to Supabase. Use
Settings → System → **Supabase backup** → **Back up now** (or the endpoint
directly) when you want to refresh the off-site copy.

### Separate installations

Each independent copy (for example a family member's PC) should use its own local
`personal_finance` database and, if desired, its own Supabase backup project or
no Supabase target at all. Point `DATABASE_URL` at that local database and set a
separate `BACKUP_DATABASE_URL`; no code changes are needed.

Do not run two app instances as live writers against the same database. If you
need to recover, restore a dump into the local database instead of turning
Supabase into a second writer.

---

## Environment variables

| Variable | Used by | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | backend | `postgres@127.0.0.1:5432/personal_finance` | Main local PostgreSQL connection URL used for all reads and writes. |
| `BACKUP_DATABASE_URL` | backend | unset | Supabase Session Pooler URL. The **Back up now** button dumps the main database and restores it here. |
| `PG_BIN` | backend | auto-detect | Optional folder containing `pg_dump` and `pg_restore` (for example `C:\Program Files\PostgreSQL\18\bin`). |
| `BACKUP_DIR` | backend | `<repo>/backups` | Where backups write dumps and `backup-state.json`. |
| `BACKUP_KEEP` | backend | `30` | Number of newest dumps to retain. |
| `TEST_DATABASE_URL` | backend | — | Optional override for tests. `tests/conftest.py` hard-sets the test DB for safety. |
| `APP_ENV` | backend | `development` | `development`, `test` or `production`. |
| `API_AUTH_TOKEN` | backend + frontend | unset | When set, every `/api/v1` request requires `Authorization: Bearer <token>`. The frontend attaches it server-side. Leave blank for trusted local use. |
| `CORS_ORIGINS` | backend | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins. |
| `BASELINE_DATE` | backend seed | today | Opening date used when the baseline is first created. |
| `LOG_LEVEL` | backend | `INFO` | Python log level. |
| `API_BASE_URL` | frontend | `http://127.0.0.1:8000` | Backend base URL used by the Next.js proxy. |

Never commit `.env`; only `.env.example` is tracked.

---

## Data model and invariants

### Transactions

A transaction has an explicit type and a positive amount:

- `income` — increases the account.
- `expense` — decreases the account and counts as gross spending.
- `refund` — increases the account, must reference an expense, and may not exceed
  the expense's remaining refundable amount or predate it. Refunds reduce net
  spending and category totals.
- `adjustment_increase` / `adjustment_decrease` — correct the ledger without
  being reported as income or expense.

Every transaction stores `account_id`, an optional `category_id`, description,
merchant/payee, payment method, notes, source (`manual`, `import`, `recurring`)
and optional `related_transaction_id` for refunds.

Deleting is a soft delete (`deleted_at`, `deleted_reason`). Balance effects are
reversed immediately and the row can be restored; reports exclude deleted rows.
An audit log records creates, updates, deletes and restores.

### Transfers

A transfer is a **single row** referencing source and destination accounts. It is
applied atomically: both balances change in one database transaction, and the
combined balance is unchanged. Editing reverses the old movement and applies the
new one; deleting reverses both sides. Transfers never appear in income, expense
or category reports, but they do affect account closing balances and the ledger.

Transfers currently do **not** enforce a sufficient-funds check, so a source
account may go negative. This is documented in `backend/tests/README.md` and is
the one intentionally skipped test.

### Committees

A committee plan stores a name, monthly installment amount, starting month and
ending month. The total installment count and total amount are derived from the
period. If the committee started before you began using Hisaab, record the
historical installments as **already paid**; those months are planning data and
do not create ledger entries.

Future committee payments are ordinary expense transactions. Choose the
committee in the transaction form's **Committee plan** field, and the first
transaction in each new month marks that installment as paid on the committee
page. The committee page calculates paid months from the already-paid count plus
linked expense months through the selected month. The plan itself never creates
transactions, transfers or account balance changes; only the linked expense does,
so it appears in reports like any other expense.

### Reporting conventions

- Date ranges are inclusive.
- `expenses_net = expenses_gross − refunds`; budgets use net spending.
- Transfers are reported separately as `transfers_in` / `transfers_out`.
- Opening balances and historical usage never contribute to income or expenses;
  period reports before the opening date return zero activity.
- Per-account annual reports include the opening balance for periods that end
  after the account opened, so opening + activity = closing reconciles.
- Soft-deleted transactions and transfers are excluded everywhere.

### Idempotency

Transaction and transfer creates accept an optional `idempotency_key`, protected
by a partial unique index. Repeating a request with the same key returns the
existing record instead of posting twice. Recurring occurrences are unique per
template and due date.

---

## CSV import and export

### Format

Required columns:

```text
transaction_date, transaction_type, amount, account, description
```

Optional columns:

```text
category, merchant_or_payee, payment_method, notes
```

- Dates must be `YYYY-MM-DD`.
- `transaction_type` must be `income`, `expense`, `adjustment_increase` or
  `adjustment_decrease`. **Refunds are not importable directly**; import the
  original expense first, then create the refund in the UI.
- `account` and `category` are matched by name, case-insensitively.
- Amounts must be positive and parse as decimal values.

Sample:

```csv
transaction_date,transaction_type,amount,account,category,description,merchant_or_payee,payment_method,notes
2026-11-02,income,95000.00,salary-M,Salary,November salary,Employer,Bank transfer,
2026-11-03,expense,2450.50,salary-M,Food & Groceries,Weekly groceries,Metro,Debit card,
2026-11-05,expense,12000.00,salary-M,Bills & Utilities,Electricity bill,K-Electric,Online,
2026-11-10,income,15000.00,salary-A,Freelance,Landing page project,Client,,
```

Download the canonical template from the Import & Export page or
`GET /api/v1/imports/sample.csv`.

### Preview and commit

1. Upload a file on **Import & Export**. Nothing is written yet.
2. Preview shows every row as `ready`, `duplicate` or `invalid`, with a reason.
3. Adjust the flags:
   - **Skip duplicates** (default on) uses a content fingerprint over date,
     type, amount, account, description, merchant and payment method.
   - **Create missing categories** (default off) creates the missing category on
     the fly. Without it, unknown categories are rejected.
4. Commit writes only valid, non-duplicate rows. Each row uses a savepoint, so a
   bad row cannot roll back the whole batch.
5. The result reports created, skipped and rejected counts plus a batch ID.

Re-uploading the same file after a successful commit creates no new
transactions.

### Exports

- **Transactions CSV** — the full ledger (transactions and transfers) for the
  selected date range and account, excluding soft-deleted entries.
- **Monthly report CSV** — summary, account and category totals for one month.

API:

```text
GET /api/v1/exports/transactions.csv?start_date=2026-11-01&end_date=2026-11-30
GET /api/v1/exports/monthly-report.csv?year=2026&month=11
GET /api/v1/imports/sample.csv
```

---

## Authentication

This is a deliberately single-user application. There are no user accounts,
sessions or passwords.

- If `API_AUTH_TOKEN` is **empty**, the API relies on network isolation and is
  intended for `127.0.0.1`/private use only.
- If it is **set**, every `/api/v1/*` endpoint requires
  `Authorization: Bearer <token>`. `/health`, `/health/ready` and `/docs` remain
  public.
- The Next.js proxy (`frontend/src/app/api/proxy/[...path]/route.ts`) attaches the
  token server-side. It is never sent to the browser or embedded in client
  bundles.
- For a direct API call:

```bash
curl -H "Authorization: Bearer $API_AUTH_TOKEN" http://127.0.0.1:8000/api/v1/accounts
```

For anything beyond a trusted local machine, put the app behind HTTPS (reverse
proxy or tunnel) and set a long random token.

---

## Testing

### Backend

The suite uses a real PostgreSQL database and the FastAPI `TestClient`. It refuses
to run unless the database name ends with `_test`, drops/recreates tables once per
session, and truncates and re-seeds before each test.

```bash
cd backend
uv run pytest -q
uv run ruff check .
```

Requirements: PostgreSQL reachable at `127.0.0.1:5432`, role `postgres`, database
`personal_finance_test`. Do not run two test sessions concurrently.

Current result: **88 passed, 1 skipped** (the skipped test documents the missing
transfer funds check). Behaviour notes are in `backend/tests/README.md`.

Coverage includes baseline reconciliation and report exclusion, transaction
CRUD/refunds/idempotency, atomic transfers, all report types, budgets/goals/
committees/recurring, CSV preview/commit/duplicates/exports, API contracts, auth,
dashboard aggregations and backup safety checks.

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

The production build statically generates every page; all data fetching happens
client-side through the proxy.

### Manual smoke test

1. Dashboard opens on the current month and shows the 327,000 opening position
   with no opening balance in income/expense totals.
2. Create an expense, edit it, refund part of it, and confirm net spending falls.
3. Transfer between accounts and confirm the combined balance is unchanged.
4. Delete the transfer and confirm both balances are restored.
5. Create a budget and verify utilization uses net spending.
6. Create a goal and add a contribution; account balances must not change.
7. Create a committee plan (for example 19 monthly installments) and change the
   as-of month; confirm paid and remaining amounts and the schedule update
   without changing account balances.
8. Create and post a recurring template; confirm next due advances and a
   transaction appears with source `recurring`.
9. Import a CSV with one valid, one duplicate and one invalid row; commit and
   confirm only the valid row is written. Re-preview to confirm duplicates.
10. Save the baseline with a deliberate mismatch and confirm the validation error;
    then restore valid values.

---

## Backup and restore

### Backup directions

There are two independent recovery paths:

1. **Local file backup** - the main local database is dumped to a dated `.dump`
   file under `backups/`. This is the fastest recovery path.
2. **Supabase off-site backup** - the main local database is dumped and restored
   into Supabase. Use this when you want a copy that survives loss of the PC.

Both are point-in-time snapshots. Writes made after the latest backup are not
recovered or merged automatically.

### Local file backup script

`pg_dump` needs the native URL, not the SQLAlchemy `+psycopg` URL. The repository
includes `backup-local.ps1`, which reads `DATABASE_URL` from `backend/.env`,
writes a public-schema dump under `backups/`, and keeps the newest 30 dumps.
Schedule it daily with Task Scheduler if desired:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\PRJ-9-EXPENSE_TRACKER\backup-local.ps1"
```

The manual equivalent is:

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
$env:PGPASSWORD = 'postgres123'
pg_dump "postgresql://postgres@127.0.0.1:5432/personal_finance" --schema=public -Fc -f "backups\postgres-public-$(Get-Date -Format yyyyMMdd-HHmm).dump"
```

Use `--schema=public` so the dump contains only the application tables. The
custom-format dump includes the schema, accounts, baseline, usage items,
transactions, transfers, budgets, goals, committees, recurring templates, audit
logs and soft-deleted rows.

### In-app Supabase backup button and reminder

Settings -> **System** contains a **Supabase backup** card. It shows the main
local source, the Supabase target, the latest backup time and the latest data
change. **Back up now**:

1. Runs `pg_dump --schema=public` against the main local `DATABASE_URL`.
2. Writes a dated dump under `backups/`.
3. Restores it into `BACKUP_DATABASE_URL` with `--clean --if-exists
   --single-transaction` and verifies row counts.
4. Stores `backups/backup-state.json` so the app knows what was covered.

The main local database is not changed by this operation. Supabase's `public`
schema is replaced with the local snapshot; do not edit data in Supabase and
expect it to be merged back. Each PC needs `pg_dump`/`pg_restore` available. The
backend searches `PATH`, the standard Windows PostgreSQL folders, then `PG_BIN`
if set.

After any successful create/update/delete/import, the frontend dispatches a
data-changed event. The global banner also polls every 30 seconds and on window
focus. If the main database has audit-log changes newer than the last Supabase
backup, the banner appears on every session with a **Back up now** button. The
banner can be dismissed for the current change, but it returns when new changes
arrive or on the next session.

This is still a point-in-time copy, not continuous replication. If the local
database is lost, restore the newest local dump or dump Supabase back into the
local database:

```powershell
# Dump Supabase (native postgresql:// URL)
$env:PGPASSWORD = '<supabase-db-password>'
pg_dump "postgresql://postgres.<project-ref>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require" --schema=public -Fc -f "backups\supabase-recovery.dump"

# Restore into the local database (stop the app first)
pg_restore -h 127.0.0.1 -p 5432 -U postgres --no-owner --no-privileges --clean --if-exists --single-transaction -d personal_finance "backups\supabase-recovery.dump"
```

The public-schema dump contains `CREATE SCHEMA public`, so keep `--clean
--if-exists` when restoring into a database whose `public` schema already exists.
Do not run Supabase as a second live writer.

### Rehearsing a restore to another local database

```powershell
createdb -h 127.0.0.1 -p 5432 -U postgres personal_finance_recovery
pg_restore -h 127.0.0.1 -p 5432 -U postgres --no-owner --no-privileges --clean --if-exists -d personal_finance_recovery "backups\postgres-public-YYYYMMDD-HHmm.dump"
```

Verify the row counts, then point `DATABASE_URL` at that database if you need to
run from the backup.

### CSV backup

Export the full ledger from **Import & Export** before bulk edits or migrations.
CSV preserves transactions and transfers but not budgets, goals, recurring
templates, audit history or soft-deleted rows.

---

## Project layout

```text
.
├── .env.example
├── backup-local.bat
├── backup-local.ps1
├── start-app.bat
├── start-backend.bat
├── start-frontend.bat
├── backups/                 # ignored; dumps + backup-state.json
├── backend/
│   ├── app/
│   │   ├── api/            # routes, dependencies, auth, error handling
│   │   ├── core/           # settings, database, exceptions, security
│   │   ├── models/         # SQLAlchemy models
│   │   ├── reports/        # reporting calculations
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # transactions, transfers, budgets, CSV, recurring…
│   │   ├── main.py         # FastAPI app
│   │   └── seed.py         # idempotent accounts/categories/baseline seed
│   ├── migrations/         # Alembic
│   ├── tests/              # pytest suite and behaviour notes
│   └── pyproject.toml      # uv-managed dependencies
└── frontend/
    ├── src/app/            # dashboard, transactions, transfers, reports,
    │                       # budgets, goals, recurring, import-export, settings
    ├── src/components/     # layout, forms, charts, shadcn/ui primitives
    ├── src/lib/            # API client, hooks, formatting, types
    ├── src/app/api/proxy/  # server-side API proxy
    └── package.json
```

The API is documented interactively at `/docs` and `/redoc`.

---

## Troubleshooting

**Dashboard opens on an empty month.**  
The dashboard always opens on the current month. If the account opening date is
later than today, use the period selector to move between months. Reports before
the opening date intentionally show zero activity.

**`psql`/backend cannot connect.**  
Confirm PostgreSQL is listening on `127.0.0.1:5432` and that `DATABASE_URL` uses
the `postgres` role and password configured on your machine.

**Supabase backup fails.**  
Normal app traffic uses the local `DATABASE_URL`; a Supabase failure should not
make the app slow or unavailable. For the backup button, set
`BACKUP_DATABASE_URL` to the Session Pooler host on port `5432` with
`?sslmode=require`. The backend needs `postgresql+psycopg://`; `psql`, `pg_dump`
and `pg_restore` need the native `postgresql://` form. If the button fails, check
that the password is in `PGPASSWORD` and that the URL does not contain
`+psycopg`.

**`uv` is not recognized.**  
Install it from <https://docs.astral.sh/uv/> and ensure `~/.local/bin` is on
`PATH` (on Windows: `C:\Users\<you>\.local\bin`).

**Tests hang or truncation blocks.**  
Only one pytest session may use `personal_finance_test` at a time. Stop other
runs, then retry.

**Frontend says the finance API is unreachable.**  
Start the backend and confirm `http://127.0.0.1:8000/health` returns `ok`.
Make sure `API_BASE_URL` points at the running backend.

**PowerShell blocks npm.**  
Use `npm.cmd run dev` / `npm.cmd run build` instead of `npm.ps1`.

**A transfer made an account negative.**  
This is currently allowed by design; there is no sufficient-funds check. Adjust
the transfer or record a deposit. See `backend/tests/README.md`.
