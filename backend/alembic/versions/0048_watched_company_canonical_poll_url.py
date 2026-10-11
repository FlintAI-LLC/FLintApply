"""Add canonical_poll_url to watched_companies."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0048_watched_company_canonical_poll_url"
down_revision: str | None = "0047_sync_users_tier_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "watched_companies",
        sa.Column("canonical_poll_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("watched_companies", "canonical_poll_url")
