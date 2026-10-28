"""record statuses and military id cards

Revision ID: 3c16a0d0622c
Revises: 4041315f7333
Create Date: 2026-10-28 20:45:55.959835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c16a0d0622c'
down_revision: Union[str, Sequence[str], None] = '4041315f7333'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('military_cards',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('soldier_id', sa.BigInteger(), nullable=False),
    sa.Column('card_no', sa.String(length=100), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('issue_date', sa.Date(), nullable=True),
    sa.Column('expiry_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.Column('updated_by', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['soldier_id'], ['soldiers.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_military_cards_card_no'), 'military_cards', ['card_no'], unique=False)
    op.create_index(op.f('ix_military_cards_deleted_at'), 'military_cards', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_military_cards_expiry_date'), 'military_cards', ['expiry_date'], unique=False)
    op.create_index(op.f('ix_military_cards_soldier_id'), 'military_cards', ['soldier_id'], unique=False)
    op.add_column('award_records', sa.Column('level', sa.String(length=100), nullable=True))
    op.add_column('award_records', sa.Column('awarded_by', sa.String(length=255), nullable=True))
    op.add_column('discipline_records', sa.Column('level', sa.String(length=100), nullable=True))
    op.add_column('discipline_records', sa.Column('decided_by', sa.String(length=255), nullable=True))
    op.add_column('discipline_records', sa.Column('cancelled', sa.Boolean(), nullable=False, server_default=sa.false()))
    # existing retirement records were entered once the case was settled
    op.add_column('retirement_records', sa.Column('case_status', sa.String(length=20), nullable=False, server_default='done'))
    op.add_column('training_participants', sa.Column('status', sa.String(length=20), nullable=False, server_default='studying'))
    op.execute("UPDATE training_participants p JOIN training_courses c ON c.id = p.course_id "
               "SET p.status = 'completed' WHERE c.end_date < CURDATE()")
    # service status ស្លាប់ (retirement type "death"); the seed only fills empty lookup lists
    op.execute("INSERT INTO lookups (category, code, name_kh, name_en, sort_order, active) "
               "SELECT 'soldier_status', 'deceased', 'ស្លាប់', 'Deceased', 6, 1 FROM DUAL WHERE NOT EXISTS "
               "(SELECT 1 FROM lookups WHERE category = 'soldier_status' AND code = 'deceased')")


def downgrade() -> None:
    """Downgrade schema (the ស្លាប់ status lookup is kept: soldiers may use it)."""
    op.drop_column('training_participants', 'status')
    op.drop_column('retirement_records', 'case_status')
    op.drop_column('discipline_records', 'cancelled')
    op.drop_column('discipline_records', 'decided_by')
    op.drop_column('discipline_records', 'level')
    op.drop_column('award_records', 'awarded_by')
    op.drop_column('award_records', 'level')
    op.drop_index(op.f('ix_military_cards_soldier_id'), table_name='military_cards')
    op.drop_index(op.f('ix_military_cards_expiry_date'), table_name='military_cards')
    op.drop_index(op.f('ix_military_cards_deleted_at'), table_name='military_cards')
    op.drop_index(op.f('ix_military_cards_card_no'), table_name='military_cards')
    op.drop_table('military_cards')
