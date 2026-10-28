"""soldier policy fields nationality ethnicity

Revision ID: c161a779abd4
Revises: 172f0346209b
Create Date: 2026-10-28 20:55:20.607811

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c161a779abd4'
down_revision: Union[str, Sequence[str], None] = '172f0346209b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('soldiers', sa.Column('national_id_expiry', sa.Date(), nullable=True))
    op.add_column('soldiers', sa.Column('nationality', sa.String(length=50), nullable=True))
    op.execute("UPDATE soldiers SET nationality = 'ខ្មែរ'")
    op.add_column('soldiers', sa.Column('ethnicity', sa.String(length=50), nullable=True))
    op.add_column('soldiers', sa.Column('base_village_id', sa.Integer(), nullable=True))
    op.add_column('soldiers', sa.Column('voting_village_id', sa.Integer(), nullable=True))
    op.add_column('soldiers', sa.Column('voting_place', sa.String(length=255), nullable=True))
    op.add_column('soldiers', sa.Column('housing_status', sa.String(length=10), nullable=True))
    op.add_column('soldiers', sa.Column('dependents_count', sa.SmallInteger(), nullable=False, server_default='0'))
    op.create_index(op.f('ix_soldiers_national_id_expiry'), 'soldiers', ['national_id_expiry'], unique=False)
    op.create_foreign_key('fk_soldiers_voting_village', 'soldiers', 'villages', ['voting_village_id'], ['id'])
    op.create_foreign_key('fk_soldiers_base_village', 'soldiers', 'villages', ['base_village_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_soldiers_voting_village', 'soldiers', type_='foreignkey')
    op.drop_constraint('fk_soldiers_base_village', 'soldiers', type_='foreignkey')
    op.drop_index(op.f('ix_soldiers_national_id_expiry'), table_name='soldiers')
    op.drop_column('soldiers', 'dependents_count')
    op.drop_column('soldiers', 'housing_status')
    op.drop_column('soldiers', 'voting_place')
    op.drop_column('soldiers', 'voting_village_id')
    op.drop_column('soldiers', 'base_village_id')
    op.drop_column('soldiers', 'ethnicity')
    op.drop_column('soldiers', 'nationality')
    op.drop_column('soldiers', 'national_id_expiry')
