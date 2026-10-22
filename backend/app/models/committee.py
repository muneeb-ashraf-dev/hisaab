from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Committee(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A monthly committee plan (a fixed number of monthly installments).

    Committees are planning records only. They are deliberately not linked to
    accounts or transactions, so they never change balances or income/expense
    reports. Paid and remaining amounts are derived from the plan period and the
    current month rather than stored redundantly.
    """

    __tablename__ = "committees"
    __table_args__ = (
        CheckConstraint("monthly_amount > 0", name="amount_positive"),
        CheckConstraint("prior_paid_installments >= 0", name="prior_paid_non_negative"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("end_month >= start_month", name="period_order"),
        CheckConstraint(
            "date_trunc('month', start_month)::date = start_month",
            name="start_month_is_month_start",
        ),
        CheckConstraint(
            "date_trunc('month', end_month)::date = end_month",
            name="end_month_is_month_start",
        ),
        Index("ix_committees_start_month", "start_month"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    start_month: Mapped[date] = mapped_column(Date, nullable=False)
    end_month: Mapped[date] = mapped_column(Date, nullable=False)
    # Historical installments paid before this committee was tracked from
    # transactions. They are planning data and never create ledger entries.
    prior_paid_installments: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    notes: Mapped[str | None] = mapped_column(Text)
