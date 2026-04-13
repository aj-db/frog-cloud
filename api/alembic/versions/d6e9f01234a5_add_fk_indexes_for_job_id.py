"""add FK indexes for job_id on crawl_pages, crawl_issues, crawl_links

Revision ID: d6e9f01234a5
Revises: c5d8e9f01234
Create Date: 2026-04-08 21:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d6e9f01234a5"
down_revision: Union[str, Sequence[str], None] = "c5d8e9f01234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_crawl_pages_job_id", "crawl_pages", ["job_id"]),
    ("ix_crawl_links_job_id", "crawl_links", ["job_id"]),
    ("ix_crawl_issues_job_id", "crawl_issues", ["job_id"]),
    ("ix_crawl_issues_job_id_issue_type", "crawl_issues", ["job_id", "issue_type"]),
]


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("COMMIT")
        for name, table, cols in _INDEXES:
            col_list = ", ".join(cols)
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} ({col_list})"
            )
    else:
        for name, table, cols in _INDEXES:
            op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table, _cols in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
