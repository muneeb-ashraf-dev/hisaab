from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import (
    OccurrenceStatus,
    RecurringFrequency,
    TransactionType,
)


class RecurringTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "recurring_templates"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("interval_count BETWEEN 1 AND 12", name="interval_range"),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="end_after_start",
        ),
        CheckConstraint(
            "transaction_type IN ('income', 'expense')",
            name="only_income_or_expense",
        ),
        CheckConstraint(
            "frequency IN ('weekly', 'monthly', 'quarterly', 'yearly')",
            name="frequency_valid",
        ),
        Index("ix_recurring_templates_next_due", "next_due_date"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        enum_column(TransactionType, length=30),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_or_payee: Mapped[str | None] = mapped_column(String(160))
    payment_method: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[RecurringFrequency] = mapped_column(
        enum_column(RecurringFrequency, length=20),
        nullable=False,
        default=RecurringFrequency.MONTHLY,
    )
    interval_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_post: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    account: Mapped[Account] = relationship(lazy="joined")  # noqa: F821
    category: Mapped[Category] = relationship(lazy="joined")  # noqa: F821
    occurrences: Mapped[list[RecurringOccurrence]] = relationship(
        back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )


class RecurringOccurrence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Idempotency guard: one row per template/due-date pair."""

    __tablename__ = "recurring_occurrences"
    __table_args__ = (
        UniqueConstraint("template_id", "due_date", name="uq_recurring_occurrence"),
        CheckConstraint(
            "status <> 'posted' OR transaction_id IS NOT NULL",
            name="posted_has_transaction",
        ),
        CheckConstraint(
            "status IN ('pending', 'posted', 'skipped')",
            name="status_valid",
        ),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recurring_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OccurrenceStatus] = mapped_column(
        enum_column(OccurrenceStatus, length=20),
        nullable=False,
        default=OccurrenceStatus.PENDING,
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )

    template: Mapped[RecurringTemplate] = relationship(back_populates="occurrences")
