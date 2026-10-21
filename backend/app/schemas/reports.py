from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.budget import BudgetProgress
from app.schemas.common import Money
from app.schemas.transaction import LedgerEntry


class CategorySpend(BaseModel):
    category_id: uuid.UUID | None
    name: str
    color: str
    amount: Money
    percentage: float
    transaction_count: int
    average_amount: Money
    largest_amount: Money
    is_essential: bool | None = None
    expense_nature: str | None = None
    previous_amount: Money | None = None
    change_pct: float | None = None


class AccountPeriodSummary(BaseModel):
    account_id: uuid.UUID
    account_name: str
    opening_balance: Money
    closing_balance: Money
    income: Money
    expenses_gross: Money
    refunds: Money
    expenses_net: Money
    transfers_in: Money
    transfers_out: Money
    adjustments_increase: Money
    adjustments_decrease: Money
    net_movement: Money
    transaction_count: int


class MonthlyPoint(BaseModel):
    month: str
    label: str
    income: Money
    expenses: Money
    refunds: Money
    net_expenses: Money
    adjustments_net: Money
    net_cash_flow: Money
    closing_balance: Money
    opening_balance: Money
    baseline_effect: Money = Decimal("0.00")


class PeriodComparison(BaseModel):
    previous_start: date | None = None
    previous_end: date | None = None
    income_change_pct: float | None = None
    expenses_change_pct: float | None = None
    net_change: Money | None = None
    previous_income: Money | None = None
    previous_expenses: Money | None = None


class LargestExpense(BaseModel):
    id: uuid.UUID
    transaction_date: date
    description: str
    amount: Money
    category_name: str | None
    account_name: str | None
    merchant_or_payee: str | None


class MonthlyReport(BaseModel):
    start_date: date
    end_date: date
    label: str
    is_partial_month: bool = False
    opening_balance: Money
    baseline_effect: Money
    income: Money
    expenses_gross: Money
    refunds: Money
    expenses_net: Money
    net_cash_flow: Money
    adjustments_increase: Money
    adjustments_decrease: Money
    adjustments_net: Money
    transfers_in: Money
    transfers_out: Money
    closing_balance: Money
    savings_rate_pct: float | None
    accounts: list[AccountPeriodSummary]
    categories: list[CategorySpend]
    largest_expenses: list[LargestExpense]
    budgets: list[BudgetProgress]
    budget_adherence_pct: float | None
    comparison: PeriodComparison
    reconciliation_difference: Money
    transaction_count: int


class AnnualReport(BaseModel):
    year: int
    start_date: date
    end_date: date
    opening_balance: Money
    baseline_effect: Money
    income: Money
    expenses_gross: Money
    refunds: Money
    expenses_net: Money
    net_cash_flow: Money
    adjustments_net: Money
    closing_balance: Money
    savings_rate_pct: float | None
    months: list[MonthlyPoint]
    accounts: list[AccountPeriodSummary]
    categories: list[CategorySpend]
    monthly_average_expenses: Money
    highest_spending_month: MonthlyPoint | None
    highest_spending_category: CategorySpend | None
    year_over_year: dict | None = None
    transaction_count: int


class CategoryReport(BaseModel):
    start_date: date
    end_date: date
    total_expenses_net: Money
    categories: list[CategorySpend]
    previous_start: date
    previous_end: date
    previous_total_expenses_net: Money
    total_change_pct: float | None
    monthly_trend: list[dict]
    definitions: dict[str, str]


class AccountReport(BaseModel):
    account_id: uuid.UUID
    account_name: str
    account_type: str
    currency: str
    start_date: date
    end_date: date
    opening_balance: Money
    closing_balance: Money
    current_balance: Money
    income: Money
    expenses_gross: Money
    refunds: Money
    expenses_net: Money
    transfers_in: Money
    transfers_out: Money
    adjustments_increase: Money
    adjustments_decrease: Money
    net_movement: Money
    history: list[LedgerEntry]
    categories: list[CategorySpend]
    income_sources: list[CategorySpend]


class LargeExpense(BaseModel):
    id: uuid.UUID
    transaction_date: date
    description: str
    amount: Money
    category_name: str | None
    merchant_or_payee: str | None
    threshold: Money
    multiple_of_median: float


class IncomeSource(BaseModel):
    name: str
    amount: Money
    percentage: float
    transaction_count: int


class RecurringCandidate(BaseModel):
    merchant_or_payee: str
    category_name: str | None
    transaction_count: int
    average_amount: Money
    amount_range_pct: float
    last_seen: date
    suggestion: str


class AnalyticsReport(BaseModel):
    start_date: date
    end_date: date
    savings_rate_pct: float | None
    savings_rate_definition: str
    income: Money
    expenses_net: Money
    fixed_expenses: Money
    variable_expenses: Money
    essential_expenses: Money
    discretionary_expenses: Money
    budget_adherence_pct: float | None
    budget_definition: str
    category_concentration: list[CategorySpend]
    top_category_share_pct: float | None
    income_sources: list[IncomeSource]
    large_expenses: list[LargeExpense]
    large_expense_threshold: Money | None
    recurring_candidates: list[RecurringCandidate]
    spending_trend: list[MonthlyPoint]
    definitions: dict[str, str]
