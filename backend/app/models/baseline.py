from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BaselineSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Auditable record of the historical position before tracking began.

    These figures are *not* transactions. They must never be included in
    monthly income or expense reports.
    """

    __tablename__ = "baseline_snapshots"
    __table_args__ = (
        UniqueConstraint("name", name="uq_baseline_snapshots_name"),
        CheckConstraint("length(trim(notes)) > 0", name="notes_required"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    baseline_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)

    accounts: Mapped[list[BaselineAccount]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan", lazy="selectin"
    )


class BaselineAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "baseline_accounts"
    __table_args__ = (
        UniqueConstraint("baseline_id", "account_id", name="uq_baseline_account"),
        CheckConstraint("original_funds >= 0", name="original_non_negative"),
        CheckConstraint("historical_usage >= 0", name="usage_non_negative"),
        CheckConstraint(
            "original_funds = historical_usage + opening_balance",
            name="original_reconciles",
        ),
        CheckConstraint(
            "length(trim(currency)) = 3",
            name="currency_iso4217",
        ),
    )

    baseline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("baseline_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    original_funds: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    historical_usage: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")

    snapshot: Mapped[BaselineSnapshot] = relationship(back_populates="accounts")
    account: Mapped[Account] = relationship(lazy="joined")  # noqa: F821
    usage_items: Mapped[list[BaselineUsageItem]] = relationship(
        back_populates="baseline_account", cascade="all, delete-orphan", lazy="selectin"
    )


class BaselineUsageItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "baseline_usage_items"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("length(trim(description)) > 0", name="description_not_blank"),
    )

    baseline_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("baseline_accounts.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)

    baseline_account: Mapped[BaselineAccount] = relationship(back_populates="usage_items")
