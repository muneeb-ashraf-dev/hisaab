from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.enums import AccountType, TransactionType
from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.reports.calculations import (
    ZERO,
    category_breakdown,
    money,
    month_end,
    monthly_points,
    movement_components,
)
from app.schemas.dashboard import (
    AccountBalancePoint,
    CategorySlice,
    DashboardOverview,
    TrendPoint,
)
from app.services.accounts import aggregate_balances, list_accounts
from app.services.budgets import (
    budget_progress_for_period,
    overall_budget_progress,
)
from app.services.ledger import recent_ledger
from app.services.recurring import upcoming


def cashflow_series(db: Session, *, start_date: date, end_date: date) -> list[TrendPoint]:
    days = (end_date - start_date).days + 1
    if days <= 62:
        rows = db.execute(
            select(
                Transaction.transaction_date,
                func.coalesce(
                    func.sum(
                        case_amount(TransactionType.INCOME)
                    ),
                    ZERO,
                ).label("income"),
                func.coalesce(func.sum(case_amount(TransactionType.EXPENSE)), ZERO).label(
                    "expenses"
                ),
                func.coalesce(func.sum(case_amount(TransactionType.REFUND)), ZERO).label(
                    "refunds"
                ),
            )
            .where(
                Transaction.deleted_at.is_(None),
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(Transaction.transaction_date)
            .order_by(Transaction.transaction_date)
        ).all()
        by_date = {row.transaction_date: row for row in rows}
        points: list[TrendPoint] = []
        cursor = start_date
        while cursor <= end_date:
            row = by_date.get(cursor)
            income = money(row.income) if row else ZERO
            gross = money(row.expenses) if row else ZERO
            refunds = money(row.refunds) if row else ZERO
            net = money(gross - refunds)
            points.append(
                TrendPoint(
                    month=cursor.isoformat(),
                    label=cursor.strftime("%d %b"),
                    income=income,
                    expenses=gross,
                    refunds=refunds,
                    net_expenses=net,
                    net_cash_flow=money(income - net),
                )
            )
            cursor += timedelta(days=1)
        return points

    return [
        TrendPoint(
            month=point.month,
            label=point.label,
            income=point.income,
            expenses=point.expenses,
            refunds=point.refunds,
            net_expenses=point.net_expenses,
            net_cash_flow=point.net_cash_flow,
        )
        for point in monthly_points(db, start_date=start_date, end_date=end_date)
    ]


def case_amount(transaction_type: TransactionType):
    from sqlalchemy import case

    return case((Transaction.transaction_type == transaction_type, Transaction.amount), else_=ZERO)


def dashboard_overview(
    db: Session, *, start_date: date, end_date: date
) -> DashboardOverview:
    today = date.today()
    month_start = today.replace(day=1)
    month_finish = month_end(month_start)

    balances = aggregate_balances(db)
    total_balance = money(sum((current for current, _ in balances.values()), ZERO))
    projected_balance = money(sum((projected for _, projected in balances.values()), ZERO))
    opening_total = money(
        sum(
            (
                Decimal(value)
                for value in db.scalars(select(Account.opening_balance))
            ),
            ZERO,
        )
    )

    accounts = list_accounts(db, start_date=start_date, end_date=end_date)
    savings_rows = db.execute(
        select(Account.id, Account.name).where(Account.account_type == AccountType.SAVINGS)
    ).all()
    savings_balance = money(
        sum((balances.get(row.id, (ZERO, ZERO))[0] for row in savings_rows), ZERO)
    )
    savings_month_income = ZERO
    for row in savings_rows:
        savings_month_income += movement_components(
            db,
            start_date=month_start,
            end_date=month_finish,
            account_id=row.id,
        ).income

    month = movement_components(db, start_date=month_start, end_date=month_finish)
    period = movement_components(db, start_date=start_date, end_date=end_date)
    categories, _ = category_breakdown(db, start_date=start_date, end_date=end_date)
    expense_slices = [
        CategorySlice(
            category_id=item.category_id,
            name=item.name,
            color=item.color,
            amount=item.amount,
            percentage=item.percentage,
            transaction_count=item.transaction_count,
        )
        for item in categories
        if item.amount > 0
    ]

    account_points = [
        AccountBalancePoint(
            account_id=account.id,
            name=account.name,
            balance=account.current_balance,
            opening_balance=account.opening_balance,
        )
        for account in accounts
    ]
    has_any = (
        db.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.deleted_at.is_(None))
        )
        or 0
    ) + (
        db.scalar(
            select(func.count()).select_from(Transfer).where(Transfer.deleted_at.is_(None))
        )
        or 0
    ) > 0

    return DashboardOverview(
        as_of=today,
        period_start=start_date,
        period_end=end_date,
        total_balance=total_balance,
        projected_balance=projected_balance,
        total_opening_balance=opening_total,
        period_income=period.income,
        period_expenses_gross=period.expenses_gross,
        period_refunds=period.refunds,
        period_expenses_net=period.expenses_net,
        period_net_cash_flow=period.net_cash_flow,
        savings_balance=savings_balance,
        savings_income_this_month=money(savings_month_income),
        month_start=month_start,
        month_income=month.income,
        month_expenses_gross=month.expenses_gross,
        month_refunds=month.refunds,
        month_expenses=month.expenses_net,
        month_net_cash_flow=month.net_cash_flow,
        budget=overall_budget_progress(db, period_start=month_start),
        budget_progress=budget_progress_for_period(db, period_start=month_start),
        accounts=accounts,
        cashflow=cashflow_series(db, start_date=start_date, end_date=end_date),
        expense_categories=expense_slices,
        account_balances=account_points,
        recent_transactions=recent_ledger(db, limit=8),
        upcoming_recurring=upcoming(db, horizon_days=30),
        has_any_transactions=has_any,
        days_remaining_in_month=(month_finish - today).days + 1,
    )
