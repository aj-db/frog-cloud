"""add status_message to crawl_jobs

Revision ID: c5d8e9f01234
Revises: b4c7d8e9f012
Create Date: 2026-04-08 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c5d8e9f01234"
down_revision: Union[str, Sequence[str], None] = "b4c7d8e9f012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crawl_jobs", sa.Column("status_message", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("crawl_jobs", "status_message")
