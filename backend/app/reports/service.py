from __future__ import annotations

import calendar
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.account import Account
from app.models.category import Category
from app.models.enums import CategoryType, TransactionType
from app.models.transaction import Transaction
from app.reports.calculations import (
    ZERO,
    account_opening_balance,
    account_summaries,
    baseline_info,
    category_breakdown,
    combined_balance_after,
    combined_opening,
    income_sources,
    large_expenses,
    money,
    month_end,
    month_starts,
    monthly_points,
    movement_components,
    pct_change,
    previous_period,
    recurring_candidates,
    savings_rate,
    spending_by_nature,
)
from app.schemas.reports import (
    AccountPeriodSummary,
    AccountReport,
    AnalyticsReport,
    AnnualReport,
    CategoryReport,
    LargeExpense,
    LargestExpense,
    MonthlyReport,
    PeriodComparison,
    RecurringCandidate,
)
from app.services.accounts import aggregate_balances
from app.services.budgets import budget_adherence, budget_progress_for_period
from app.services.ledger import query_ledger

DEFINITIONS = {
    "net_expenses": (
        "Gross expenses minus refunds linked to expenses. Internal transfers are excluded."
    ),
    "net_cash_flow": "Income minus net expenses. Internal transfers and adjustments are excluded.",
    "savings_rate": "(Income - net expenses) / income x 100. Returns null when income is zero.",
    "baseline_effect": (
        "Opening balances introduced at the baseline date. Shown separately so a period that "
        "starts before tracking began still reconciles."
    ),
    "adjustments": (
        "Reconciliation entries that change an account balance without being income or expense. "
        "They appear separately in reconciliation, never in income or spending totals."
    ),
    "essential_spending": "Net expenses whose category is marked essential.",
    "discretionary_spending": "Net expenses whose category is not marked essential.",
    "fixed_spending": "Net expenses in categories marked as fixed.",
    "variable_spending": (
        "Net expenses in categories marked as variable; mixed categories are split 50/50."
    ),
    "budget_adherence": (
        "Overall budget utilization for the starting month: net expenses / overall budget x 100. "
        "Transfers and baseline figures are excluded."
    ),
    "large_expense": (
        "An expense above Q3 + 1.5 x IQR of expenses in the period (Tukey fence). "
        "Requires at least 5 expenses; otherwise no unusual expenses are flagged."
    ),
    "concentration": "Percentage of net expenses in the largest category.",
    "recurring_candidate": (
        "An expense description or merchant seen at least 3 times across 2+ months in the period. "
        "A stable amount range of 25% or less makes it a stronger candidate."
    ),
    "transfers": (
        "Transfers move money between your own accounts. They change account balances but are "
        "never counted as income or expenses, including transfers into savings."
    ),
}


def _largest_expenses(
    db: Session, *, start_date: date, end_date: date, limit: int = 10
) -> list[LargestExpense]:
    stmt = (
        select(
            Transaction.id,
            Transaction.transaction_date,
            Transaction.description,
            Transaction.amount,
            Transaction.merchant_or_payee,
            Category.name.label("category_name"),
            Account.name.label("account_name"),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
            Transaction.transaction_type == TransactionType.EXPENSE,
        )
        .order_by(Transaction.amount.desc(), Transaction.transaction_date.desc())
        .limit(limit)
    )
    return [
        LargestExpense(
            id=row.id,
            transaction_date=row.transaction_date,
            description=row.description,
            amount=row.amount,
            category_name=row.category_name,
            account_name=row.account_name,
            merchant_or_payee=row.merchant_or_payee,
        )
        for row in db.execute(stmt)
    ]


def monthly_report(db: Session, *, start_date: date, end_date: date) -> MonthlyReport:
    if end_date < start_date:
        raise ValidationError("end_date must be on or after start_date.")
    opening, baseline_effect = combined_opening(db, start_date)
    movement = movement_components(db, start_date=start_date, end_date=end_date)
    closing = money(opening + baseline_effect + movement.net_cash_flow + movement.adjustments_net)
    actual_closing = combined_balance_after(db, end_date)
    reconciliation = money(actual_closing - closing)

    accounts = [
        AccountPeriodSummary(**row)
        for row in account_summaries(db, start_date=start_date, end_date=end_date)
    ]
    categories, total_net = category_breakdown(db, start_date=start_date, end_date=end_date)
    budgets = budget_progress_for_period(db, period_start=start_date.replace(day=1))
    adherence = budget_adherence(db, start_date=start_date, end_date=end_date)

    if start_date.day == 1 and end_date == month_end(start_date):
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
    else:
        prev_start, prev_end = previous_period(start_date, end_date)
    prev_movement = movement_components(db, start_date=prev_start, end_date=prev_end)
    comparison = PeriodComparison(
        previous_start=prev_start,
        previous_end=prev_end,
        previous_income=prev_movement.income,
        previous_expenses=prev_movement.expenses_net,
        income_change_pct=pct_change(movement.income, prev_movement.income),
        expenses_change_pct=pct_change(movement.expenses_net, prev_movement.expenses_net),
        net_change=money(movement.net_cash_flow - prev_movement.net_cash_flow),
    )

    label = (
        start_date.strftime("%B %Y")
        if start_date.day == 1 and end_date == month_end(start_date)
        else f"{start_date:%d %b %Y} – {end_date:%d %b %Y}"
    )
    return MonthlyReport(
        start_date=start_date,
        end_date=end_date,
        label=label,
        is_partial_month=not (start_date.day == 1 and end_date == month_end(start_date)),
        opening_balance=opening,
        baseline_effect=baseline_effect,
        income=movement.income,
        expenses_gross=movement.expenses_gross,
        refunds=movement.refunds,
        expenses_net=movement.expenses_net,
        net_cash_flow=movement.net_cash_flow,
        adjustments_increase=movement.adjustments_increase,
        adjustments_decrease=movement.adjustments_decrease,
        adjustments_net=movement.adjustments_net,
        transfers_in=movement.transfers_in,
        transfers_out=movement.transfers_out,
        closing_balance=closing,
        savings_rate_pct=savings_rate(movement.income, movement.expenses_net),
        accounts=accounts,
        categories=categories,
        largest_expenses=_largest_expenses(db, start_date=start_date, end_date=end_date),
        budgets=budgets,
        budget_adherence_pct=adherence,
        comparison=comparison,
        reconciliation_difference=reconciliation,
        transaction_count=movement.transaction_count,
    )


def month_report(db: Session, *, year: int, month: int) -> MonthlyReport:
    if not 1 <= month <= 12:
        raise ValidationError("month must be between 1 and 12.")
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return monthly_report(db, start_date=start, end_date=end)


def annual_report(
    db: Session, *, start_date: date, end_date: date, year: int | None = None
) -> AnnualReport:
    opening, baseline_effect = combined_opening(db, start_date)
    movement = movement_components(db, start_date=start_date, end_date=end_date)
    closing = money(opening + baseline_effect + movement.net_cash_flow + movement.adjustments_net)
    points = monthly_points(db, start_date=start_date, end_date=end_date)
    categories, _ = category_breakdown(db, start_date=start_date, end_date=end_date)
    accounts = [
        AccountPeriodSummary(**row)
        for row in account_summaries(db, start_date=start_date, end_date=end_date)
    ]

    month_count = max(len(month_starts(start_date, end_date)), 1)
    average = money(movement.expenses_net / month_count)

    highest_month = None
    if movement.expenses_net > 0:
        highest_month = max(points, key=lambda point: point.net_expenses)
    highest_category = categories[0] if categories else None

    yoy = None
    if year is not None:
        prev_start = date(year - 1, 1, 1)
        prev_end = date(year - 1, 12, 31)
        prev_movement = movement_components(db, start_date=prev_start, end_date=prev_end)
        has_previous_data = (
            prev_movement.transaction_count > 0
            and (
                prev_movement.income > 0
                or prev_movement.expenses_gross > 0
                or prev_movement.refunds > 0
            )
        )
        if has_previous_data:
            yoy = {
                "year": year - 1,
                "income": prev_movement.income,
                "expenses_net": prev_movement.expenses_net,
                "net_cash_flow": prev_movement.net_cash_flow,
                "income_change_pct": pct_change(movement.income, prev_movement.income),
                "expenses_change_pct": pct_change(
                    movement.expenses_net, prev_movement.expenses_net
                ),
                "net_change": money(movement.net_cash_flow - prev_movement.net_cash_flow),
            }

    return AnnualReport(
        year=year or start_date.year,
        start_date=start_date,
        end_date=end_date,
        opening_balance=opening,
        baseline_effect=baseline_effect,
        income=movement.income,
        expenses_gross=movement.expenses_gross,
        refunds=movement.refunds,
        expenses_net=movement.expenses_net,
        net_cash_flow=movement.net_cash_flow,
        adjustments_net=movement.adjustments_net,
        closing_balance=closing,
        savings_rate_pct=savings_rate(movement.income, movement.expenses_net),
        months=points,
        accounts=accounts,
        categories=categories,
        monthly_average_expenses=average,
        highest_spending_month=highest_month,
        highest_spending_category=highest_category,
        year_over_year=yoy,
        transaction_count=movement.transaction_count,
    )


def category_report(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    category_type: CategoryType = CategoryType.EXPENSE,
) -> CategoryReport:
    categories, total_net = category_breakdown(
        db, start_date=start_date, end_date=end_date, category_type=category_type
    )
    prev_start, prev_end = previous_period(start_date, end_date)
    previous_categories, previous_total = category_breakdown(
        db, start_date=prev_start, end_date=prev_end, category_type=category_type
    )
    previous_map = {item.category_id: item.amount for item in previous_categories}
    for item in categories:
        previous_amount = previous_map.get(item.category_id, ZERO)
        item.previous_amount = previous_amount
        item.change_pct = pct_change(item.amount, previous_amount)

    trend = []
    for month_start in month_starts(start_date, end_date):
        period_start = max(month_start, start_date)
        period_end = min(month_end(month_start), end_date)
        month_categories, month_total = category_breakdown(
            db, start_date=period_start, end_date=period_end, category_type=category_type
        )
        trend.append(
            {
                "month": month_start.strftime("%Y-%m"),
                "label": month_start.strftime("%b %Y"),
                "total": month_total,
                "categories": {
                    str(item.category_id): item.amount for item in month_categories
                },
            }
        )

    return CategoryReport(
        start_date=start_date,
        end_date=end_date,
        total_expenses_net=total_net,
        categories=categories,
        previous_start=prev_start,
        previous_end=prev_end,
        previous_total_expenses_net=previous_total,
        total_change_pct=pct_change(total_net, previous_total),
        monthly_trend=trend,
        definitions=DEFINITIONS,
    )


def account_report(
    db: Session,
    *,
    account_id: uuid.UUID,
    start_date: date,
    end_date: date,
    history_limit: int = 100,
) -> AccountReport:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found.")
    opening = account_opening_balance(account, start_date, db, end_date=end_date)
    movement = movement_components(
        db, start_date=start_date, end_date=end_date, account_id=account.id
    )
    closing = money(opening + movement.net_movement)
    balances = aggregate_balances(db)
    current, _ = balances.get(account.id, (ZERO, ZERO))
    categories, _ = category_breakdown(
        db, start_date=start_date, end_date=end_date, account_id=account.id
    )
    income_breakdown, _ = category_breakdown(
        db,
        start_date=start_date,
        end_date=end_date,
        category_type=CategoryType.INCOME,
        account_id=account.id,
    )
    history, _ = query_ledger(
        db,
        page=1,
        page_size=history_limit,
        start_date=start_date,
        end_date=end_date,
        account_id=account.id,
        sort_by="entry_date",
        sort_dir="desc",
    )
    return AccountReport(
        account_id=account.id,
        account_name=account.name,
        account_type=account.account_type.value,
        currency=account.currency,
        start_date=start_date,
        end_date=end_date,
        opening_balance=opening,
        closing_balance=closing,
        current_balance=current,
        income=movement.income,
        expenses_gross=movement.expenses_gross,
        refunds=movement.refunds,
        expenses_net=movement.expenses_net,
        transfers_in=movement.transfers_in,
        transfers_out=movement.transfers_out,
        adjustments_increase=movement.adjustments_increase,
        adjustments_decrease=movement.adjustments_decrease,
        net_movement=movement.net_movement,
        history=history,
        categories=categories,
        income_sources=income_breakdown,
    )


def analytics_report(db: Session, *, start_date: date, end_date: date) -> AnalyticsReport:
    movement = movement_components(db, start_date=start_date, end_date=end_date)
    categories, total_net = category_breakdown(db, start_date=start_date, end_date=end_date)
    nature = spending_by_nature(db, start_date=start_date, end_date=end_date)
    sources = income_sources(db, start_date=start_date, end_date=end_date)
    flagged, threshold = large_expenses(db, start_date=start_date, end_date=end_date)
    candidates = recurring_candidates(db, start_date=start_date, end_date=end_date)
    adherence = budget_adherence(db, start_date=start_date, end_date=end_date)
    concentration = categories[:5]
    top_share = concentration[0].percentage if concentration and total_net > 0 else None

    return AnalyticsReport(
        start_date=start_date,
        end_date=end_date,
        savings_rate_pct=savings_rate(movement.income, movement.expenses_net),
        savings_rate_definition=DEFINITIONS["savings_rate"],
        income=movement.income,
        expenses_net=movement.expenses_net,
        fixed_expenses=nature["fixed"],
        variable_expenses=nature["variable"],
        essential_expenses=nature["essential"],
        discretionary_expenses=nature["discretionary"],
        budget_adherence_pct=adherence,
        budget_definition=DEFINITIONS["budget_adherence"],
        category_concentration=concentration,
        top_category_share_pct=top_share,
        income_sources=sources,
        large_expenses=[LargeExpense(**row) for row in flagged],
        large_expense_threshold=threshold,
        recurring_candidates=[RecurringCandidate(**row) for row in candidates],
        spending_trend=monthly_points(db, start_date=start_date, end_date=end_date),
        definitions=DEFINITIONS,
    )


def annual_report_for_year(db: Session, year: int) -> AnnualReport:
    return annual_report(
        db,
        start_date=date(year, 1, 1),
        end_date=date(year, 12, 31),
        year=year,
    )


def report_available_years(db: Session) -> list[int]:
    rows = db.execute(
        select(
            func.extract("year", Transaction.transaction_date).label("year"),
        )
        .where(Transaction.deleted_at.is_(None))
        .group_by("year")
        .order_by("year")
    )
    years = {int(row.year) for row in rows}
    _, baseline_date = baseline_info(db)
    if baseline_date is not None:
        years.add(baseline_date.year)
    years.add(date.today().year)
    return sorted(years, reverse=True)
