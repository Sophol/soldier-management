"""Seed permissions, roles, the first admin user and starter reference data
(ranks, positions, specialties, lookups, document types, settings).

Usage:  python -m scripts.seed [--admin-password ...]
Safe to run more than once: existing rows are left untouched.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.core.permissions import MODULES, SYSTEM_MODULES, module_actions  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    DocumentType,
    Lookup,
    Permission,
    Position,
    Rank,
    RankClass,
    Role,
    Setting,
    Specialty,
    User,
)
from scripts.sql_dump import iter_rows  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# DRAFT rank list – confirm the official names/order with the office (plan.txt §13 Q1).
# (name_kh, name_en, minimum years in rank before the next promotion)
RANKS = {
    ("នាយទាហាន", "Officers"): [
        ("មហាសេនីយ៍", "Senior General", None),
        ("ឧត្តមសេនីយ៍ឯក", "General", None),
        ("ឧត្តមសេនីយ៍ទោ", "Lieutenant General", 4),
        ("ឧត្តមសេនីយ៍ត្រី", "Major General", 4),
        ("វរសេនីយ៍ឯក", "Colonel", 4),
        ("វរសេនីយ៍ទោ", "Lieutenant Colonel", 4),
        ("វរសេនីយ៍ត្រី", "Major", 4),
        ("អនុសេនីយ៍ឯក", "Captain", 3),
        ("អនុសេនីយ៍ទោ", "Lieutenant", 3),
        ("អនុសេនីយ៍ត្រី", "Second Lieutenant", 2),
    ],
    ("នាយទាហានរង", "Non-commissioned officers"): [
        ("ព្រឹន្ទបាលឯក", "Chief Warrant Officer", 2),
        ("ព្រឹន្ទបាលទោ", "Warrant Officer", 2),
        ("ព្រឹន្ទបាលត្រី", "Junior Warrant Officer", 2),
        ("ពលបាលឯក", "Sergeant First Class", 2),
        ("ពលបាលទោ", "Sergeant", 2),
        ("ពលបាលត្រី", "Corporal", 2),
    ],
    ("ពលទាហាន", "Enlisted"): [
        ("ពលទាហានឯក", "Private First Class", 1),
        ("ពលទាហានទោ", "Private", 1),
    ],
}

# DRAFT positions – replace with the office's official list. (name_kh, name_en, grade: 1 = highest)
POSITIONS = [
    ("អគ្គនាយក", "Director General", 1),
    ("អគ្គនាយករង", "Deputy Director General", 2),
    ("មេបញ្ជាការ", "Commander", 2),
    ("មេបញ្ជាការរង", "Deputy Commander", 3),
    ("នាយសេនាធិការ", "Chief of Staff", 3),
    ("ប្រធាននាយកដ្ឋាន", "Director of Department", 3),
    ("អនុប្រធាននាយកដ្ឋាន", "Deputy Director of Department", 4),
    ("ប្រធានការិយាល័យ", "Chief of Office", 5),
    ("អនុប្រធានការិយាល័យ", "Deputy Chief of Office", 6),
    ("មេវរសេនាតូច", "Battalion Commander", 5),
    ("មេវរសេនាតូចរង", "Deputy Battalion Commander", 6),
    ("មេសេនាធំ", "Company Commander", 7),
    ("មេសេនាតូច", "Platoon Leader", 8),
    ("មន្ត្រីជំនាញ", "Specialist Officer", 8),
    ("មន្ត្រីរដ្ឋបាល", "Administrative Officer", 9),
    ("មេក្រុម", "Squad Leader", 9),
    ("ពលទាហាន", "Soldier", 10),
]

# draft specialty -> section (lookup code of "specialty_section")
SPECIALTY_SECTION = {
    "រដ្ឋបាល និងបុគ្គលិក": "admin", "ហិរញ្ញវត្ថុ": "admin", "ច្បាប់": "admin", "ភស្តុភារ": "admin",
    "ព័ត៌មានវិទ្យា": "technical", "ទូរគមនាគមន៍": "technical", "វិស្វកម្ម": "technical",
    "បើកបរ និងជួសជុលយានយន្ត": "technical", "ថ្មើរជើង": "operations", "ការពារ និងអន្តរាគមន៍": "operations",
    "ចារកម្ម និងស៊ើបការណ៍": "operations", "វេជ្ជសាស្ត្រ": "health",
}
# draft sub-positions (មុខតំណែងរង): deputy -> head
POSITION_PARENT = {
    "អគ្គនាយករង": "អគ្គនាយក", "មេបញ្ជាការរង": "មេបញ្ជាការ", "អនុប្រធាននាយកដ្ឋាន": "ប្រធាននាយកដ្ឋាន",
    "អនុប្រធានការិយាល័យ": "ប្រធានការិយាល័យ", "មេវរសេនាតូចរង": "មេវរសេនាតូច",
}

# DRAFT specialties – replace with the office's official list. (name_kh, name_en, military យោធា / civil ស៊ីវិល)
SPECIALTIES = [
    ("រដ្ឋបាល និងបុគ្គលិក", "Administration and personnel", "civil"),
    ("ហិរញ្ញវត្ថុ", "Finance", "civil"),
    ("ច្បាប់", "Law", "civil"),
    ("ព័ត៌មានវិទ្យា", "Information technology", "civil"),
    ("ទូរគមនាគមន៍", "Telecommunications", "military"),
    ("ភស្តុភារ", "Logistics", "military"),
    ("វេជ្ជសាស្ត្រ", "Medicine", "civil"),
    ("វិស្វកម្ម", "Engineering", "civil"),
    ("ថ្មើរជើង", "Infantry", "military"),
    ("ការពារ និងអន្តរាគមន៍", "Protection and intervention", "military"),
    ("បើកបរ និងជួសជុលយានយន្ត", "Driving and vehicle maintenance", "military"),
    ("ចារកម្ម និងស៊ើបការណ៍", "Intelligence", "military"),
]

LOOKUPS = {
    "soldier_status": [
        ("active", "កំពុងបម្រើការងារ", "Active"), ("studying", "កំពុងសិក្សា", "Studying"),
        ("suspended", "ព្យួរការងារ", "Suspended"), ("retired", "និវត្តន៍", "Retired"),
        ("category2", "យោធិនប្រភេទ២", "Category 2"), ("separated", "ចេញពីជួរ", "Separated"),
    ],
    "education_level": [
        (None, "បឋមសិក្សា", "Primary"), (None, "អនុវិទ្យាល័យ", "Lower secondary"),
        (None, "វិទ្យាល័យ", "Upper secondary"), (None, "បរិញ្ញាបត្ររង", "Associate degree"),
        (None, "បរិញ្ញាបត្រ", "Bachelor"), (None, "អនុបណ្ឌិត", "Master"), (None, "បណ្ឌិត", "Doctorate"),
    ],
    "language": [
        (None, "អង់គ្លេស", "English"), (None, "បារាំង", "French"), (None, "ចិន", "Chinese"),
        (None, "វៀតណាម", "Vietnamese"), (None, "ថៃ", "Thai"), (None, "រុស្ស៊ី", "Russian"),
    ],
    "blood_type": [(None, "A", "A"), (None, "B", "B"), (None, "AB", "AB"), (None, "O", "O")],
    "marital_status": [
        ("single", "នៅលីវ", "Single"), ("married", "រៀបការ", "Married"),
        ("divorced", "លែងលះ", "Divorced"), ("widowed", "ពោះម៉ាយ/មេម៉ាយ", "Widowed"),
    ],
    "award_type": [
        ("card", "ប័ណ្ណសរសើរ", "Commendation card"), ("letter", "លិខិតសរសើរ", "Letter of commendation"),
        ("medal", "គ្រឿងឥស្សរិយយស/មេដាយ", "Medal"),
    ],
    "discipline_type": [
        (None, "ស្ដីបន្ទោស", "Reprimand"), (None, "ព្រមាន", "Warning"),
        (None, "ពិន័យដាក់វិន័យ", "Disciplinary detention"),
        (None, "ទម្លាក់ឋានន្តរស័ក្តិ", "Demotion"), (None, "ដកហូតមុខតំណែង", "Removal from position"),
    ],
    "separation_reason": [
        ("resign", "លាឈប់", "Resignation"), ("dismiss", "បណ្ដេញចេញ", "Dismissal"),
        ("death", "ទទួលមរណភាព", "Death"), ("desert", "រត់ចោលជួរ", "Desertion"),
        ("transfer_out", "ផ្ទេរចេញក្រៅក្រសួង", "Transferred out"),
    ],
    # DRAFT sections (ផ្នែក) grouping the specialties – replace with the office's list
    "specialty_section": [
        ("admin", "ផ្នែករដ្ឋបាល និងគ្រប់គ្រង", "Administration and management"),
        ("technical", "ផ្នែកបច្ចេកទេស", "Technical"),
        ("operations", "ផ្នែកប្រតិបត្តិការ", "Operations"),
        ("health", "ផ្នែកសុខាភិបាល", "Health"),
    ],
}

DOCUMENT_TYPES = [
    ("លិខិត", "Letter"), ("ប្រកាស", "Proclamation"), ("សេចក្ដីសម្រេច", "Decision"),
    ("ដីកា", "Order"), ("សារាចរ", "Circular"), ("សេចក្ដីណែនាំ", "Instruction"),
    ("របាយការណ៍", "Report"), ("សំណើ", "Request"), ("លិខិតអញ្ជើញ", "Invitation"),
]

SETTINGS = [
    ("org_name_kh", "ការិយាល័យតែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងឋានន្តរស័ក្តិ", "ឈ្មោះស្ថាប័ន (ខ្មែរ)"),
    ("org_name_en", "Office of Appointment, Transfer and Promotion", "Organisation name (English)"),
    ("outgoing_number_format", "{seq}/{yy}", "Outgoing number format: {seq} {yyyy} {yy}"),
    ("retirement_age_male", "60", "Retirement age – male (confirm with office)"),
    ("retirement_age_female", "55", "Retirement age – female (confirm with office)"),
    ("alert_months_ahead", "6", "Months ahead for retirement alerts"),
    ("workflow_overdue_days", "3", "Days a decision may wait at one approval step before it is flagged"),
]


# the roles of the decision workflow (New.txt §12): (role, Khmer label, workflow permission)
# ជំនួយការ enters and submits; each other role approves its own step
WORKFLOW_ROLES = [
    ("Assistant", "ជំនួយការ", None),
    ("Deputy Chief of Office", "នាយរងការិយាល័យ", "wf_deputy_office"),
    ("Chief of Office", "នាយការិយាល័យ", "wf_chief_office"),
    ("Deputy Director", "នាយករង", "wf_deputy_director"),
    ("Director", "នាយក", "wf_director"),
]


def _keys(modules, actions) -> set[tuple[str, str]]:
    return {(m, a) for m in modules for a in actions if a in module_actions(m)}


def role_permission_keys(role: str) -> set[tuple[str, str]]:
    # health data of conscripts is only for roles given it explicitly (answer.txt)
    business = [m for m in MODULES if m not in SYSTEM_MODULES and not m.startswith("wf_") and m != "conscript_medical"]
    decisions = ["decisions_appoint", "decisions_transfer", "decisions_promote"]
    if role == "Admin":
        # approval steps belong only to the role of that level (and Super Admin): not to the system admin
        return {(m, a) for m in MODULES if m not in {"roles", "settings"} and not m.startswith("wf_")
                for a in module_actions(m)}
    if role in ("Officer", "Assistant"):  # enter data and requests, submit them to the workflow
        return _keys(business, ["view", "create", "update", "search", "print", "export"])
    if role == "Approver":  # may also revert an approved decision
        return _keys(business, ["view", "search", "print", "export"]) | {(m, "approve") for m in decisions}
    if role == "Viewer":
        return _keys(business, ["view", "search", "print"])
    for name, _, wf in WORKFLOW_ROLES:
        if role == name and wf:
            return role_permission_keys("Viewer") | {(wf, "approve")}
    return set()


def main(admin_password: str, source_dir: Path = PROJECT_ROOT) -> None:
    db = SessionLocal()
    try:
        existing = {(p.module_key, p.action) for p in db.scalars(select(Permission))}
        added = {(m, a) for m in MODULES for a in module_actions(m)} - existing
        for m, a in sorted(added):
            db.add(Permission(module_key=m, action=a))
        db.flush()
        perms = {(p.module_key, p.action): p for p in db.scalars(select(Permission))}

        roles_def = [
            ("Super Admin", "គ្រប់គ្រងប្រព័ន្ធទាំងស្រុង", True),
            ("Admin", "អ្នកគ្រប់គ្រង", False),
            ("Officer", "មន្ត្រីបញ្ចូលទិន្នន័យ", False),
            ("Approver", "អ្នកអនុម័តសេចក្ដីសម្រេច", False),
            ("Viewer", "អ្នកមើលប៉ុណ្ណោះ", False),
            *((name, desc, False) for name, desc, _ in WORKFLOW_ROLES),
        ]
        for name, desc, is_super in roles_def:
            role = db.scalar(select(Role).where(Role.name == name))
            if not role:
                role = Role(name=name, description=desc, is_super=is_super)
                role.permissions = [perms[k] for k in sorted(role_permission_keys(name))]
                db.add(role)
            elif added:
                # permissions that did not exist before this run (new modules): give them to the roles that
                # would have them on a fresh install; permissions an admin removed earlier stay removed
                have = {p.key for p in role.permissions}
                role.permissions += [perms[k] for k in sorted(role_permission_keys(name) & added)
                                     if f"{k[0]}.{k[1]}" not in have]
        db.flush()

        if not db.scalar(select(User).where(User.username == "admin")):
            super_role = db.scalar(select(Role).where(Role.name == "Super Admin"))
            db.add(User(username="admin", password_hash=hash_password(admin_password),
                        full_name="Administrator", role_id=super_role.id))
            print(f"Created user admin / {admin_password}  (change it after first login)")

        if not db.scalar(select(RankClass.id).limit(1)):
            order = 100
            for ci, ((cls_kh, cls_en), names) in enumerate(RANKS.items(), start=1):
                rc = RankClass(name_kh=cls_kh, name_en=cls_en, sort_order=ci)
                db.add(rc)
                db.flush()
                for kh, en, years in names:
                    db.add(Rank(rank_class_id=rc.id, name_kh=kh, name_en=en, min_years_to_next=years, sort_order=order))
                    order -= 1
        else:
            # fill English names / minimum years on ranks seeded before these were added (never overwrite edits)
            draft = {kh: (en, years) for names in RANKS.values() for kh, en, years in names}
            for r in db.scalars(select(Rank)):
                en, years = draft.get(r.name_kh, (None, None))
                r.name_en = r.name_en or en
                if r.min_years_to_next is None:
                    r.min_years_to_next = years

        if not db.scalar(select(Position.id).limit(1)):
            for i, (kh, en, grade) in enumerate(POSITIONS, start=1):
                db.add(Position(name_kh=kh, name_en=en, grade=grade, sort_order=i))

        if not db.scalar(select(Specialty.id).limit(1)):
            for kh, en, category in SPECIALTIES:
                db.add(Specialty(name_kh=kh, name_en=en, category=category))
        else:
            # the category column was added later (default 'military'): mark the draft civil specialties once
            civil = {kh for kh, _, category in SPECIALTIES if category == "civil"}
            for sp in db.scalars(select(Specialty).where(Specialty.name_kh.in_(civil), Specialty.category == "military",
                                                         Specialty.updated_at == Specialty.created_at)):
                sp.category = "civil"

        for cat, items in LOOKUPS.items():
            if db.scalar(select(Lookup.id).where(Lookup.category == cat).limit(1)):
                continue
            for i, (code, kh, en) in enumerate(items, start=1):
                db.add(Lookup(category=cat, code=code, name_kh=kh, name_en=en, sort_order=i))

        if not db.scalar(select(Lookup.id).where(Lookup.category == "occupation").limit(1)):
            member_db = source_dir / "member_db.sql"
            jobs = [r["job_name"] for r in iter_rows(member_db, "jobs")] if member_db.exists() else []
            jobs = [j.replace("ទាហ៊ាន", "ទាហាន") for j in jobs] or ["កសិករ", "មន្ដ្រីរាជការ", "ផ្សេងៗ"]
            for i, j in enumerate(jobs, start=1):
                db.add(Lookup(category="occupation", name_kh=j, sort_order=i))

        if not db.scalar(select(DocumentType.id).limit(1)):
            for kh, en in DOCUMENT_TYPES:
                db.add(DocumentType(name_kh=kh, name_en=en))

        db.flush()
        # sections and sub-positions were added later: fill them only where still empty
        sections = {lk.code: lk.id for lk in db.scalars(select(Lookup).where(Lookup.category == "specialty_section"))}
        for sp in db.scalars(select(Specialty).where(Specialty.section_id.is_(None))):
            sp.section_id = sections.get(SPECIALTY_SECTION.get(sp.name_kh))
        positions = {p.name_kh: p for p in db.scalars(select(Position))}
        for child, parent in POSITION_PARENT.items():
            if child in positions and parent in positions and positions[child].parent_id is None \
                    and not any(p.parent_id == positions[child].id for p in positions.values()):
                positions[child].parent_id, positions[child].level = positions[parent].id, positions[parent].level + 1

        for key, value, desc in SETTINGS:
            if not db.get(Setting, key):
                db.add(Setting(key=key, value=value, description=desc))

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-password", default="Admin@123")
    ap.add_argument("--source-dir", type=Path, default=PROJECT_ROOT, help="folder containing member_db.sql (jobs list)")
    args = ap.parse_args()
    main(args.admin_password, args.source_dir)
