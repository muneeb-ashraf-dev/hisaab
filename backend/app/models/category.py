from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import CategoryType, ExpenseNature


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("name", name="uq_categories_name"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "color ~ '^#[0-9A-Fa-f]{6}$'",
            name="color_hex",
        ),
        CheckConstraint(
            "category_type IN ('income', 'expense')",
            name="category_type_valid",
        ),
        CheckConstraint(
            "expense_nature IN ('fixed', 'variable', 'mixed')",
            name="expense_nature_valid",
        ),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    category_type: Mapped[CategoryType] = mapped_column(
        enum_column(CategoryType, length=20),
        nullable=False,
    )
    parent_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="Circle")
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366F1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_essential: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expense_nature: Mapped[ExpenseNature] = mapped_column(
        enum_column(ExpenseNature, length=20),
        nullable=False,
        default=ExpenseNature.VARIABLE,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    parent: Mapped[Category | None] = relationship(
        remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list[Category]] = relationship(back_populates="parent")
