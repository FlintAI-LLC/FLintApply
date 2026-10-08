"""Daily product metric counters for admin monitoring."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0046_daily_product_metrics"
down_revision = "0045_chunk_embedding_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_product_metrics",
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("metric_date", "metric_key"),
    )


def downgrade() -> None:
    op.drop_table("daily_product_metrics")
