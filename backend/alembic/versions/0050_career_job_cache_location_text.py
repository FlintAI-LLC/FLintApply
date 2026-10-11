"""Widen career_job_cache.location for multi-state listings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0050_job_cache_location_text"
down_revision: str | None = "0049_career_ats_icims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "career_job_cache",
        "location",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
        postgresql_using="location::text",
    )


def downgrade() -> None:
    op.alter_column(
        "career_job_cache",
        "location",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
        postgresql_using="left(location, 500)",
    )
