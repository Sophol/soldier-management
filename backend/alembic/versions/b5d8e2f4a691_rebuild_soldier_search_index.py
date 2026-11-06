"""rebuild the soldier search index (ft_soldiers_search)

The soldiers whose military ID was padded by f2a9d4b6c813 (652 -> 000652) dropped out of the MySQL FULLTEXT index:
searching their ID, or even their name, found nothing. A later edit puts a row back only if it changes one of the
indexed columns, so the index is rebuilt from the table.

Revision ID: b5d8e2f4a691
Revises: a7c3e9d51f20
Create Date: 2026-11-05 18:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b5d8e2f4a691'
down_revision: str | Sequence[str] | None = 'a7c3e9d51f20'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_COLUMNS = ("name_kh", "name_latin", "military_id", "national_id", "phone")  # as in d4e7a1c90b52


def upgrade() -> None:
    """Upgrade schema."""
    if op.get_bind().dialect.name != 'mysql':  # PostgreSQL searches with ILIKE + pg_trgm: nothing to rebuild
        return
    # as when it was created: stopwords off, or ngram drops every token containing one (such as "a")
    op.execute("SET SESSION innodb_ft_enable_stopword = OFF")
    op.drop_index('ft_soldiers_search', table_name='soldiers')
    op.execute(f"CREATE FULLTEXT INDEX ft_soldiers_search ON soldiers ({', '.join(SEARCH_COLUMNS)}) WITH PARSER ngram")


def downgrade() -> None:
    """Downgrade schema."""
    # the rebuilt index is the same index: nothing to undo
    pass
