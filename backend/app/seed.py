"""Idempotent initialization of the personal finance ledger.

Run with:
    uv run python -m app.seed

The command is safe to run repeatedly. It creates the three required accounts,
their opening balances, and default categories only when they are missing.
It never fabricates transactions.
"""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.account import Account
from app.models.baseline import BaselineAccount, BaselineSnapshot, BaselineUsageItem
from app.models.category import Category
from app.models.enums import AccountType, CategoryType, ExpenseNature

BASELINE_DATE = date.fromisoformat(settings.baseline_date)

ACCOUNT_SEEDS = [
    {
        "name": "salary-M",
        "account_type": AccountType.CHECKING,
        "opening_balance": Decimal("27000.00"),
        "original_funds": Decimal("27000.00"),
        "historical_usage": Decimal("0.00"),
        "notes": "Monthly salary account. Opening balance at fresh start.",
    },
    {
        "name": "salary-A",
        "account_type": AccountType.CHECKING,
        "opening_balance": Decimal("0.00"),
        "original_funds": Decimal("0.00"),
        "historical_usage": Decimal("0.00"),
        "notes": "Monthly salary account. Opening balance at fresh start.",
    },
    {
        "name": "savings",
        "account_type": AccountType.SAVINGS,
        "opening_balance": Decimal("300000.00"),
        "original_funds": Decimal("300000.00"),
        "historical_usage": Decimal("0.00"),
        "notes": "Long-term savings. Opening balance at fresh start.",
    },
]

USAGE_ITEMS: dict[str, list[dict[str, object]]] = {}

CATEGORY_SEEDS = [
    # Income
    ("Salary", CategoryType.INCOME, "Wallet", "#0F766E", True, ExpenseNature.FIXED, 10),
    ("Freelance", CategoryType.INCOME, "Laptop", "#0EA5E9", True, ExpenseNature.VARIABLE, 20),
    ("Teaching", CategoryType.INCOME, "GraduationCap", "#6366F1", True, ExpenseNature.VARIABLE, 30),
    ("Bank Interest", CategoryType.INCOME, "Landmark", "#14B8A6", True, ExpenseNature.VARIABLE, 40),
    (
        "Other Income",
        CategoryType.INCOME,
        "CirclePlus",
        "#64748B",
        True,
        ExpenseNature.VARIABLE,
        50,
    ),
    # Expenses
    (
        "Food & Groceries",
        CategoryType.EXPENSE,
        "UtensilsCrossed",
        "#F97316",
        True,
        ExpenseNature.VARIABLE,
        10,
    ),
    ("Transport", CategoryType.EXPENSE, "Bus", "#3B82F6", True, ExpenseNature.VARIABLE, 20),
    (
        "Bills & Utilities",
        CategoryType.EXPENSE,
        "ReceiptText",
        "#8B5CF6",
        True,
        ExpenseNature.FIXED,
        30,
    ),
    ("Housing & Rent", CategoryType.EXPENSE, "Home", "#0F766E", True, ExpenseNature.FIXED, 40),
    ("Education", CategoryType.EXPENSE, "GraduationCap", "#2563EB", True, ExpenseNature.FIXED, 50),
    ("Health", CategoryType.EXPENSE, "HeartPulse", "#EF4444", True, ExpenseNature.VARIABLE, 60),
    ("Shopping", CategoryType.EXPENSE, "ShoppingBag", "#EC4899", False, ExpenseNature.VARIABLE, 70),
    (
        "Laptop & Electronics",
        CategoryType.EXPENSE,
        "Laptop",
        "#6366F1",
        False,
        ExpenseNature.VARIABLE,
        80,
    ),
    ("Committee", CategoryType.EXPENSE, "Users", "#D97706", True, ExpenseNature.FIXED, 90),
    (
        "Entertainment",
        CategoryType.EXPENSE,
        "Clapperboard",
        "#A855F7",
        False,
        ExpenseNature.VARIABLE,
        100,
    ),
    ("Charity", CategoryType.EXPENSE, "HandHeart", "#10B981", False, ExpenseNature.VARIABLE, 110),
    (
        "Other Expenses",
        CategoryType.EXPENSE,
        "CircleEllipsis",
        "#64748B",
        False,
        ExpenseNature.VARIABLE,
        120,
    ),
]


def seed_accounts(db: Session) -> dict[str, Account]:
    accounts: dict[str, Account] = {}
    for item in ACCOUNT_SEEDS:
        account = db.scalar(select(Account).where(func.lower(Account.name) == item["name"].lower()))
        if account is None:
            account = Account(
                name=item["name"],
                account_type=item["account_type"],
                currency=settings.currency,
                opening_balance=item["opening_balance"],
                opening_date=BASELINE_DATE,
                is_active=True,
                notes=item["notes"],
            )
            db.add(account)
            db.flush()
            print(
                f"  created account {account.name} ({account.opening_balance} {account.currency})"
            )
        else:
            print(f"  account {account.name} already exists; left unchanged")
        accounts[account.name] = account
    return accounts


def seed_categories(db: Session) -> int:
    created = 0
    for name, cat_type, icon, color, essential, nature, sort_order in CATEGORY_SEEDS:
        existing = db.scalar(select(Category).where(func.lower(Category.name) == name.lower()))
        if existing is not None:
            continue
        db.add(
            Category(
                name=name,
                category_type=cat_type,
                icon=icon,
                color=color,
                is_essential=essential,
                expense_nature=nature,
                sort_order=sort_order,
            )
        )
        created += 1
    db.flush()
    print(f"  categories created: {created}")
    return created


def seed_baseline(db: Session, accounts: dict[str, Account]) -> bool:
    existing = db.scalar(
        select(BaselineSnapshot).where(BaselineSnapshot.name == "Initial baseline")
    )
    if existing is not None:
        print("  baseline already exists; left unchanged")
        return False

    snapshot = BaselineSnapshot(
        name="Initial baseline",
        baseline_date=BASELINE_DATE,
        notes=(
            "Opening position when tracking began. Historical usage is not tracked; "
            "the opening balances are the fresh starting point."
        ),
    )
    db.add(snapshot)
    db.flush()
    for item in ACCOUNT_SEEDS:
        account = accounts[item["name"]]
        usage_items = USAGE_ITEMS.get(item["name"], [])
        historical_usage = sum(
            (Decimal(str(usage["amount"])) for usage in usage_items),
            Decimal("0.00"),
        )
        entry = BaselineAccount(
            baseline_id=snapshot.id,
            account_id=account.id,
            original_funds=account.opening_balance + historical_usage,
            historical_usage=historical_usage,
            opening_balance=account.opening_balance,
            currency=settings.currency,
        )
        db.add(entry)
        db.flush()
        for usage in usage_items:
            db.add(
                BaselineUsageItem(
                    baseline_account_id=entry.id,
                    description=str(usage["description"]),
                    amount=usage["amount"],
                    occurred_on=None,
                    notes="Historical usage before tracking began.",
                )
            )
    print("  baseline snapshot created")
    return True


def run_seed() -> None:
    print(f"Seeding personal finance database ({settings.database_url.split('@')[-1]})")
    with SessionLocal() as db:
        accounts = seed_accounts(db)
        seed_categories(db)
        seed_baseline(db, accounts)
        db.commit()

        opening_total = sum(
            (Decimal(item["opening_balance"]) for item in ACCOUNT_SEEDS), Decimal("0.00")
        )
        print(f"  combined opening balance: {opening_total} {settings.currency}")
        actual = db.scalar(select(func.coalesce(func.sum(Account.opening_balance), 0)))
        print(f"  account opening total in database: {Decimal(actual or 0)} {settings.currency}")
    print("Seed complete. Opening balances are excluded from income and expense reports.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the personal finance database.")
    parser.parse_args()
    run_seed()


if __name__ == "__main__":
    main()
