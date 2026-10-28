"""saved filters

Revision ID: 4041315f7333
Revises: b66c078d3711
Create Date: 2026-10-28 20:32:17.958142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4041315f7333'
down_revision: Union[str, Sequence[str], None] = 'b66c078d3711'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('saved_filters',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('module', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('params', sa.JSON(), nullable=False),
    sa.Column('shared', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_saved_filters_module'), 'saved_filters', ['module'], unique=False)
    op.create_index(op.f('ix_saved_filters_user_id'), 'saved_filters', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_saved_filters_user_id'), table_name='saved_filters')
    op.drop_index(op.f('ix_saved_filters_module'), table_name='saved_filters')
    op.drop_table('saved_filters')
