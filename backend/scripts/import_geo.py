"""Import Cambodian geography (provinces > districts > communes > villages) and countries.

Usage:  python -m scripts.import_geo [--source-dir ..]

Sources (in the project root by default):
  provinces.sql, districts.sql, communes.sql, "villages (1).sql"  -> inva_db 2021 dumps (master data)
  member_db.sql                                                    -> only the `countries` table is used
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import insert, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models import Commune, Country, District, Province, Village  # noqa: E402
from scripts.sql_dump import iter_rows  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PHNOM_PENH_ID = 12


def _clean(v):
    return v.strip() if isinstance(v, str) else v


def main(source_dir: Path) -> None:
    files = {
        "provinces": source_dir / "provinces.sql",
        "districts": source_dir / "districts.sql",
        "communes": source_dir / "communes.sql",
        "villages": source_dir / "villages (1).sql",
    }
    for f in files.values():
        if not f.exists():
            sys.exit(f"Missing source file: {f}")

    db = SessionLocal()
    try:
        if db.scalar(select(Province.id).limit(1)):
            print("Geography already imported – skipping (truncate the 4 tables to re-import).")
        else:
            provinces = [
                {
                    "id": r["id"], "name_kh": _clean(r["name"]), "name_en": _clean(r["name_en"]),
                    "type": "រាជធានី" if r["id"] == PHNOM_PENH_ID else "ខេត្ត", "active": bool(r["active"]),
                }
                for r in iter_rows(files["provinces"], "provinces")
            ]
            db.execute(insert(Province), provinces)
            pids = {p["id"] for p in provinces}

            districts = [
                {
                    "id": r["id"], "province_id": r["province_id"], "name_kh": _clean(r["name"]),
                    "name_en": _clean(r["name_en"]),
                    "type": "ខណ្ឌ" if r["province_id"] == PHNOM_PENH_ID else "ស្រុក", "active": bool(r["active"]),
                }
                for r in iter_rows(files["districts"], "districts")
                if r["province_id"] in pids
            ]
            db.execute(insert(District), districts)
            dids = {d["id"]: d["province_id"] for d in districts}

            communes = [
                {
                    "id": r["id"], "district_id": r["district_id"], "name_kh": _clean(r["name"]),
                    "name_en": _clean(r["name_en"]),
                    "type": "សង្កាត់" if dids.get(r["district_id"]) == PHNOM_PENH_ID else "ឃុំ",
                    "active": bool(r["active"]),
                }
                for r in iter_rows(files["communes"], "communes")
                if r["district_id"] in dids
            ]
            db.execute(insert(Commune), communes)
            cids = {c["id"] for c in communes}

            villages, skipped = [], 0
            for r in iter_rows(files["villages"], "villages"):
                if r["commune_id"] not in cids:
                    skipped += 1
                    continue
                villages.append({
                    "id": r["id"], "commune_id": r["commune_id"], "name_kh": _clean(r["name"]),
                    "name_en": _clean(r["name_en"]), "active": bool(r["active"]),
                })
            for i in range(0, len(villages), 2000):
                db.execute(insert(Village), villages[i:i + 2000])
            db.commit()
            print(f"provinces={len(provinces)} districts={len(districts)} communes={len(communes)} "
                  f"villages={len(villages)} (skipped orphans: {skipped})")

        member_db = source_dir / "member_db.sql"
        if not db.scalar(select(Country.id).limit(1)) and member_db.exists():
            countries = [
                {"id": r["id"], "name_kh": _clean(r["name"]), "name_en": _clean(r["name_en"] or r["name"]), "active": bool(r["active"])}
                for r in iter_rows(member_db, "countries")
            ]
            db.execute(insert(Country), countries)
            db.commit()
            print(f"countries={len(countries)}")
        db.execute(text("SELECT 1"))
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", type=Path, default=PROJECT_ROOT)
    main(ap.parse_args().source_dir)
