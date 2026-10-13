"""Platform notification settings (admin-configurable digest send hour)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0053_notification_platform_settings"
down_revision: str | None = "0052_cw_seniority_digest_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_platform_settings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "singleton_key",
            sa.String(length=32),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "job_alert_digest_hour_local",
            sa.Integer(),
            nullable=False,
            server_default="18",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by_admin_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "job_alert_digest_hour_local BETWEEN 0 AND 23",
            name="ck_notification_platform_digest_hour",
        ),
        sa.UniqueConstraint("singleton_key", name="uq_notification_platform_singleton"),
    )
    op.execute(
        """
        INSERT INTO notification_platform_settings (id, singleton_key, job_alert_digest_hour_local)
        VALUES (gen_random_uuid(), 'default', 18)
        """
    )


def downgrade() -> None:
    op.drop_table("notification_platform_settings")
