"""conscript service type status reserve unit

Revision ID: 172f0346209b
Revises: 3c16a0d0622c
Create Date: 2026-10-28 20:52:20.654922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '172f0346209b'
down_revision: Union[str, Sequence[str], None] = '3c16a0d0622c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('conscript_services', sa.Column('service_type', sa.String(length=10), nullable=False, server_default='duty'))
    op.add_column('conscript_services', sa.Column('status', sa.String(length=10), nullable=False, server_default='serving'))
    op.add_column('conscript_services', sa.Column('reserve_unit_id', sa.BigInteger(), nullable=True))
    op.add_column('conscript_services', sa.Column('reserve_unit_text', sa.String(length=255), nullable=True))
    op.add_column('conscript_services', sa.Column('post_service_status', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_conscript_services_service_type'), 'conscript_services', ['service_type'], unique=False)
    op.create_index(op.f('ix_conscript_services_status'), 'conscript_services', ['status'], unique=False)
    op.create_foreign_key('fk_conscript_services_reserve_unit', 'conscript_services', 'units', ['reserve_unit_id'], ['id'])
    # service periods that already ended are finished
    op.execute("UPDATE conscript_services SET status = 'finished' WHERE end_date < CURDATE()")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_conscript_services_reserve_unit', 'conscript_services', type_='foreignkey')
    op.drop_index(op.f('ix_conscript_services_status'), table_name='conscript_services')
    op.drop_index(op.f('ix_conscript_services_service_type'), table_name='conscript_services')
    op.drop_column('conscript_services', 'post_service_status')
    op.drop_column('conscript_services', 'reserve_unit_text')
    op.drop_column('conscript_services', 'reserve_unit_id')
    op.drop_column('conscript_services', 'status')
    op.drop_column('conscript_services', 'service_type')
