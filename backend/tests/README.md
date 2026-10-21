# API test suite

Pytest tests for the personal-finance FastAPI application. They exercise the
real HTTP API (through `fastapi.testclient.TestClient`) against a real
PostgreSQL database. Application code, models, migrations and the development
database are never modified.

## Safety guard

`conftest.py` installs the following settings **before importing any `app`
module**:

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/personal_finance_test
APP_ENV=test
API_AUTH_TOKEN=<unset>
```

After the engine is created, the suite verifies that the connected database name
ends with `_test` and raises `RuntimeError` otherwise. This prevents an
accidental run against `personal_finance`.

The suite owns the `personal_finance_test` schema: at session start it runs
`drop_all` / `create_all`, and before every test it truncates every table and
re-seeds the baseline. Any data in that database is disposable. Do not run two
pytest sessions against the same test database concurrently — the truncate and
DDL statements will block or deadlock.

## Prerequisites

* PostgreSQL reachable at `127.0.0.1:5432`
* Role `postgres` with password `postgres123`
* Database `personal_finance_test` (must already exist; the suite creates tables,
  not the database)

## Running

From `backend/`:

```powershell
uv run pytest -q
uv run ruff check tests
```

`pyproject.toml` sets `addopts = "-q --disable-warnings"`. Use
`uv run pytest -o addopts="" -q -ra` when you want the pass/skip summary line.

Current result: **73 passed, 1 skipped**.

## Fixture lifecycle

* `_schema` (session, autouse) – drop and recreate all tables once.
* `_reset_database` (function, autouse) – `TRUNCATE ... RESTART IDENTITY
  CASCADE`, then seed the deterministic baseline. Every test starts from the
  same state.
* `client` – `TestClient` with application lifespan enabled.
* `db` – SQLAlchemy session for assertions that are easier to make directly
  against the database.
* `accounts` / `account_ids` – account-name to UUID mapping.
* `categories` / `category_ids` – category-name to UUID mapping.
* `make_transaction`, `make_transfer` – API helpers with Nov-2026 defaults.
* `balance_of` – reads an account's current balance through
  `GET /api/v1/accounts/{id}`, so the result is never stale ORM identity-map
  data.
* `month_params` – November 2026 date-range query parameters.

### Baseline seed

| Account | Opening | Original funds | Historical usage |
| --- | ---: | ---: | ---: |
| `salary-M` | 27,000.00 | 75,000.00 | 48,000.00 |
| `salary-A` | 0.00 | 63,000.00 | 63,000.00 |
| `savings` | 105,000.00 | 300,000.00 | 195,000.00 |
| **Total** | **132,000.00** | 438,000.00 | 306,000.00 |

Baseline date: **2026-11-01**. The baseline snapshot also includes two savings
usage items (`Laptop` 125,000 and `Committee` 70,000).

Categories: `Salary`, `Freelance` (income); `Groceries` (essential/variable),
`Rent` (essential/fixed), `Transport` (non-essential/variable).

All transaction data uses explicit dates between 2026-10-01 and 2026-11-30.
`date.today()` is used only to derive the current budget period in the dashboard
budget test.

## Test modules

| File | Coverage |
| --- | --- |
| `test_baseline.py` | Baseline read/update, opening balances, historical usage excluded from reports, date guard |
| `test_transactions.py` | Create/update/delete/restore, validation, refunds, idempotency, ledger search/sort/paging |
| `test_transfers.py` | Atomic balance moves, validation, idempotency, update/delete, report isolation |
| `test_reports.py` | Monthly/annual/category/account/analytics reports, reconciliation, soft-delete exclusion |
| `test_budgets_goals_recurring.py` | Budget progress, goals/contributions, recurring posting/skip/delete |
| `test_import_export.py` | CSV preview/commit, duplicate detection, validation errors, CSV exports |
| `test_api_contract.py` | Health/readiness, CRUD contracts, conflicts, auth, error envelopes, pagination meta |
| `test_dashboard.py` | KPIs, cashflow series, category slices, recent transactions, budgets, date filters |

## Behaviour notes and known issues

### 1. Transfers do not check available funds (skipped test)

`app/services/transfers.py` validates that the accounts differ, exist and are
active, but never compares the amount with the source balance. A transfer from
an account with 27,000 can move 100,000 and leave the source negative.

`test_transfer_allows_negative_source_balance` is therefore skipped with a
message pointing here. Once a balance check is added, remove the `pytest.skip`
and assert a 422 response.

### 2. CSV import multipart flags are parsed explicitly

The commit endpoint accepts `skip_duplicates` and `create_missing_categories` as
strings and parses them through a small `_form_flag` helper. The installed
FastAPI/Starlette stack coerces an omitted optional boolean form field to
`False`, which silently disabled the documented `skip_duplicates=true` default.
Omitted values now apply the documented defaults (`true` / `false`), and the
tests cover both omitted and explicit `false` values.

### 3. Recurring posting is guarded by `next_due_date`

`post_due` advances `next_due_date`, so running it again for the same
`through` date returns `created_count=0` and `skipped_count=0`. Rewinding
`next_due_date` and rerunning returns `created_count=0` and `skipped_count=1`.
The tests document both outcomes; this is expected duplicate protection, not a
bug.

### 4. Refund rules

A refund must reference an **expense** (not income), may not exceed the
expense's remaining refundable amount, and may not be dated before the original
expense. A refund dated on the same day as the expense is allowed. Refunds
reduce `expenses_net` and category totals but are tracked separately from gross
expenses.

### 5. Reporting conventions

* Date ranges are inclusive.
* Transfers affect `transfers_in` / `transfers_out` and account closing
  balances, but not income or expenses.
* Baseline balances and historical usage are context only; they never appear as
  income or expenses. `baseline_effect` remains 0 for periods at or after the
  baseline date.
* Soft-deleted transactions and transfers are excluded from reports.

### 6. Decimal handling

API JSON may encode decimals as strings or numbers. Tests normalise both through
`tests.helpers.dec()`, which quantises to two decimal places before comparing.
