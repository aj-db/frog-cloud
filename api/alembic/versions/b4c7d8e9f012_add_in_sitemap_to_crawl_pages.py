"""add in_sitemap to crawl_pages

Revision ID: b4c7d8e9f012
Revises: a3f2b1c4d5e6
Create Date: 2026-04-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b4c7d8e9f012"
down_revision: Union[str, Sequence[str], None] = "a3f2b1c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crawl_pages", sa.Column("in_sitemap", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("crawl_pages", "in_sitemap")
