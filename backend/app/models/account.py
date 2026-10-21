from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import AccountType


class Account(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("name", name="uq_accounts_name"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso4217"),
        CheckConstraint(
            "account_type IN ('checking', 'savings', 'cash', 'other')",
            name="account_type_valid",
        ),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        enum_column(AccountType, length=20),
        nullable=False,
        default=AccountType.CHECKING,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PKR")
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    opening_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
