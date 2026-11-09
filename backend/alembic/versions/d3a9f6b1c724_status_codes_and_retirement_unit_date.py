"""soldier statuses get their codes; retirement records keep the unit date they replace

- soldier_status: the seed skipped the whole category once a migration had added "deceased", so the codes the
  system reads (active, retired, category2, separated...) were missing: a status named like one of them takes its
  code, the others are added. Soldiers without a status get the one their records give (else "active").
- retirement_records.previous_unit_date: "ផ្លាស់អង្គភាព ពេលចូលនិវត្តន៍" moves the soldier; deleting the record now
  puts the soldier back in the unit they left, with its date.
- soldiers.date_of_birth is indexed: a new soldier is compared with those of the same name and birth date.
- the strength movements of soldier 234 written twice while that move was not undone (2026-11-01) are corrected.

Revision ID: d3a9f6b1c724
Revises: c7e1a4d92b38
Create Date: 2026-11-09 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3a9f6b1c724'
down_revision: str | Sequence[str] | None = 'c7e1a4d92b38'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = [  # as in scripts/seed.py, with the names a user may have given the same status
    ("active", "កំពុងបម្រើការងារ", "Active", ("កំពុងបម្រើការងារ", "សកម្ម", "កំពុងបម្រើការ")),
    ("studying", "កំពុងសិក្សា", "Studying", ("កំពុងសិក្សា",)),
    ("suspended", "ព្យួរការងារ", "Suspended", ("ព្យួរការងារ",)),
    ("retired", "និវត្តន៍", "Retired", ("និវត្តន៍", "ចូលនិវត្តន៍", "សោធននិវត្តន៍", "សោធិនិវត្តន៍")),
    ("category2", "យោធិនប្រភេទ២", "Category 2", ("យោធិនប្រភេទ២", "យោធិនប្រភេទ ២")),
    ("separated", "ចេញពីជួរ", "Separated", ("ចេញពីជួរ",)),
    ("deceased", "ស្លាប់", "Deceased", ("ស្លាប់",)),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('retirement_records', sa.Column('previous_unit_date', sa.Date(), nullable=True))
    op.create_index('ix_soldiers_date_of_birth', 'soldiers', ['date_of_birth'])
    conn = op.get_bind()

    # 1. the soldier_status codes
    for code, kh, en, names in STATUSES:
        if conn.execute(sa.text("SELECT 1 FROM lookups WHERE category = 'soldier_status' AND code = :c"), {"c": code}).first():
            continue
        same = conn.execute(sa.text("SELECT id FROM lookups WHERE category = 'soldier_status' AND code IS NULL "
                                    "AND name_kh IN :names ORDER BY id LIMIT 1").bindparams(sa.bindparam("names", expanding=True)),
                            {"names": list(names)}).scalar()
        if same:
            conn.execute(sa.text("UPDATE lookups SET code = :c, name_en = COALESCE(name_en, :en) WHERE id = :id"),
                         {"c": code, "en": en, "id": same})
        else:
            order = conn.execute(sa.text("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM lookups "
                                         "WHERE category = 'soldier_status'")).scalar()
            conn.execute(sa.text("INSERT INTO lookups (category, code, name_kh, name_en, sort_order, active) "
                                 "VALUES ('soldier_status', :c, :kh, :en, :o, 1)"), {"c": code, "kh": kh, "en": en, "o": order})

    # 2. soldiers without a status: the one their records give, as saving those records would have set it
    def status(code: str) -> int:
        return conn.execute(sa.text("SELECT id FROM lookups WHERE category = 'soldier_status' AND code = :c"),
                            {"c": code}).scalar()

    live = "SELECT soldier_id FROM {} WHERE deleted_at IS NULL"
    for code, where in (
            ("separated", f"id IN ({live.format('separation_records')})"),
            ("category2", f"id IN ({live.format('category2_records')})"),
            ("deceased", "id IN (SELECT soldier_id FROM retirement_records WHERE deleted_at IS NULL AND type = 'death')"),
            ("retired", f"id IN ({live.format('retirement_records')})"),
            ("active", "1 = 1")):
        conn.execute(sa.text(f"UPDATE soldiers SET status_id = :s WHERE status_id IS NULL AND {where}"), {"s": status(code)})

    # 3. soldier 234 (2026-11-01): retired with a move to another unit, the record deleted without undoing the move,
    # then moved back by hand — twice. Each time a movement out of the unit he had not entered was written: he left
    # unit 2 once (movement 253), and the second pair (256, 257) repeats the first.
    rows = conn.execute(sa.text(
        "SELECT id, unit_id, direction FROM strength_movements WHERE soldier_id = 234 AND id IN (253, 254, 256, 257) "
        "AND movement_date = '2026-11-01' AND source_table = 'soldiers' ORDER BY id")).all()
    if [tuple(r) for r in rows] == [(253, 144, "out"), (254, 3, "in"), (256, 144, "out"), (257, 3, "in")] and \
            conn.execute(sa.text("SELECT current_unit_id FROM soldiers WHERE id = 234")).scalar() == 1:
        conn.execute(sa.text("UPDATE strength_movements SET unit_id = 2 WHERE id = 253"))
        conn.execute(sa.text("DELETE FROM strength_movements WHERE id IN (256, 257)"))


def downgrade() -> None:
    """Downgrade schema."""
    # the statuses and the corrected movements stay: they are what the data should have been
    op.drop_index('ix_soldiers_date_of_birth', table_name='soldiers')
    op.drop_column('retirement_records', 'previous_unit_date')
