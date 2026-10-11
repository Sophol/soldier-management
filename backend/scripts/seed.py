"""Seed permissions, roles, the first admin user and starter lookup data.

Usage:  python -m scripts.seed [--admin-password ...]
Safe to run more than once: existing rows are left untouched.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.core.permissions import ACTIONS, MODULES, SYSTEM_MODULES  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import DocumentType, Lookup, Permission, Rank, RankClass, Role, Setting, User  # noqa: E402
from scripts.sql_dump import iter_rows  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# DRAFT rank list – confirm the official names/order with the office (plan.txt §13 Q1).
RANKS = {
    ("នាយទាហាន", "Officers"): [
        "មហាសេនីយ៍", "ឧត្តមសេនីយ៍ឯក", "ឧត្តមសេនីយ៍ទោ", "ឧត្តមសេនីយ៍ត្រី",
        "វរសេនីយ៍ឯក", "វរសេនីយ៍ទោ", "វរសេនីយ៍ត្រី",
        "អនុសេនីយ៍ឯក", "អនុសេនីយ៍ទោ", "អនុសេនីយ៍ត្រី",
    ],
    ("នាយទាហានរង", "Non-commissioned officers"): [
        "ព្រឹន្ទបាលឯក", "ព្រឹន្ទបាលទោ", "ព្រឹន្ទបាលត្រី",
        "ពលបាលឯក", "ពលបាលទោ", "ពលបាលត្រី",
    ],
    ("ពលទាហាន", "Enlisted"): ["ពលទាហានឯក", "ពលទាហានទោ"],
}

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
]


def role_permission_keys(role: str) -> set[tuple[str, str]]:
    business = [m for m in MODULES if m not in SYSTEM_MODULES]
    if role == "Admin":
        return {(m, a) for m in MODULES if m not in {"roles", "settings"} for a in ACTIONS}
    if role == "Officer":
        return {(m, a) for m in business for a in ["view", "create", "update", "search", "print", "export"]}
    if role == "Approver":
        keys = {(m, a) for m in business for a in ["view", "search", "print", "export"]}
        return keys | {(m, "approve") for m in ["decisions_appoint", "decisions_transfer", "decisions_promote"]}
    if role == "Viewer":
        return {(m, a) for m in business for a in ["view", "search", "print"]}
    return set()


def main(admin_password: str, source_dir: Path = PROJECT_ROOT) -> None:
    db = SessionLocal()
    try:
        existing = {(p.module_key, p.action) for p in db.scalars(select(Permission))}
        for m in MODULES:
            for a in ACTIONS:
                if (m, a) not in existing:
                    db.add(Permission(module_key=m, action=a))
        db.flush()
        perms = {(p.module_key, p.action): p for p in db.scalars(select(Permission))}

        roles_def = [
            ("Super Admin", "គ្រប់គ្រងប្រព័ន្ធទាំងស្រុង", True),
            ("Admin", "អ្នកគ្រប់គ្រង", False),
            ("Officer", "មន្ត្រីបញ្ចូលទិន្នន័យ", False),
            ("Approver", "អ្នកអនុម័តសេចក្ដីសម្រេច", False),
            ("Viewer", "អ្នកមើលប៉ុណ្ណោះ", False),
        ]
        for name, desc, is_super in roles_def:
            if not db.scalar(select(Role).where(Role.name == name)):
                role = Role(name=name, description=desc, is_super=is_super)
                role.permissions = [perms[k] for k in sorted(role_permission_keys(name))]
                db.add(role)
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
                for n in names:
                    db.add(Rank(rank_class_id=rc.id, name_kh=n, sort_order=order))
                    order -= 1

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
