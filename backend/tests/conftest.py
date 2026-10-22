"""Pytest configuration for the personal finance API.

The test database URL is installed *before* any ``app`` module is imported so
that ``app.core.db`` binds its engine to the throw-away ``personal_finance_test``
database.  The suite refuses to run against any other database.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal

TEST_DATABASE_URL = (
    "postgresql+psycopg://postgres:postgres123@127.0.0.1:5432/personal_finance_test"
)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["APP_ENV"] = "test"
os.environ.pop("API_AUTH_TOKEN", None)
os.environ.pop("TEST_DATABASE_URL", None)
# Never let the test run inherit a real Supabase backup target from backend/.env.
os.environ.pop("BACKUP_DATABASE_URL", None)
os.environ.pop("PG_BIN", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401  (register every table on Base.metadata)
from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.baseline import (  # noqa: E402
    BaselineAccount,
    BaselineSnapshot,
    BaselineUsageItem,
)
from app.models.category import Category  # noqa: E402
from app.models.enums import AccountType, CategoryType, ExpenseNature  # noqa: E402
from tests.helpers import API, BASELINE_DATE, NOV_END, NOV_START, dec  # noqa: E402

# The suite must never touch the development database.
_resolved_name = make_url(str(engine.url)).database or ""
if not _resolved_name.endswith("_test"):
    raise RuntimeError(
        f"Refusing to run tests against database {_resolved_name!r}; "
        "the database name must end with '_test'."
    )

# Optional bearer auth stays disabled unless a test monkeypatches the setting.
settings.api_auth_token = None
settings.app_env = "test"
# Pydantic also reads backend/.env, so clear the real backup target explicitly.
settings.backup_database_url = None
settings.pg_bin = None

ACCOUNT_SEED = [
    # name, account type, opening balance, original funds, historical usage
    ("salary-M", AccountType.CHECKING, "27000.00", "75000.00", "48000.00"),
    ("salary-A", AccountType.CHECKING, "0.00", "63000.00", "63000.00"),
    ("savings", AccountType.SAVINGS, "105000.00", "300000.00", "195000.00"),
]

USAGE_SEED = {
    "savings": [
        ("Laptop", "125000.00"),
        ("Committee", "70000.00"),
    ]
}

CATEGORY_SEED = [
    # name, type, essential, nature, sort order, color
    ("Salary", CategoryType.INCOME, True, ExpenseNature.FIXED, 10, "#0F766E"),
    ("Freelance", CategoryType.INCOME, True, ExpenseNature.VARIABLE, 20, "#0EA5E9"),
    ("Groceries", CategoryType.EXPENSE, True, ExpenseNature.VARIABLE, 10, "#F97316"),
    ("Rent", CategoryType.EXPENSE, True, ExpenseNature.FIXED, 20, "#0F766E"),
    ("Transport", CategoryType.EXPENSE, False, ExpenseNature.VARIABLE, 30, "#3B82F6"),
]


def _truncate_all(db: Session) -> None:
    preparer = engine.dialect.identifier_preparer
    tables = ", ".join(preparer.quote(table.name) for table in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    db.commit()


def _seed_baseline(db: Session) -> None:
    accounts: dict[str, Account] = {}
    for name, account_type, opening, _original, _usage in ACCOUNT_SEED:
        account = Account(
            name=name,
            account_type=account_type,
            currency="PKR",
            opening_balance=Decimal(opening),
            opening_date=BASELINE_DATE,
            is_active=True,
            notes=f"Baseline fixture account {name}.",
        )
        db.add(account)
        accounts[name] = account
    db.flush()

    opening_total = sum((account.opening_balance for account in accounts.values()), Decimal("0"))
    if opening_total != Decimal("132000.00"):
        raise AssertionError(
            f"Baseline fixture opening total is {opening_total}, expected 132000.00"
        )

    snapshot = BaselineSnapshot(
        name="Initial baseline",
        baseline_date=BASELINE_DATE,
        notes="Historical position before tracking began; not income or expenses.",
    )
    db.add(snapshot)
    db.flush()

    for name, _account_type, opening, original, usage in ACCOUNT_SEED:
        entry = BaselineAccount(
            baseline_id=snapshot.id,
            account_id=accounts[name].id,
            original_funds=Decimal(original),
            historical_usage=Decimal(usage),
            opening_balance=Decimal(opening),
            currency="PKR",
        )
        db.add(entry)
        db.flush()
        if Decimal(original) != Decimal(usage) + Decimal(opening):
            raise AssertionError(f"Baseline fixture for {name} does not reconcile.")
        for description, amount in USAGE_SEED.get(name, []):
            db.add(
                BaselineUsageItem(
                    baseline_account_id=entry.id,
                    description=description,
                    amount=Decimal(amount),
                    occurred_on=None,
                    notes="Historical usage before tracking began.",
                )
            )

    for name, category_type, essential, nature, order, color in CATEGORY_SEED:
        db.add(
            Category(
                name=name,
                category_type=category_type,
                icon="Circle",
                color=color,
                is_active=True,
                is_essential=essential,
                expense_nature=nature,
                sort_order=order,
            )
        )
    db.commit()


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    with engine.begin() as connection:
        Base.metadata.drop_all(connection)
        Base.metadata.create_all(connection)
    yield


@pytest.fixture()
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _reset_database(db: Session) -> Iterator[None]:
    _truncate_all(db)
    db.expire_all()
    _seed_baseline(db)
    db.expire_all()
    yield


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def accounts(db: Session) -> dict[str, uuid.UUID]:
    rows = db.scalars(select(Account).order_by(Account.name)).all()
    return {row.name: row.id for row in rows}


@pytest.fixture()
def account_ids(accounts: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    return accounts


@pytest.fixture()
def categories(db: Session) -> dict[str, uuid.UUID]:
    rows = db.scalars(select(Category).order_by(Category.name)).all()
    return {row.name: row.id for row in rows}


@pytest.fixture()
def category_ids(categories: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    return categories


@pytest.fixture()
def make_transaction(client: TestClient) -> Callable[..., dict]:
    """Create a transaction through the API with sensible defaults."""

    def _create(
        *,
        account_id: uuid.UUID | str,
        category_id: uuid.UUID | str | None = None,
        **overrides: object,
    ) -> dict:
        payload: dict[str, object] = {
            "transaction_date": NOV_START.isoformat(),
            "transaction_type": "income",
            "amount": "1000.00",
            "account_id": str(account_id),
            "category_id": str(category_id) if category_id else None,
            "description": "Test transaction",
        }
        payload.update(overrides)
        response = client.post(f"{API}/transactions", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture()
def make_transfer(client: TestClient) -> Callable[..., dict]:
    """Create a transfer through the API with sensible defaults."""

    def _create(
        *,
        from_account_id: uuid.UUID | str,
        to_account_id: uuid.UUID | str,
        **overrides: object,
    ) -> dict:
        payload: dict[str, object] = {
            "transfer_date": NOV_START.isoformat(),
            "from_account_id": str(from_account_id),
            "to_account_id": str(to_account_id),
            "amount": "5000.00",
            "description": "Test transfer",
        }
        payload.update(overrides)
        response = client.post(f"{API}/transfers", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture()
def balance_of(client: TestClient) -> Callable[..., Decimal]:
    """Read an account's current balance from the API (fresh query each call)."""

    def _balance(account_id: uuid.UUID | str) -> Decimal:
        response = client.get(
            f"{API}/accounts/{account_id}",
            params={
                "start_date": NOV_START.isoformat(),
                "end_date": NOV_END.isoformat(),
            },
        )
        assert response.status_code == 200, response.text
        return dec(response.json()["current_balance"])

    return _balance


def month_params(start: date = NOV_START, end: date = NOV_END) -> dict[str, str]:
    return {"start_date": start.isoformat(), "end_date": end.isoformat()}
