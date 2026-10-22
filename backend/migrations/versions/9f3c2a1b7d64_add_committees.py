"""add committees

Revision ID: 9f3c2a1b7d64
Revises: 95839572a146
Create Date: 2026-10-22 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f3c2a1b7d64"
down_revision: str | None = "95839572a146"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "committees",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("monthly_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("start_month", sa.Date(), nullable=False),
        sa.Column("end_month", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "monthly_amount > 0", name=op.f("ck_committees_amount_positive")
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_committees_name_not_blank")
        ),
        sa.CheckConstraint(
            "end_month >= start_month", name=op.f("ck_committees_period_order")
        ),
        sa.CheckConstraint(
            "date_trunc('month', start_month)::date = start_month",
            name=op.f("ck_committees_start_month_is_month_start"),
        ),
        sa.CheckConstraint(
            "date_trunc('month', end_month)::date = end_month",
            name=op.f("ck_committees_end_month_is_month_start"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_committees")),
    )
    op.create_index(
        "ix_committees_start_month", "committees", ["start_month"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_committees_start_month", table_name="committees")
    op.drop_table("committees")
