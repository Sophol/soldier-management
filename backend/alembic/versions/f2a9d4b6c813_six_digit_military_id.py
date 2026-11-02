"""military IDs (អត្តលេខ) shown with 6 digits: numeric IDs padded with leading zeros (652 -> 000652)

Revision ID: f2a9d4b6c813
Revises: e8b3c5f1a2d7
Create Date: 2026-11-01 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f2a9d4b6c813'
down_revision: Union[str, Sequence[str], None] = 'e8b3c5f1a2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _numeric(col: str) -> str:
    return f"{col} REGEXP '^[0-9]+$'" if op.get_bind().dialect.name == 'mysql' else f"{col} ~ '^[0-9]+$'"


def upgrade() -> None:
    """Upgrade schema."""
    # skipped where the padded ID is already taken (it would break the unique index)
    op.execute(f"UPDATE soldiers SET military_id = LPAD(military_id, 6, '0') "
               f"WHERE {_numeric('military_id')} AND LENGTH(military_id) < 6 "
               f"AND LPAD(military_id, 6, '0') NOT IN (SELECT m FROM (SELECT military_id AS m FROM soldiers) t)")


def downgrade() -> None:
    """Downgrade schema."""
    # leading zeros cannot be told apart from IDs entered with them: they stay
    pass
