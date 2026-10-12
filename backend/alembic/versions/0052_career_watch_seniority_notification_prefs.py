"""Career Watch seniority filter + notification digest prefs."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0052_cw_seniority_digest_prefs"
down_revision: str | None = "0051_career_ats_amazon_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_watched_companies",
        sa.Column(
            "seniority_levels",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="America/Los_Angeles",
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "instant_job_alert_email",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_preferences", "instant_job_alert_email")
    op.drop_column("notification_preferences", "timezone")
    op.drop_column("user_watched_companies", "seniority_levels")
