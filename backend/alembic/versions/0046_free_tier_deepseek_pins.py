"""Seed tier_step_llm_configs for free plan → DeepSeek.

Free-tier users route all editable pipeline steps through deepseek-v4-flash.
This is substantially cheaper than Gemini Flash and provides comparable quality
for free-tier volumes.

Inherited-client steps (phase3_truthfulness, phase4_narrative, phase4_rank,
tone_lint, title_fit_insights) and global-only steps (company_intel) are
excluded — they cannot have tier-level pins per model_registry.py rules.

Safe to re-run: inserts are skipped when an active row already exists.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

_PLAN_CODE = "free"
_PROVIDER = "deepseek"
_MODEL = "deepseek-v4-flash"
_NOTES = "Bootstrapped: free tier cost reduction — DeepSeek over Gemini Flash"

# All editable steps (excludes INHERITED_CLIENT_STEPS and GLOBAL_ONLY_STEPS).
_FREE_TIER_STEPS = [
    "resume_structure",
    "phase1_keywords",
    "phase2_audit",
    "phase3_rewrite",
    "phase4_qa",
    "polish",
    "mechanical_fixes",
    "cover_letter",
    "job_fit",
    "job_title_suggestions",
    "story",
    "story_coach",
    "story_interview",
    "story_verify",
    "chat",
    "checkup",
]


def upgrade() -> None:
    conn = op.get_bind()
    for step in _FREE_TIER_STEPS:
        existing = conn.execute(
            sa.text(
                "SELECT id FROM tier_step_llm_configs "
                "WHERE plan_code = :plan AND step = :step AND is_active = true"
            ),
            {"plan": _PLAN_CODE, "step": step},
        ).fetchone()
        if existing is not None:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO tier_step_llm_configs "
                "(id, plan_code, step, provider, model_string, is_active, notes, "
                " created_by_admin_id, created_at, updated_at) "
                "VALUES (:id, :plan, :step, :provider, :model, true, :notes, "
                "        null, now(), now())"
            ),
            {
                "id": str(uuid.uuid4()),
                "plan": _PLAN_CODE,
                "step": step,
                "provider": _PROVIDER,
                "model": _MODEL,
                "notes": _NOTES,
            },
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM tier_step_llm_configs "
            "WHERE plan_code = :plan AND provider = :provider AND model_string = :model "
            "  AND notes = :notes"
        ).bindparams(
            plan=_PLAN_CODE,
            provider=_PROVIDER,
            model=_MODEL,
            notes=_NOTES,
        )
    )
