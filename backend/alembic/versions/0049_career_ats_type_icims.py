"""Add icims to career_ats_type enum."""

from __future__ import annotations

from alembic import op

revision: str = "0049_career_ats_type_icims"
down_revision: str | None = "0048_watched_company_canonical_poll_url"
branch_labels = None
depends_on = None

_CAREER_ATS_TYPE_ENUM = "career_ats_type"


def upgrade() -> None:
    op.execute(
        f"ALTER TYPE {_CAREER_ATS_TYPE_ENUM} ADD VALUE IF NOT EXISTS 'icims'"
    )


def downgrade() -> None:
    pass
