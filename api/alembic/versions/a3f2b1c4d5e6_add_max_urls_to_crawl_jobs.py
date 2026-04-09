"""add max_urls to crawl_jobs

Revision ID: a3f2b1c4d5e6
Revises: 8c61373c9db7
Create Date: 2026-04-07 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a3f2b1c4d5e6"
down_revision: Union[str, Sequence[str], None] = "8c61373c9db7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crawl_jobs", sa.Column("max_urls", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("crawl_jobs", "max_urls")
