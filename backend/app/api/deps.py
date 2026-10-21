from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.exceptions import ValidationError

DbSession = Annotated[Session, Depends(get_db)]


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ) -> None:
        self.page = page
        self.page_size = page_size


PageDep = Annotated[PageParams, Depends()]


def resolve_range(
    start_date: date | None,
    end_date: date | None,
    *,
    default_days: int | None = None,
) -> tuple[date, date]:
    today = date.today()
    if start_date is None and end_date is None:
        if default_days is None:
            start = today.replace(day=1)
            end = today
        else:
            start = today - timedelta(days=default_days - 1)
            end = today
    else:
        start = start_date or (end_date - timedelta(days=29) if end_date else today)
        end = end_date or today
    if end < start:
        raise ValidationError("end_date must be on or after start_date.")
    if (end - start).days > 366 * 5:
        raise ValidationError("Date range cannot exceed 5 years.")
    return start, end


def optional_range(
    start_date: date | None, end_date: date | None
) -> tuple[date | None, date | None]:
    if start_date and end_date and end_date < start_date:
        raise ValidationError("end_date must be on or after start_date.")
    return start_date, end_date
