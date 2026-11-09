"""the "rank_position_update" permission (Update ស័ក្តិ និងមុខតំណែង)

Given to the roles that may already edit soldiers (soldiers.update): they used the page with that permission.

Revision ID: c7e1a4d92b38
Revises: b5d8e2f4a691
Create Date: 2026-11-09 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7e1a4d92b38'
down_revision: str | Sequence[str] | None = 'b5d8e2f4a691'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT id FROM permissions WHERE module_key = 'rank_position_update' "
                            "AND action = 'update'")).first():
        return  # already made (by the seed)
    conn.execute(sa.text("INSERT INTO permissions (module_key, action) VALUES ('rank_position_update', 'update')"))
    conn.execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT rp.role_id, (SELECT id FROM permissions WHERE module_key = 'rank_position_update' AND action = 'update') "
        "FROM role_permissions rp JOIN permissions p ON p.id = rp.permission_id "
        "WHERE p.module_key = 'soldiers' AND p.action = 'update'"))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN "
                         "(SELECT id FROM (SELECT id FROM permissions WHERE module_key = 'rank_position_update') x)"))
    conn.execute(sa.text("DELETE FROM permissions WHERE module_key = 'rank_position_update'"))
