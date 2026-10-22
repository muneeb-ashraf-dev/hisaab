"""committee payment tracking

Revision ID: 2f7a1c9d4b30
Revises: 9f3c2a1b7d64
Create Date: 2026-10-22 00:00:01.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2f7a1c9d4b30"
down_revision: str | None = "9f3c2a1b7d64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "committees",
        sa.Column(
            "prior_paid_installments",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_committees_prior_paid_non_negative"),
        "committees",
        "prior_paid_installments >= 0",
    )

    op.add_column(
        "transactions",
        sa.Column("committee_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_transactions_committee_id_committees"),
        "transactions",
        "committees",
        ["committee_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_transactions_committee",
        "transactions",
        ["committee_id"],
        unique=False,
    )
    op.create_check_constraint(
        op.f("ck_transactions_committee_only_for_expense"),
        "transactions",
        "transaction_type = 'expense' OR committee_id IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_transactions_committee_only_for_expense"),
        "transactions",
        type_="check",
    )
    op.drop_index("ix_transactions_committee", table_name="transactions")
    op.drop_constraint(
        op.f("fk_transactions_committee_id_committees"),
        "transactions",
        type_="foreignkey",
    )
    op.drop_column("transactions", "committee_id")

    op.drop_constraint(
        op.f("ck_committees_prior_paid_non_negative"),
        "committees",
        type_="check",
    )
    op.drop_column("committees", "prior_paid_installments")
