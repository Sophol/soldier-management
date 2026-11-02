"""soldier list at scale: rank_sort column and search indexes

Revision ID: d4e7a1c90b52
Revises: c161a779abd4
Create Date: 2026-11-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e7a1c90b52'
down_revision: Union[str, Sequence[str], None] = 'c161a779abd4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# the columns the soldier list's free-text search (q) looks in
SEARCH_COLUMNS = ("name_kh", "name_latin", "military_id", "national_id", "phone")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('soldiers', sa.Column('rank_sort', sa.Integer(), nullable=True))
    op.execute("UPDATE soldiers SET rank_sort = (SELECT ranks.sort_order FROM ranks WHERE ranks.id = soldiers.current_rank_id)")
    op.create_index('ix_soldiers_rank_sort_desc', 'soldiers', [sa.text('rank_sort DESC'), 'name_kh'])
    op.create_index('ix_soldiers_rank_sort_asc', 'soldiers', ['rank_sort', 'name_kh'])

    # search "contains" without reading the whole table (not declared on the model: dialect-specific)
    dialect = op.get_bind().dialect.name
    if dialect == 'mysql':
        # ngram parser: works for Khmer (no spaces between words). Stopwords off: ngram drops every token that
        # contains a stopword (such as "a"), which would make Latin names unsearchable
        op.execute("SET SESSION innodb_ft_enable_stopword = OFF")
        op.execute(f"CREATE FULLTEXT INDEX ft_soldiers_search ON soldiers ({', '.join(SEARCH_COLUMNS)}) WITH PARSER ngram")
    elif dialect == 'postgresql':
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        for col in SEARCH_COLUMNS:  # trigram indexes serve ILIKE '%...%' directly
            op.execute(f"CREATE INDEX ix_soldiers_{col}_trgm ON soldiers USING gin ({col} gin_trgm_ops)")


def downgrade() -> None:
    """Downgrade schema."""
    dialect = op.get_bind().dialect.name
    if dialect == 'mysql':
        op.drop_index('ft_soldiers_search', table_name='soldiers')
    elif dialect == 'postgresql':
        for col in SEARCH_COLUMNS:
            op.drop_index(f'ix_soldiers_{col}_trgm', table_name='soldiers')
    op.drop_index('ix_soldiers_rank_sort_asc', table_name='soldiers')
    op.drop_index('ix_soldiers_rank_sort_desc', table_name='soldiers')
    op.drop_column('soldiers', 'rank_sort')
