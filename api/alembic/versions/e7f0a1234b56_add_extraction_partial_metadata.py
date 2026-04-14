"""add extraction_partial and extraction_metadata to crawl_jobs

Revision ID: e7f0a1234b56
Revises: d6e9f01234a5
Create Date: 2026-04-08 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "e7f0a1234b56"
down_revision: Union[str, Sequence[str], None] = "d6e9f01234a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "crawl_jobs",
        sa.Column("extraction_partial", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "crawl_jobs",
        sa.Column("extraction_metadata", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crawl_jobs", "extraction_metadata")
    op.drop_column("crawl_jobs", "extraction_partial")
