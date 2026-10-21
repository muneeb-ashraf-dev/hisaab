from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import GoalStatus


class FinancialGoal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "financial_goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="target_positive"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "status IN ('active', 'completed', 'paused', 'cancelled')",
            name="status_valid",
        ),
        Index("ix_financial_goals_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[GoalStatus] = mapped_column(
        enum_column(GoalStatus, length=20),
        nullable=False,
        default=GoalStatus.ACTIVE,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    contributions: Mapped[list[GoalContribution]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", lazy="selectin"
    )


class GoalContribution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Money set aside toward a goal.

    Contributions are intentionally not modelled as income or expenses: moving
    money aside is not spending. Current goal progress is always derived from
    these rows rather than stored redundantly.
    """

    __tablename__ = "goal_contributions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_goal_contributions_date", "contribution_date"),
    )

    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_goals.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    contribution_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))

    goal: Mapped[FinancialGoal] = relationship(back_populates="contributions")
