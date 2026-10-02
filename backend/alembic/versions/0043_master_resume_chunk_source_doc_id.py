"""Add source_doc_id to master_resume_chunks."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "master_resume_chunks",
        sa.Column(
            "source_doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("master_resumes.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_master_resume_chunks_source_doc_id",
        "master_resume_chunks",
        ["source_doc_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_master_resume_chunks_source_doc_id",
        table_name="master_resume_chunks",
    )
    op.drop_column("master_resume_chunks", "source_doc_id")
