"""Record the query embedding time separately on each query row.

Without this, `retrieval_ms` folded the embedding into the search and the latency panel
reported an embedding share of zero, which is the opposite of the finding the panel exists
to show.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "queries", sa.Column("embed_ms", sa.Float(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("queries", "embed_ms")
