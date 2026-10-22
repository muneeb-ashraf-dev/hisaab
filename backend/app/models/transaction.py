from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import TransactionType


class Transaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "transaction_type NOT IN ('income', 'expense') OR category_id IS NOT NULL",
            name="category_required_for_income_expense",
        ),
        CheckConstraint(
            "transaction_type NOT IN ('adjustment_increase', 'adjustment_decrease') "
            "OR category_id IS NULL",
            name="adjustments_have_no_category",
        ),
        CheckConstraint(
            "deleted_at IS NULL OR deleted_reason IS NOT NULL",
            name="deleted_has_reason",
        ),
        CheckConstraint(
            "transaction_type <> 'refund' OR related_transaction_id IS NOT NULL",
            name="refund_has_original",
        ),
        CheckConstraint(
            "transaction_type = 'expense' OR committee_id IS NULL",
            name="committee_only_for_expense",
        ),
        CheckConstraint(
            "transaction_type IN ('income', 'expense', 'refund', "
            "'adjustment_increase', 'adjustment_decrease')",
            name="transaction_type_valid",
        ),
        Index("ix_transactions_date", "transaction_date"),
        Index(
            "ix_transactions_active_date",
            "transaction_date",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_transactions_account_date", "account_id", "transaction_date"),
        Index("ix_transactions_category", "category_id"),
        Index("ix_transactions_committee", "committee_id"),
        Index("ix_transactions_type", "transaction_type"),
        Index(
            "uq_transactions_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        enum_column(TransactionType, length=30),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    committee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("committees.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_or_payee: Mapped[str | None] = mapped_column(String(160))
    payment_method: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)
    related_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    account: Mapped[Account] = relationship(lazy="joined")  # noqa: F821
    category: Mapped[Category | None] = relationship(lazy="joined")  # noqa: F821
    committee: Mapped[Committee | None] = relationship(lazy="joined")  # noqa: F821
    related_transaction: Mapped[Transaction | None] = relationship(
        remote_side="Transaction.id", back_populates="refunds"
    )
    refunds: Mapped[list[Transaction]] = relationship(back_populates="related_transaction")
