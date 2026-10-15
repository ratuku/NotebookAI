"""Persist retrieval metrics; historical/unmeasured results remain null."""

import sqlalchemy as sa
from alembic import op

revision = "7a4c239f0821"
down_revision = "2d519c617a30"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("questions", sa.Column("retrieval_stats", sa.JSON(), nullable=True))
    op.add_column("artifacts", sa.Column("retrieval_stats", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("artifacts", "retrieval_stats")
    op.drop_column("questions", "retrieval_stats")
