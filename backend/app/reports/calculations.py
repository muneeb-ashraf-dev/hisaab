from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category
from app.models.enums import CategoryType, ExpenseNature, TransactionType
from app.models.transaction import Transaction
from app.models.transfer import Transfer
from app.schemas.reports import CategorySpend, IncomeSource, MonthlyPoint

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def money(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(CENT)


def pct_change(current: Decimal, previous: Decimal) -> float | None:
    if previous == 0:
        return None
    return float(((current - previous) / previous * 100).quantize(Decimal("0.1")))


def savings_rate(income: Decimal, net_expenses: Decimal) -> float | None:
    if income <= 0:
        return None
    return float(((income - net_expenses) / income * 100).quantize(Decimal("0.1")))


@dataclass
class Movement:
    income: Decimal = ZERO
    expenses_gross: Decimal = ZERO
    refunds: Decimal = ZERO
    adjustments_increase: Decimal = ZERO
    adjustments_decrease: Decimal = ZERO
    transfers_in: Decimal = ZERO
    transfers_out: Decimal = ZERO
    transaction_count: int = 0
    expense_count: int = 0

    @property
    def expenses_net(self) -> Decimal:
        return money(self.expenses_gross - self.refunds)

    @property
    def adjustments_net(self) -> Decimal:
        return money(self.adjustments_increase - self.adjustments_decrease)

    @property
    def net_cash_flow(self) -> Decimal:
        return money(self.income - self.expenses_net)

    @property
    def net_movement(self) -> Decimal:
        return money(
            self.income
            - self.expenses_gross
            + self.refunds
            + self.adjustments_increase
            - self.adjustments_decrease
            + self.transfers_in
            - self.transfers_out
        )


def movement_components(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: uuid.UUID | None = None,
    strict_before: date | None = None,
) -> Movement:
    conditions = [Transaction.deleted_at.is_(None)]
    if start_date:
        conditions.append(Transaction.transaction_date >= start_date)
    if end_date:
        conditions.append(Transaction.transaction_date <= end_date)
    if strict_before:
        conditions.append(Transaction.transaction_date < strict_before)
    if account_id:
        conditions.append(Transaction.account_id == account_id)

    def amount_for(*types: TransactionType):
        return func.coalesce(
            func.sum(
                case(
                    (Transaction.transaction_type.in_(types), Transaction.amount),
                    else_=ZERO,
                )
            ),
            ZERO,
        )

    txn_stmt = select(
        amount_for(TransactionType.INCOME).label("income"),
        amount_for(TransactionType.EXPENSE).label("expenses"),
        amount_for(TransactionType.REFUND).label("refunds"),
        amount_for(TransactionType.ADJUSTMENT_INCREASE).label("adj_in"),
        amount_for(TransactionType.ADJUSTMENT_DECREASE).label("adj_out"),
        func.count().label("txn_count"),
        func.coalesce(
            func.sum(case((Transaction.transaction_type == TransactionType.EXPENSE, 1), else_=0)),
            0,
        ).label("expense_count"),
    ).where(*conditions)
    row = db.execute(txn_stmt).one()
    movement = Movement(
        income=money(row.income),
        expenses_gross=money(row.expenses),
        refunds=money(row.refunds),
        adjustments_increase=money(row.adj_in),
        adjustments_decrease=money(row.adj_out),
        transaction_count=int(row.txn_count or 0),
        expense_count=int(row.expense_count or 0),
    )

    transfer_conditions = [Transfer.deleted_at.is_(None)]
    if start_date:
        transfer_conditions.append(Transfer.transfer_date >= start_date)
    if end_date:
        transfer_conditions.append(Transfer.transfer_date <= end_date)
    if strict_before:
        transfer_conditions.append(Transfer.transfer_date < strict_before)

    if account_id:
        incoming = func.coalesce(
            func.sum(case((Transfer.to_account_id == account_id, Transfer.amount), else_=ZERO)),
            ZERO,
        )
        outgoing = func.coalesce(
            func.sum(case((Transfer.from_account_id == account_id, Transfer.amount), else_=ZERO)),
            ZERO,
        )
    else:
        incoming = func.coalesce(func.sum(Transfer.amount), ZERO)
        outgoing = func.coalesce(func.sum(Transfer.amount), ZERO)

    transfer_row = db.execute(
        select(incoming.label("incoming"), outgoing.label("outgoing")).where(*transfer_conditions)
    ).one()
    movement.transfers_in = money(transfer_row.incoming)
    movement.transfers_out = money(transfer_row.outgoing)
    return movement


def baseline_info(db: Session) -> tuple[Decimal, date | None]:
    total, earliest = db.execute(
        select(
            func.coalesce(func.sum(Account.opening_balance), ZERO),
            func.min(Account.opening_date),
        )
    ).one()
    return money(total), earliest


def combined_opening(db: Session, start_date: date) -> tuple[Decimal, Decimal]:
    """Return (opening_balance, baseline_effect) for a combined report period.

    Opening balances are the ledger's starting state on the baseline date. A
    period that starts before the baseline reports opening 0 and a separately
    identified baseline effect so the reconciliation still balances.
    """
    baseline_total, baseline_date = baseline_info(db)
    if baseline_date is None:
        return ZERO, ZERO
    if start_date >= baseline_date:
        before = movement_components(db, strict_before=start_date)
        opening = money(baseline_total + before.net_movement)
        return opening, ZERO
    return ZERO, baseline_total


def combined_balance_after(db: Session, end_date: date) -> Decimal:
    baseline_total, baseline_date = baseline_info(db)
    if baseline_date is None or end_date < baseline_date:
        return ZERO
    movement = movement_components(db, end_date=end_date)
    return money(baseline_total + movement.net_movement)


def account_opening_balance(
    account: Account, start_date: date, db: Session, *, end_date: date | None = None
) -> Decimal:
    """Return the account balance immediately before ``start_date``.

    ``Account.opening_balance`` is the starting position on ``opening_date``.
    A period that begins before that date still includes the opening balance so
    its closing balance reconciles with the live account balance; only a period
    that ends before the account existed starts from zero.
    """
    if end_date is not None and end_date < account.opening_date:
        return ZERO
    opening = Decimal(account.opening_balance)
    if start_date > account.opening_date:
        before = movement_components(db, strict_before=start_date, account_id=account.id)
        opening += before.net_movement
    return money(opening)


def account_summaries(
    db: Session, *, start_date: date, end_date: date
) -> list[dict]:
    accounts = list(db.scalars(select(Account).order_by(Account.name)))
    result = []
    for account in accounts:
        opening = account_opening_balance(account, start_date, db, end_date=end_date)
        movement = movement_components(
            db, start_date=start_date, end_date=end_date, account_id=account.id
        )
        closing = money(opening + movement.net_movement)
        result.append(
            {
                "account_id": account.id,
                "account_name": account.name,
                "opening_balance": opening,
                "closing_balance": closing,
                "income": movement.income,
                "expenses_gross": movement.expenses_gross,
                "refunds": movement.refunds,
                "expenses_net": movement.expenses_net,
                "transfers_in": movement.transfers_in,
                "transfers_out": movement.transfers_out,
                "adjustments_increase": movement.adjustments_increase,
                "adjustments_decrease": movement.adjustments_decrease,
                "net_movement": movement.net_movement,
                "transaction_count": movement.transaction_count,
            }
        )
    return result


def category_breakdown(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    category_type: CategoryType = CategoryType.EXPENSE,
    account_id: uuid.UUID | None = None,
) -> tuple[list[CategorySpend], Decimal]:
    """Net category totals. Refunds reduce the category they belong to."""
    if category_type == CategoryType.EXPENSE:
        txn_types = (TransactionType.EXPENSE, TransactionType.REFUND)
    else:
        txn_types = (TransactionType.INCOME,)

    gross = func.coalesce(
        func.sum(
            case(
                (Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount),
                else_=ZERO,
            )
        ),
        ZERO,
    )
    refunds = func.coalesce(
        func.sum(
            case(
                (Transaction.transaction_type == TransactionType.REFUND, Transaction.amount),
                else_=ZERO,
            )
        ),
        ZERO,
    )
    if category_type == CategoryType.EXPENSE:
        counts = func.coalesce(
            func.sum(case((Transaction.transaction_type == TransactionType.EXPENSE, 1), else_=0)),
            0,
        )
        largest = func.coalesce(
            func.max(
                case((Transaction.transaction_type == TransactionType.EXPENSE, Transaction.amount))
            ),
            ZERO,
        )
        amount_sum = gross
    else:
        counts = func.count()
        largest = func.coalesce(func.max(Transaction.amount), ZERO)
        amount_sum = func.coalesce(func.sum(Transaction.amount), ZERO)

    stmt = (
        select(
            Transaction.category_id,
            Category.name,
            Category.color,
            Category.is_essential,
            Category.expense_nature,
            gross.label("expenses"),
            refunds.label("refunds"),
            amount_sum.label("amount_sum"),
            counts.label("txn_count"),
            largest.label("largest"),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
            Transaction.transaction_type.in_(txn_types),
        )
        .group_by(
            Transaction.category_id,
            Category.name,
            Category.color,
            Category.is_essential,
            Category.expense_nature,
        )
    )
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    raw: list[dict] = []
    for row in db.execute(stmt):
        if category_type == CategoryType.EXPENSE:
            amount = money(Decimal(row.expenses or 0) - Decimal(row.refunds or 0))
        else:
            amount = money(row.amount_sum)
        count = int(row.txn_count or 0)
        raw.append(
            {
                "category_id": row.category_id,
                "name": row.name or "Uncategorized",
                "color": row.color or "#94A3B8",
                "amount": amount,
                "transaction_count": count,
                "average_amount": money(Decimal(amount) / count) if count else ZERO,
                "largest_amount": money(row.largest),
                "is_essential": row.is_essential,
                "expense_nature": row.expense_nature.value if row.expense_nature else None,
            }
        )
    total = money(sum((item["amount"] for item in raw), ZERO))
    denom = abs(total)
    for item in raw:
        item["percentage"] = (
            float((item["amount"] / denom * 100).quantize(Decimal("0.1"))) if denom else 0.0
        )
    raw.sort(key=lambda item: item["amount"], reverse=True)
    return [CategorySpend(**item) for item in raw], total


def month_starts(start_date: date, end_date: date) -> list[date]:
    cursor = start_date.replace(day=1)
    months: list[date] = []
    while cursor <= end_date:
        months.append(cursor)
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


def month_end(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year, 12, 31)
    return date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)


def monthly_points(db: Session, *, start_date: date, end_date: date) -> list[MonthlyPoint]:
    points: list[MonthlyPoint] = []
    for month_start in month_starts(start_date, end_date):
        period_start = max(month_start, start_date)
        period_end = min(month_end(month_start), end_date)
        opening, baseline_effect = combined_opening(db, period_start)
        movement = movement_components(db, start_date=period_start, end_date=period_end)
        closing = money(
            opening + baseline_effect + movement.net_cash_flow + movement.adjustments_net
        )
        points.append(
            MonthlyPoint(
                month=month_start.strftime("%Y-%m"),
                label=month_start.strftime("%b %Y"),
                income=movement.income,
                expenses=movement.expenses_gross,
                refunds=movement.refunds,
                net_expenses=movement.expenses_net,
                adjustments_net=movement.adjustments_net,
                net_cash_flow=movement.net_cash_flow,
                opening_balance=opening,
                closing_balance=closing,
                baseline_effect=baseline_effect,
            )
        )
    return points


def previous_period(start_date: date, end_date: date) -> tuple[date, date]:
    length = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    return prev_start, prev_end


def income_sources(
    db: Session, *, start_date: date, end_date: date, account_id: uuid.UUID | None = None
) -> list[IncomeSource]:
    stmt = (
        select(
            Category.name,
            func.coalesce(func.sum(Transaction.amount), ZERO).label("amount"),
            func.count().label("txn_count"),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
            Transaction.transaction_type == TransactionType.INCOME,
        )
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
    )
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    rows = list(db.execute(stmt))
    total = money(sum((Decimal(row.amount or 0) for row in rows), ZERO))
    return [
        IncomeSource(
            name=row.name or "Uncategorized",
            amount=money(row.amount),
            percentage=float((Decimal(row.amount or 0) / total * 100).quantize(Decimal("0.1")))
            if total
            else 0.0,
            transaction_count=int(row.txn_count or 0),
        )
        for row in rows
    ]


def large_expenses(
    db: Session, *, start_date: date, end_date: date, limit: int = 8
) -> tuple[list[dict], Decimal | None]:
    amounts = list(
        db.scalars(
            select(Transaction.amount).where(
                Transaction.deleted_at.is_(None),
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
        )
    )
    if len(amounts) < 5:
        return [], None

    values = sorted(Decimal(value) for value in amounts)
    median = statistics.median(values)
    q1, q3 = statistics.quantiles(values, n=4, method="inclusive")[0], statistics.quantiles(
        values, n=4, method="inclusive")[2]
    iqr = q3 - q1
    threshold = money(q3 + Decimal("1.5") * iqr)
    if threshold <= 0:
        threshold = money(median * 2)

    stmt = (
        select(
            Transaction.id,
            Transaction.transaction_date,
            Transaction.description,
            Transaction.amount,
            Transaction.merchant_or_payee,
            Category.name.label("category_name"),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.amount > threshold,
        )
        .order_by(Transaction.amount.desc())
        .limit(limit)
    )
    rows = []
    for row in db.execute(stmt):
        multiple = float((Decimal(row.amount) / median).quantize(Decimal("0.1"))) if median else 0.0
        rows.append(
            {
                "id": row.id,
                "transaction_date": row.transaction_date,
                "description": row.description,
                "amount": money(row.amount),
                "category_name": row.category_name,
                "merchant_or_payee": row.merchant_or_payee,
                "threshold": threshold,
                "multiple_of_median": multiple,
            }
        )
    return rows, threshold


def spending_by_nature(db: Session, *, start_date: date, end_date: date) -> dict[str, Decimal]:
    categories, _ = category_breakdown(db, start_date=start_date, end_date=end_date)
    fixed = ZERO
    variable = ZERO
    for category in categories:
        if category.expense_nature == ExpenseNature.FIXED.value:
            fixed += category.amount
        elif category.expense_nature == ExpenseNature.VARIABLE.value:
            variable += category.amount
        else:
            fixed += category.amount / 2
            variable += category.amount / 2
    return {
        "fixed": money(fixed),
        "variable": money(variable),
        "essential": money(sum((item.amount for item in categories if item.is_essential), ZERO)),
        "discretionary": money(
            sum((item.amount for item in categories if not item.is_essential), ZERO)
        ),
    }


def recurring_candidates(
    db: Session, *, start_date: date, end_date: date, limit: int = 10
) -> list[dict]:
    label = func.coalesce(
        func.nullif(Transaction.merchant_or_payee, ""), Transaction.description
    ).label("label")
    stmt = (
        select(
            label,
            Category.name.label("category_name"),
            func.count().label("txn_count"),
            func.avg(Transaction.amount).label("average"),
            func.min(Transaction.amount).label("minimum"),
            func.max(Transaction.amount).label("maximum"),
            func.max(Transaction.transaction_date).label("last_seen"),
            func.count(func.distinct(func.date_trunc("month", Transaction.transaction_date))).label(
                "months"
            ),
        )
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.deleted_at.is_(None),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
            Transaction.transaction_type == TransactionType.EXPENSE,
        )
        .group_by(label, Category.name)
        .having(func.count() >= 3)
        .having(
            func.count(func.distinct(func.date_trunc("month", Transaction.transaction_date))) >= 2
        )
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = []
    for row in db.execute(stmt):
        average = Decimal(row.average or 0)
        minimum = Decimal(row.minimum or 0)
        maximum = Decimal(row.maximum or 0)
        if average:
            spread = float(((maximum - minimum) / average * 100).quantize(Decimal("0.1")))
        else:
            spread = 100.0
        rows.append(
            {
                "merchant_or_payee": row.label,
                "category_name": row.category_name,
                "transaction_count": int(row.txn_count or 0),
                "average_amount": money(average),
                "amount_range_pct": spread,
                "last_seen": row.last_seen,
                "suggestion": (
                    "Likely recurring: similar amount across multiple months. "
                    "Consider a recurring template."
                    if spread <= 25
                    else "Frequent merchant. Amounts vary, so review before automating."
                ),
            }
        )
    return rows
