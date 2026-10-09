"""Backfill users.tier from active subscriptions and tier_override grants."""

from __future__ import annotations

from alembic import op

revision = "0047_sync_users_tier_backfill"
down_revision = "0046_daily_product_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users u
        SET tier = 'pro'
        WHERE u.tier = 'free'
          AND (
            EXISTS (
              SELECT 1
              FROM subscriptions s
              WHERE s.user_id = u.id
                AND s.status IN (
                  'active', 'trialing', 'grace', 'cancel_at_period_end'
                )
                AND s.period_start <= now()
                AND now() <= s.period_end
            )
            OR EXISTS (
              SELECT 1
              FROM admin_user_grants g
              WHERE g.user_id = u.id
                AND g.grant_type = 'tier_override'
                AND g.revoked_at IS NULL
                AND (g.expires_at IS NULL OR g.expires_at > now())
            )
          )
        """
    )


def downgrade() -> None:
    # Irreversible data repair — do not mass-downgrade paid users.
    pass
