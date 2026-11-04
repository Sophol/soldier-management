"""military ID cards: reason the card was issued / replaced (មូលហេតុធ្វើ ឬប្ដូរអត្តសញ្ញាណប័ណ្ណយោធិន)

Revision ID: a7c3e9d51f20
Revises: f2a9d4b6c813
Create Date: 2026-11-04 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c3e9d51f20'
down_revision: Union[str, Sequence[str], None] = 'f2a9d4b6c813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('military_cards', sa.Column('reason', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('military_cards', 'reason')
