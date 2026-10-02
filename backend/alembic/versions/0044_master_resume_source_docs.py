"""master_resume_source_docs + source_doc_id FK target."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "master_resume_source_docs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(512), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_master_resume_source_docs_user_id",
        "master_resume_source_docs",
        ["user_id"],
    )

    bind = op.get_bind()
    insp = sa.inspect(bind)
    fks = {fk["name"] for fk in insp.get_foreign_keys("master_resume_chunks")}
    for fk_name in fks:
        cols = next(
            fk["constrained_columns"]
            for fk in insp.get_foreign_keys("master_resume_chunks")
            if fk["name"] == fk_name
        )
        if "source_doc_id" in cols:
            op.drop_constraint(fk_name, "master_resume_chunks", type_="foreignkey")

    op.create_foreign_key(
        "fk_master_resume_chunks_source_doc_id",
        "master_resume_chunks",
        "master_resume_source_docs",
        ["source_doc_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_master_resume_chunks_source_doc_id",
        "master_resume_chunks",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "master_resume_chunks_source_doc_id_fkey",
        "master_resume_chunks",
        "master_resumes",
        ["source_doc_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_index("ix_master_resume_source_docs_user_id", "master_resume_source_docs")
    op.drop_table("master_resume_source_docs")
