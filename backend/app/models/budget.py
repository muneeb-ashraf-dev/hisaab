from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import BudgetPeriodType


class Budget(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("warning_threshold BETWEEN 1 AND 100", name="threshold_range"),
        CheckConstraint(
            "date_trunc('month', period_start)::date = period_start",
            name="period_start_is_month_start",
        ),
        CheckConstraint("period_type IN ('monthly')", name="period_type_valid"),
        Index(
            "uq_budgets_overall_month",
            "period_start",
            unique=True,
            postgresql_where=text("category_id IS NULL"),
        ),
        Index(
            "uq_budgets_category_month",
            "category_id",
            "period_start",
            unique=True,
            postgresql_where=text("category_id IS NOT NULL"),
        ),
    )

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    period_type: Mapped[BudgetPeriodType] = mapped_column(
        enum_column(BudgetPeriodType, length=20),
        nullable=False,
        default=BudgetPeriodType.MONTHLY,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    warning_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    notes: Mapped[str | None] = mapped_column(Text)

    category: Mapped[Category | None] = relationship(lazy="joined")  # noqa: F821
