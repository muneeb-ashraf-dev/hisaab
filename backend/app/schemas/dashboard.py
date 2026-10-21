from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.account import AccountWithBalance
from app.schemas.budget import BudgetProgress
from app.schemas.common import Money
from app.schemas.recurring import UpcomingRecurring
from app.schemas.transaction import LedgerEntry


class TrendPoint(BaseModel):
    month: str
    label: str
    income: Money
    expenses: Money
    refunds: Money = Decimal("0.00")
    net_cash_flow: Money
    net_expenses: Money = Decimal("0.00")


class CategorySlice(BaseModel):
    category_id: uuid.UUID | None
    name: str
    color: str
    amount: Money
    percentage: float
    transaction_count: int


class AccountBalancePoint(BaseModel):
    account_id: uuid.UUID
    name: str
    balance: Money
    opening_balance: Money


class DashboardOverview(BaseModel):
    as_of: date
    period_start: date
    period_end: date
    total_balance: Money
    projected_balance: Money
    total_opening_balance: Money
    period_income: Money
    period_expenses_gross: Money
    period_refunds: Money
    period_expenses_net: Money
    period_net_cash_flow: Money
    savings_balance: Money
    savings_income_this_month: Money
    month_start: date
    month_income: Money
    month_expenses_gross: Money
    month_refunds: Money
    month_expenses: Money
    month_net_cash_flow: Money
    budget: BudgetProgress | None = None
    budget_progress: list[BudgetProgress] = []
    accounts: list[AccountWithBalance] = []
    cashflow: list[TrendPoint] = []
    expense_categories: list[CategorySlice] = []
    account_balances: list[AccountBalancePoint] = []
    recent_transactions: list[LedgerEntry] = []
    upcoming_recurring: list[UpcomingRecurring] = []
    has_any_transactions: bool = False
    days_remaining_in_month: int = 0
