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

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Transfer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single atomic record representing both sides of an internal transfer.

    No money is created or destroyed: the source decreases and the destination
    increases by the same amount. Transfers are deliberately not income or
    expense transactions, so they can never leak into spending reports.
    """

    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("from_account_id <> to_account_id", name="distinct_accounts"),
        CheckConstraint(
            "deleted_at IS NULL OR deleted_reason IS NOT NULL",
            name="deleted_has_reason",
        ),
        Index("ix_transfers_date", "transfer_date"),
        Index("ix_transfers_from_date", "from_account_id", "transfer_date"),
        Index("ix_transfers_to_date", "to_account_id", "transfer_date"),
        Index(
            "uq_transfers_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    from_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    to_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    from_account: Mapped[Account] = relationship(  # noqa: F821
        foreign_keys=[from_account_id], lazy="joined"
    )
    to_account: Mapped[Account] = relationship(  # noqa: F821
        foreign_keys=[to_account_id], lazy="joined"
    )
