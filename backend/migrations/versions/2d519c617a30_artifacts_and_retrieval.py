"""Saved artifacts and retrieval method provenance."""

import sqlalchemy as sa
from alembic import op

revision = "2d519c617a30"
down_revision = "150b2498c744"
branch_labels = None
depends_on = None


def upgrade():
    # Existing answers used the original hybrid pipeline (normal).
    op.add_column(
        "questions",
        sa.Column("retrieval_method", sa.String(20), nullable=False, server_default="normal"),
    )
    op.alter_column("questions", "retrieval_method", server_default=None)
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "notebook_id",
            sa.String(36),
            sa.ForeignKey("notebooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("retrieval_method", sa.String(20), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_artifacts_notebook_id", "artifacts", ["notebook_id"])


def downgrade():
    op.drop_table("artifacts")
    op.drop_column("questions", "retrieval_method")
