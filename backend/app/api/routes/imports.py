from __future__ import annotations

from datetime import date

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import Response

from app.api.deps import DbSession, optional_range, resolve_range
from app.reports.service import month_report, monthly_report
from app.schemas.imports import ImportCommitResult, ImportPreview
from app.services import csv_io

router = APIRouter(tags=["import / export"])


def _form_flag(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@router.post("/imports/preview", response_model=ImportPreview)
async def preview_import(
    db: DbSession,
    file: UploadFile = File(...),
) -> ImportPreview:
    content = await file.read()
    return csv_io.preview_import(
        db, content=content, filename=file.filename or "transactions.csv"
    )


@router.post("/imports/commit", response_model=ImportCommitResult)
async def commit_import(
    db: DbSession,
    file: UploadFile = File(...),
    skip_duplicates: str | None = Form(None),
    create_missing_categories: str | None = Form(None),
) -> ImportCommitResult:
    content = await file.read()
    return csv_io.commit_import(
        db,
        content=content,
        filename=file.filename or "transactions.csv",
        # Multipart booleans are parsed explicitly: an omitted optional flag is
        # coerced to False by the form parser, which would silently disable the
        # documented "skip duplicates" default.
        skip_duplicates=_form_flag(skip_duplicates, default=True),
        create_missing_categories=_form_flag(create_missing_categories, default=False),
    )


@router.get("/imports/sample.csv")
def download_sample() -> Response:
    return Response(
        content=csv_io.sample_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="transactions-template.csv"'
        },
    )


@router.get("/exports/transactions.csv")
def export_transactions(
    db: DbSession,
    start_date: date | None = None,
    end_date: date | None = None,
    account_id: str | None = None,
    include_transfers: bool = True,
) -> Response:
    start, end = optional_range(start_date, end_date)
    uid = None
    if account_id:
        from uuid import UUID

        try:
            uid = UUID(account_id)
        except ValueError:
            from app.core.exceptions import ValidationError

            raise ValidationError("account_id must be a valid UUID.") from None
    content = csv_io.export_transactions_csv(
        db,
        start_date=start,
        end_date=end,
        account_id=uid,
        include_transfers=include_transfers,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="transactions-export.csv"'
        },
    )


@router.get("/exports/monthly-report.csv")
def export_monthly_report(
    db: DbSession,
    year: int | None = Query(default=None, ge=2000, le=2200),
    month: int | None = Query(default=None, ge=1, le=12),
    start_date: date | None = None,
    end_date: date | None = None,
) -> Response:
    if start_date or end_date:
        start, end = resolve_range(start_date, end_date)
        report = monthly_report(db, start_date=start, end_date=end)
    else:
        today = date.today()
        report = month_report(db, year=year or today.year, month=month or today.month)
    content = csv_io.report_csv(report)
    filename = f"monthly-report-{report.start_date:%Y-%m}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
