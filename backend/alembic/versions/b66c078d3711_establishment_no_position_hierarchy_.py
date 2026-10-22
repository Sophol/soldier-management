"""establishment no, position hierarchy, specialty section, incoming from unit, conscript fields

Revision ID: b66c078d3711
Revises: 2578c17456e5
Create Date: 2026-10-22 09:36:56.315760

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b66c078d3711'
down_revision: Union[str, Sequence[str], None] = '2578c17456e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('conscripts', sa.Column('specialty_id', sa.Integer(), nullable=True))
    op.add_column('conscripts', sa.Column('blood_type_id', sa.Integer(), nullable=True))
    op.add_column('conscripts', sa.Column('spouse_job_id', sa.Integer(), nullable=True))
    op.add_column('documents_incoming', sa.Column('from_unit_id', sa.BigInteger(), nullable=True))
    op.create_index(op.f('ix_documents_incoming_from_unit_id'), 'documents_incoming', ['from_unit_id'], unique=False)
    op.add_column('positions', sa.Column('parent_id', sa.Integer(), nullable=True))
    op.add_column('positions', sa.Column('level', sa.SmallInteger(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_positions_parent_id'), 'positions', ['parent_id'], unique=False)
    op.add_column('soldiers', sa.Column('establishment_no', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_soldiers_establishment_no'), 'soldiers', ['establishment_no'], unique=False)
    op.add_column('specialties', sa.Column('section_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_specialties_section_id'), 'specialties', ['section_id'], unique=False)
    op.create_foreign_key('fk_conscripts_spouse_job', 'conscripts', 'lookups', ['spouse_job_id'], ['id'])
    op.create_foreign_key('fk_conscripts_blood_type', 'conscripts', 'lookups', ['blood_type_id'], ['id'])
    op.create_foreign_key('fk_conscripts_specialty', 'conscripts', 'specialties', ['specialty_id'], ['id'])
    op.create_foreign_key('fk_documents_incoming_from_unit', 'documents_incoming', 'units', ['from_unit_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_positions_parent', 'positions', 'positions', ['parent_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('fk_specialties_section', 'specialties', 'lookups', ['section_id'], ['id'])
    # incoming documents whose sender text is exactly one unit's name now point to that unit
    op.execute("UPDATE documents_incoming d JOIN (SELECT name_kh, MIN(id) AS id FROM units GROUP BY name_kh "
               "HAVING COUNT(*) = 1) u ON u.name_kh = d.from_unit SET d.from_unit_id = u.id")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_conscripts_spouse_job', 'conscripts', type_='foreignkey')
    op.drop_constraint('fk_conscripts_blood_type', 'conscripts', type_='foreignkey')
    op.drop_constraint('fk_conscripts_specialty', 'conscripts', type_='foreignkey')
    op.drop_constraint('fk_documents_incoming_from_unit', 'documents_incoming', type_='foreignkey')
    op.drop_constraint('fk_positions_parent', 'positions', type_='foreignkey')
    op.drop_constraint('fk_specialties_section', 'specialties', type_='foreignkey')
    op.drop_index(op.f('ix_specialties_section_id'), table_name='specialties')
    op.drop_column('specialties', 'section_id')
    op.drop_index(op.f('ix_soldiers_establishment_no'), table_name='soldiers')
    op.drop_column('soldiers', 'establishment_no')
    op.drop_index(op.f('ix_positions_parent_id'), table_name='positions')
    op.drop_column('positions', 'level')
    op.drop_column('positions', 'parent_id')
    op.drop_index(op.f('ix_documents_incoming_from_unit_id'), table_name='documents_incoming')
    op.drop_column('documents_incoming', 'from_unit_id')
    op.drop_column('conscripts', 'spouse_job_id')
    op.drop_column('conscripts', 'blood_type_id')
    op.drop_column('conscripts', 'specialty_id')
