"""Add embedding_model to master_resume_chunks."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

_EMBEDDING_MODEL = "text-embedding-3-small"


def upgrade() -> None:
    op.add_column(
        "master_resume_chunks",
        sa.Column("embedding_model", sa.Text(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE master_resume_chunks "
            "SET embedding_model = :model "
            "WHERE embedding_model IS NULL"
        ).bindparams(model=_EMBEDDING_MODEL)
    )


def downgrade() -> None:
    op.drop_column("master_resume_chunks", "embedding_model")
