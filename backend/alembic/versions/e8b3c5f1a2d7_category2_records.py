"""category-2 soldiers (យោធិនប្រភេទ២: ពលី, ពលី-មរណ, ពិការ) get their own records and permission

Revision ID: e8b3c5f1a2d7
Revises: d4e7a1c90b52
Create Date: 2026-11-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b3c5f1a2d7'
down_revision: Union[str, Sequence[str], None] = 'd4e7a1c90b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MOVED_COLUMNS = ("soldier_id", "decision_no", "decision_date", "effective_date", "notes", "previous_status_id",
                 "previous_unit_id", "created_by", "updated_by", "created_at", "updated_at")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('category2_records',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('soldier_id', sa.BigInteger(), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=True),
    sa.Column('decision_no', sa.String(length=100), nullable=True),
    sa.Column('decision_date', sa.Date(), nullable=True),
    sa.Column('effective_date', sa.Date(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('previous_status_id', sa.Integer(), nullable=True),
    sa.Column('previous_unit_id', sa.BigInteger(), nullable=True),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.Column('updated_by', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['previous_status_id'], ['lookups.id'], ),
    sa.ForeignKeyConstraint(['previous_unit_id'], ['units.id'], ),
    sa.ForeignKeyConstraint(['soldier_id'], ['soldiers.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_category2_records_deleted_at'), 'category2_records', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_category2_records_soldier_id'), 'category2_records', ['soldier_id'], unique=False)

    # retirement records of type "category2" move to the new table (type unknown: set it on the new page),
    # with their attachments and strength movements
    conn = op.get_bind()
    cols = ", ".join(MOVED_COLUMNS)
    for (old_id,) in conn.execute(sa.text(
            "SELECT id FROM retirement_records WHERE type = 'category2' AND deleted_at IS NULL")).all():
        conn.execute(sa.text(f"INSERT INTO category2_records ({cols}) SELECT {cols} FROM retirement_records "
                             "WHERE id = :id"), {"id": old_id})
        new_id = conn.execute(sa.text("SELECT MAX(id) FROM category2_records")).scalar()
        conn.execute(sa.text("UPDATE document_files SET owner_type = 'category2', owner_id = :new "
                             "WHERE owner_type = 'retirement' AND owner_id = :old"), {"new": new_id, "old": old_id})
        conn.execute(sa.text("UPDATE strength_movements SET source_table = 'category2_records', source_id = :new "
                             "WHERE source_table = 'retirement_records' AND source_id = :old"),
                     {"new": new_id, "old": old_id})
        conn.execute(sa.text("DELETE FROM retirement_records WHERE id = :id"), {"id": old_id})

    # the "category2" permission module: given to the roles that hold the same retirement permission
    for (action,) in conn.execute(sa.text("SELECT action FROM permissions WHERE module_key = 'retirement'")).all():
        conn.execute(sa.text("INSERT INTO permissions (module_key, action) VALUES ('category2', :a)"), {"a": action})
        conn.execute(sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT rp.role_id, (SELECT id FROM permissions WHERE module_key = 'category2' AND action = :a) "
            "FROM role_permissions rp JOIN permissions p ON p.id = rp.permission_id "
            "WHERE p.module_key = 'retirement' AND p.action = :a"), {"a": action})


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN "
                         "(SELECT id FROM (SELECT id FROM permissions WHERE module_key = 'category2') p)"))
    conn.execute(sa.text("DELETE FROM permissions WHERE module_key = 'category2'"))
    cols = ", ".join(MOVED_COLUMNS)
    for (old_id,) in conn.execute(sa.text("SELECT id FROM category2_records WHERE deleted_at IS NULL")).all():
        conn.execute(sa.text(f"INSERT INTO retirement_records (type, case_status, {cols}) "
                             f"SELECT 'category2', 'done', {cols} FROM category2_records WHERE id = :id"), {"id": old_id})
        new_id = conn.execute(sa.text("SELECT MAX(id) FROM retirement_records")).scalar()
        conn.execute(sa.text("UPDATE document_files SET owner_type = 'retirement', owner_id = :new "
                             "WHERE owner_type = 'category2' AND owner_id = :old"), {"new": new_id, "old": old_id})
        conn.execute(sa.text("UPDATE strength_movements SET source_table = 'retirement_records', source_id = :new "
                             "WHERE source_table = 'category2_records' AND source_id = :old"),
                     {"new": new_id, "old": old_id})
    op.drop_index(op.f('ix_category2_records_soldier_id'), table_name='category2_records')
    op.drop_index(op.f('ix_category2_records_deleted_at'), table_name='category2_records')
    op.drop_table('category2_records')
