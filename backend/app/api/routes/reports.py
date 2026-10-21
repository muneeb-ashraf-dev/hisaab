from __future__ import annotations

import math
import uuid
from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import DbSession, PageDep, resolve_range
from app.core.exceptions import ValidationError
from app.reports.service import (
    account_report,
    analytics_report,
    annual_report,
    annual_report_for_year,
    category_report,
    month_report,
    monthly_report,
    report_available_years,
)
from app.schemas.common import Page, PageMeta
from app.schemas.reports import (
    AccountReport,
    AnalyticsReport,
    AnnualReport,
    CategoryReport,
    MonthlyReport,
)
from app.schemas.transaction import LedgerEntry
from app.services.ledger import query_ledger

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly", response_model=MonthlyReport)
def get_monthly_report(
    db: DbSession,
    year: int | None = Query(default=None, ge=2000, le=2200),
    month: int | None = Query(default=None, ge=1, le=12),
    start_date: date | None = None,
    end_date: date | None = None,
) -> MonthlyReport:
    if start_date or end_date:
        start, end = resolve_range(start_date, end_date)
        return monthly_report(db, start_date=start, end_date=end)
    today = date.today()
    target_year = year or today.year
    target_month = month or today.month
    return month_report(db, year=target_year, month=target_month)


@router.get("/annual", response_model=AnnualReport)
def get_annual_report(
    db: DbSession,
    year: int | None = Query(default=None, ge=2000, le=2200),
    start_date: date | None = None,
    end_date: date | None = None,
) -> AnnualReport:
    if start_date or end_date:
        start, end = resolve_range(start_date, end_date)
        if (end - start).days > 366:
            raise ValidationError("Annual report range cannot exceed 366 days.")
        return annual_report(db, start_date=start, end_date=end)
    target_year = year or date.today().year
    return annual_report_for_year(db, target_year)


@router.get("/categories", response_model=CategoryReport)
def get_category_report(
    db: DbSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> CategoryReport:
    start, end = resolve_range(start_date, end_date)
    return category_report(db, start_date=start, end_date=end)


@router.get("/categories/{category_id}/transactions", response_model=Page[LedgerEntry])
def category_drilldown(
    db: DbSession,
    category_id: uuid.UUID,
    page: PageDep,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Page[LedgerEntry]:
    start, end = resolve_range(start_date, end_date)
    items, total = query_ledger(
        db,
        page=page.page,
        page_size=page.page_size,
        start_date=start,
        end_date=end,
        category_id=category_id,
        sort_by="entry_date",
        sort_dir="desc",
    )
    return Page(
        items=items,
        meta=PageMeta(
            page=page.page,
            page_size=page.page_size,
            total=total,
            total_pages=max(math.ceil(total / page.page_size), 1),
        ),
    )


@router.get("/accounts/{account_id}", response_model=AccountReport)
def get_account_report(
    db: DbSession,
    account_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AccountReport:
    start, end = resolve_range(start_date, end_date)
    return account_report(
        db, account_id=account_id, start_date=start, end_date=end
    )


@router.get("/analytics", response_model=AnalyticsReport)
def get_analytics(
    db: DbSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AnalyticsReport:
    start, end = resolve_range(start_date, end_date)
    return analytics_report(db, start_date=start, end_date=end)


@router.get("/years", response_model=list[int])
def get_years(db: DbSession) -> list[int]:
    return report_available_years(db)
