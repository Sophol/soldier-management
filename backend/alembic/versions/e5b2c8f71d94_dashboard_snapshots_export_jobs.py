"""dashboard figures counted in the background; Excel files made in the background; activity-log retention

Revision ID: e5b2c8f71d94
Revises: d3a9f6b1c724
Create Date: 2026-11-09 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5b2c8f71d94'
down_revision: str | Sequence[str] | None = 'd3a9f6b1c724'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SETTINGS = [  # as in scripts/seed.py
    ("dashboard_refresh_minutes", "5", "Minutes the dashboard figures are kept before they are counted again"),
    ("audit_retention_years", "3", "Years the activity log is kept (0 = keep everything)"),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'dashboard_snapshots',
        sa.Column('scope_key', sa.String(length=64), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('scope_key'),
    )
    op.create_table(
        'export_jobs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('filename', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('file_path', sa.String(length=255), nullable=True),
        sa.Column('size', sa.BigInteger(), nullable=True),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_export_jobs_user_id', 'export_jobs', ['user_id'])
    op.create_index('ix_export_jobs_created_at', 'export_jobs', ['created_at'])
    conn = op.get_bind()
    for key, value, desc in SETTINGS:
        if not conn.execute(sa.text("SELECT 1 FROM settings WHERE `key` = :k"), {"k": key}).first():
            conn.execute(sa.text("INSERT INTO settings (`key`, value, description) VALUES (:k, :v, :d)"),
                         {"k": key, "v": value, "d": desc})


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('export_jobs')
    op.drop_table('dashboard_snapshots')
    op.execute("DELETE FROM settings WHERE `key` IN ('dashboard_refresh_minutes', 'audit_retention_years')")
