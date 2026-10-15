"""admin role: no approval-step permissions

Revision ID: 523eddda3ddb
Revises: ce0dd06213b2
Create Date: 2026-10-15 16:38:20.294447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '523eddda3ddb'
down_revision: Union[str, Sequence[str], None] = 'ce0dd06213b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """The first workflow seed gave the Admin role every approval step; each step belongs only to the
    role of that level (and Super Admin)."""
    op.execute("DELETE rp FROM role_permissions rp JOIN roles r ON r.id = rp.role_id "
               "JOIN permissions p ON p.id = rp.permission_id WHERE r.name = 'Admin' AND p.module_key LIKE 'wf\\_%'")


def downgrade() -> None:
    """Nothing to restore: giving Admin the approval steps again would be the bug this fixed."""
