"""Add amazon_jobs to career_ats_type enum."""

from __future__ import annotations

from alembic import op

revision: str = "0051_career_ats_amazon_jobs"
down_revision: str | None = "0050_career_job_cache_location_text"
branch_labels = None
depends_on = None

_CAREER_ATS_TYPE_ENUM = "career_ats_type"


def upgrade() -> None:
    op.execute(
        f"ALTER TYPE {_CAREER_ATS_TYPE_ENUM} ADD VALUE IF NOT EXISTS 'amazon_jobs'"
    )


def downgrade() -> None:
    pass
