"""Dashboard statistics, alerts and reports (JSON for screen/print, XLSX for export)."""

from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from sqlalchemy import extract, func, literal_column, select
from sqlalchemy.orm import Session

from app.api.v1.conscripts import registration_counts
from app.api.v1.decisions import IN_PROGRESS, overdue_cutoff
from app.api.v1.records import MOVEMENT_REASONS
from app.api.v1.system import get_setting
from app.core.database import get_db
from app.core.deps import require
from app.models import (
    AwardRecord,
    Country,
    Decision,
    DisciplineRecord,
    DocumentIncoming,
    DocumentOutgoing,
    Position,
    Province,
    Rank,
    RankClass,
    RetirementRecord,
    SeparationRecord,
    Soldier,
    StrengthMovement,
    TrainingCourse,
    TrainingParticipant,
    Unit,
    User,
)
from app.models.conscript import REGISTRATION_STATUSES
from app.models.decision import DECISION_KINDS
from app.services.common import scope_unit_ids, unit_subtree_ids
from app.services.soldier import age, diff_ym, soldier_summary, ym_text
from app.services.staffing import serving

router = APIRouter(tags=["reports"])

# strength movements of soldiers that still exist (deleted soldiers no longer count)
LIVE_MOVEMENT = StrengthMovement.soldier_id.in_(select(Soldier.id).where(Soldier.deleted_at.is_(None)))


def active_soldiers(db: Session, user: User, unit_id: int | None = None):
    stmt = serving(select(Soldier))
    scope = scope_unit_ids(db, user)
    if scope is not None:
        stmt = stmt.where(Soldier.current_unit_id.in_(scope))
    if unit_id:
        stmt = stmt.where(Soldier.current_unit_id.in_(unit_subtree_ids(db, unit_id)))
    return stmt


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def promotion_due(db: Session, user: User, unit_id: int | None = None) -> list[Soldier]:
    stmt = active_soldiers(db, user, unit_id).join(Rank, Rank.id == Soldier.current_rank_id).where(
        Rank.min_years_to_next.is_not(None), Soldier.rank_date.is_not(None),
        Soldier.rank_date <= func.date_sub(func.curdate(), literal_column("INTERVAL ranks.min_years_to_next YEAR")),
    ).order_by(Rank.sort_order.desc(), Soldier.rank_date)
    return list(db.scalars(stmt).unique())


def retirement_age(s: Soldier, by_gender: dict[str, int]) -> int:
    """The rank's retirement age when the rank defines one, otherwise the per-gender setting."""
    if s.rank and s.rank.retirement_age:
        return s.rank.retirement_age
    return by_gender.get(s.gender, by_gender["M"])


def retirement_due(db: Session, user: User, unit_id: int | None = None) -> list[tuple[Soldier, date]]:
    months = int(get_setting(db, "alert_months_ahead", "6") or 6)
    by_gender = {"M": int(get_setting(db, "retirement_age_male", "60") or 60),
                 "F": int(get_setting(db, "retirement_age_female", "55") or 55)}
    horizon = date.today() + timedelta(days=months * 30)
    # nobody can be due before the youngest possible retirement age: filter in SQL first
    youngest = min([*by_gender.values(), *(a for a in db.scalars(select(Rank.retirement_age)) if a)])
    stmt = active_soldiers(db, user, unit_id).where(Soldier.date_of_birth <= _add_years(horizon, -youngest))
    out = []
    for s in db.scalars(stmt).unique():
        retire_on = _add_years(s.date_of_birth, retirement_age(s, by_gender))
        if retire_on <= horizon:
            out.append((s, retire_on))
    return sorted(out, key=lambda x: x[1])


@router.get("/dashboard/summary")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require("dashboard", "view"))):
    today = date.today()
    soldiers = db.scalars(active_soldiers(db, user)).unique().all()
    by_class, by_gender, by_status, by_institution = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    institutions = {u.id: u.name_kh for u in db.scalars(select(Unit).where(Unit.level == 1))}
    for s in soldiers:
        by_class[s.rank.rank_class.name_kh if s.rank else "មិនទាន់កំណត់"] += 1
        by_gender["ប្រុស" if s.gender == "M" else "ស្រី"] += 1
        by_status[s.status.name_kh if s.status else "មិនទាន់កំណត់"] += 1
        root = int(s.unit.path.strip("/").split("/")[0]) if s.unit else None
        by_institution[institutions.get(root, "មិនទាន់កំណត់")] += 1

    scope = scope_unit_ids(db, user)
    total_stmt = select(func.count(Soldier.id)).where(Soldier.deleted_at.is_(None))
    if scope is not None:
        total_stmt = total_stmt.where(Soldier.current_unit_id.in_(scope))
    total_all = db.scalar(total_stmt)
    doc_in_month = db.scalar(select(func.count(DocumentIncoming.id)).where(
        DocumentIncoming.deleted_at.is_(None), extract("year", DocumentIncoming.doc_date) == today.year,
        extract("month", DocumentIncoming.doc_date) == today.month))
    doc_out_month = db.scalar(select(func.count(DocumentOutgoing.id)).where(
        DocumentOutgoing.deleted_at.is_(None), extract("year", DocumentOutgoing.doc_date) == today.year,
        extract("month", DocumentOutgoing.doc_date) == today.month))
    # decisions still in the approval workflow, per kind; those waiting at a step this user acts on; overdue ones
    live = select(Decision.kind, Decision.status, Decision.status_changed_at).where(
        Decision.deleted_at.is_(None), Decision.status.in_(IN_PROGRESS))
    in_workflow = db.execute(live).all()
    pending = defaultdict(int)
    for k, _, _ in in_workflow:
        pending[k] += 1
    mine = {st for st in IN_PROGRESS if user.can("wf_publish" if st == "approved" else f"wf_{st}", "approve")}
    cutoff = overdue_cutoff(db)
    waiting_for_me = sum(1 for _, st, _ in in_workflow if st in mine)
    overdue = sum(1 for _, _, changed in in_workflow if changed and changed < cutoff)

    # strength in/out for the last 12 months
    start = date(today.year - 1, today.month, 1)
    yy_col = extract("year", StrengthMovement.movement_date).label("yy")
    mm_col = extract("month", StrengthMovement.movement_date).label("mm")
    mv_stmt = select(yy_col, mm_col, StrengthMovement.direction, func.count()).where(
        StrengthMovement.movement_date >= start, LIVE_MOVEMENT)
    if scope is not None:
        mv_stmt = mv_stmt.where(StrengthMovement.unit_id.in_(scope))
    mv = db.execute(mv_stmt.group_by(yy_col, mm_col, StrengthMovement.direction)).all()
    months = []
    y, m = start.year, start.month
    for _ in range(13):
        months.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    series = {"in": dict.fromkeys(months, 0), "out": dict.fromkeys(months, 0)}
    for yy, mm, direction, c in mv:
        key = f"{int(yy)}-{int(mm):02d}"
        if key in series[direction]:
            series[direction][key] = c

    disc_ending = db.scalar(select(func.count(DisciplineRecord.id)).where(
        DisciplineRecord.deleted_at.is_(None), DisciplineRecord.end_date.between(today, today + timedelta(days=30))))

    return {
        "total_active": len(soldiers),
        "total_all": total_all,
        "by_rank_class": dict(by_class),
        "by_gender": dict(by_gender),
        "by_status": dict(by_status),
        "by_institution": dict(by_institution),
        "documents": {"incoming_month": doc_in_month, "outgoing_month": doc_out_month},
        "pending_decisions": {k: pending.get(k, 0) for k in DECISION_KINDS},
        "workflow": {"waiting_for_me": waiting_for_me, "overdue": overdue},
        "movements": {"months": months, "in": list(series["in"].values()), "out": list(series["out"].values())},
        "alerts": {
            "promotion_due": len(promotion_due(db, user)),
            "retirement_due": len(retirement_due(db, user)),
            "discipline_ending": disc_ending,
            "missing_photo": sum(1 for s in soldiers if not s.photo_path),
            "missing_national_id": sum(1 for s in soldiers if not s.national_id),
            "missing_unit": sum(1 for s in soldiers if not s.current_unit_id),
        },
    }


# ---------------- reports ----------------

REPORTS = {
    "strength_by_unit": "តារាងកម្លាំងតាមអង្គភាព",
    "strength_by_rank": "តារាងកម្លាំងតាមឋានន្តរស័ក្តិ",
    "soldier_list": "បញ្ជីយោធិន",
    "movements": "របាយការណ៍កើនថយ",
    "decisions": "បញ្ជីតែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងឋានន្តរស័ក្តិ",
    "promotion_due": "បញ្ជីយោធិនគ្រប់លក្ខខណ្ឌដំឡើងឋានន្តរស័ក្តិ",
    "retirement_due": "បញ្ជីយោធិនជិតដល់អាយុចូលនិវត្តន៍",
    "training": "របាយការណ៍បណ្ដុះបណ្ដាល",
    "discipline": "របាយការណ៍វិន័យ និងទណ្ឌកម្ម",
    "awards": "របាយការណ៍សរសើរ និងគ្រឿងឥស្សរិយយស",
    "retirement": "បញ្ជីសោធននិវត្តន៍ និងយោធិនប្រភេទ២",
    "separation": "បញ្ជីយោធិនចេញពីជួរ",
    "conscripts": "ស្ថិតិយុវជនបំពេញកាតព្វកិច្ចយោធា តាមរាជធានី/ខេត្ត",
}

SOLDIER_COLS = [("military_id", "អត្តលេខ"), ("rank_name", "ឋានន្តរស័ក្តិ"), ("name_kh", "គោត្តនាមនិងនាម"),
                ("gender", "ភេទ")]

# every soldier field the "soldier list" report can show (ជ្រើសរើសព័ត៌មាន); keys of soldier_summary + profile names
SOLDIER_FIELDS = {
    "military_id": "អត្តលេខ", "rank_name": "ឋានន្តរស័ក្តិ", "name_kh": "គោត្តនាម និងនាម", "name_latin": "ឈ្មោះឡាតាំង",
    "gender": "ភេទ", "date_of_birth": "ថ្ងៃខែឆ្នាំកំណើត", "age": "អាយុ", "phone": "ទូរសព្ទ",
    "position_name": "មុខតំណែង", "position_date": "ថ្ងៃខែឆ្នាំមុខតំណែង", "time_in_position": "រយៈពេលមុខតំណែង",
    "unit_name": "អង្គភាព", "unit_path": "ស្ថាប័នកងឯកភាព-អង្គភាព", "institution_name": "ចំណុះស្ថាប័នកងឯកភាព",
    "enlistment_date": "ថ្ងៃចូលបម្រើទ័ព", "service_length": "រយៈពេលបម្រើ", "rank_date": "ថ្ងៃឡើងស័ក្តិ",
    "time_in_rank": "រយៈពេលឡើងស័ក្តិ", "status_name": "ស្ថានភាព", "specialty_name": "ជំនាញឯកទេស",
}
DEFAULT_SOLDIER_FIELDS = ["military_id", "rank_name", "name_kh", "gender", "age", "position_name", "unit_name",
                          "enlistment_date", "service_length", "time_in_rank", "status_name"]


def _soldier_cells(s: Soldier) -> dict:
    return {"military_id": s.military_id, "rank_name": s.rank.name_kh if s.rank else "", "name_kh": s.name_kh,
            "gender": "ប្រុស" if s.gender == "M" else "ស្រី", "unit_name": s.unit.name_kh if s.unit else "",
            "position_name": s.position.name_kh if s.position else ""}


def build_report(db: Session, user: User, key: str, date_from: date | None, date_to: date | None,
                 unit_id: int | None, kind: str | None, fields: str | None = None) -> dict:
    if key not in REPORTS:
        raise HTTPException(404, "រកមិនឃើញរបាយការណ៍")
    df = date_from or date(date.today().year, 1, 1)
    dt = date_to or date.today()
    scope = scope_unit_ids(db, user)
    unit_ids = unit_subtree_ids(db, unit_id) if unit_id else None

    def soldier_in_scope(model):
        conds = []
        if scope is not None:
            conds.append(model.soldier_id.in_(select(Soldier.id).where(Soldier.current_unit_id.in_(scope))))
        if unit_ids is not None:
            conds.append(model.soldier_id.in_(select(Soldier.id).where(Soldier.current_unit_id.in_(unit_ids))))
        return conds

    cols: list[tuple[str, str]]
    rows: list[dict] = []
    totals = None

    if key == "strength_by_unit":
        classes = db.scalars(select(RankClass).order_by(RankClass.sort_order)).all()
        cols = [("unit", "អង្គភាព")] + [(f"c{c.id}", c.name_kh) for c in classes] + \
               [("none", "មិនទាន់កំណត់"), ("female", "ស្រី"), ("total", "សរុប")]
        units = db.scalars(select(Unit).order_by(Unit.path)).all()
        if unit_ids is not None:
            units = [u for u in units if u.id in unit_ids]
        if scope is not None:
            units = [u for u in units if u.id in scope]
        soldiers = db.scalars(active_soldiers(db, user, unit_id)).unique().all()
        counts = defaultdict(lambda: defaultdict(int))
        for s in soldiers:
            path_ids = [int(p) for p in s.unit.path.strip("/").split("/")] if s.unit else []
            for uid in path_ids:  # count in the unit and all of its parents
                counts[uid][f"c{s.rank.rank_class_id}" if s.rank else "none"] += 1
                counts[uid]["female"] += s.gender == "F"
                counts[uid]["total"] += 1
        for u in units:
            rows.append({"unit": ("　" * (u.level - 1)) + u.name_kh, "_level": u.level,
                         **{k: counts[u.id].get(k, 0) for k, _ in cols[1:]}})
        totals = {"unit": "សរុបរួម", **{k: 0 for k, _ in cols[1:]}}
        for s in soldiers:
            totals[f"c{s.rank.rank_class_id}" if s.rank else "none"] += 1
            totals["female"] += s.gender == "F"
            totals["total"] += 1

    elif key == "strength_by_rank":
        cols = [("rank_class", "ថ្នាក់"), ("rank", "ឋានន្តរស័ក្តិ"), ("male", "ប្រុស"), ("female", "ស្រី"), ("total", "សរុប")]
        soldiers = db.scalars(active_soldiers(db, user, unit_id)).unique().all()
        c = defaultdict(lambda: {"male": 0, "female": 0})
        for s in soldiers:
            c[s.current_rank_id]["female" if s.gender == "F" else "male"] += 1
        for r in db.scalars(select(Rank).order_by(Rank.sort_order.desc())):
            v = c.get(r.id, {"male": 0, "female": 0})
            rows.append({"rank_class": r.rank_class.name_kh, "rank": r.name_kh, **v, "total": v["male"] + v["female"]})
        if None in c:
            v = c[None]
            rows.append({"rank_class": "-", "rank": "មិនទាន់កំណត់", **v, "total": v["male"] + v["female"]})
        totals = {"rank_class": "សរុប", "rank": "", "male": sum(r["male"] for r in rows),
                  "female": sum(r["female"] for r in rows), "total": sum(r["total"] for r in rows)}

    elif key == "soldier_list":
        chosen = [f for f in (fields or "").split(",") if f in SOLDIER_FIELDS] or DEFAULT_SOLDIER_FIELDS
        cols = [(f, SOLDIER_FIELDS[f]) for f in chosen]
        stmt = active_soldiers(db, user, unit_id).outerjoin(Rank, Rank.id == Soldier.current_rank_id) \
            .order_by(Rank.sort_order.desc(), Soldier.name_kh)
        for s in db.scalars(stmt).unique():
            d = soldier_summary(s)
            d["gender"] = "ប្រុស" if s.gender == "M" else "ស្រី"
            rows.append(d)

    elif key == "movements":
        cols = [("movement_date", "កាលបរិច្ឆេទ"), ("direction", "កើន/ថយ"), ("reason", "មូលហេតុ")] + SOLDIER_COLS + \
               [("unit_name", "អង្គភាព"), ("note", "កំណត់សម្គាល់")]
        stmt = select(StrengthMovement).where(StrengthMovement.movement_date.between(df, dt), LIVE_MOVEMENT)
        if scope is not None:
            stmt = stmt.where(StrengthMovement.unit_id.in_(scope))
        if unit_ids is not None:
            stmt = stmt.where(StrengthMovement.unit_id.in_(unit_ids))
        ins = outs = 0
        for m in db.scalars(stmt.order_by(StrengthMovement.movement_date)).unique():
            ins += m.direction == "in"
            outs += m.direction == "out"
            rows.append({"movement_date": m.movement_date.isoformat(), "direction": "កើន" if m.direction == "in" else "ថយ",
                         "reason": MOVEMENT_REASONS.get(m.reason, m.reason), **_soldier_cells(m.soldier),
                         "unit_name": m.unit.name_kh if m.unit else "", "note": m.note or ""})
        totals = {"movement_date": "សរុប", "direction": f"កើន {ins} / ថយ {outs}"}

    elif key == "decisions":
        cols = [("kind", "ប្រភេទ"), ("decision_no", "លេខ"), ("effective_date", "ថ្ងៃចូលជាធរមាន")] + SOLDIER_COLS + \
               [("change", "ការផ្លាស់ប្ដូរ")]
        stmt = select(Decision).where(Decision.status == "published", Decision.deleted_at.is_(None),
                                      Decision.effective_date.between(df, dt))
        if kind:
            stmt = stmt.where(Decision.kind == kind)
        names = {"rank": {r.id: r.name_kh for r in db.scalars(select(Rank))},
                 "unit": {u.id: u.name_kh for u in db.scalars(select(Unit))},
                 "pos": {p.id: p.name_kh for p in db.scalars(select(Position))}}
        for d in db.scalars(stmt.order_by(Decision.effective_date)).unique():
            for it in d.items:
                if scope is not None and it.new_unit_id not in scope and it.old_unit_id not in scope:
                    continue
                if unit_ids is not None and it.new_unit_id not in unit_ids and it.old_unit_id not in unit_ids:
                    continue
                parts = []
                if it.new_rank_id:
                    parts.append(f"{names['rank'].get(it.old_rank_id, '-')} → {names['rank'][it.new_rank_id]}")
                if it.new_position_id:
                    parts.append(f"{names['pos'].get(it.old_position_id, '-')} → {names['pos'][it.new_position_id]}")
                if it.new_unit_id:
                    parts.append(f"{names['unit'].get(it.old_unit_id, '-')} → {names['unit'][it.new_unit_id]}")
                rows.append({"kind": DECISION_KINDS[d.kind], "decision_no": d.decision_no,
                             "effective_date": d.effective_date.isoformat(), **_soldier_cells(it.soldier),
                             "change": "; ".join(parts)})

    elif key == "promotion_due":
        cols = SOLDIER_COLS + [("unit_name", "អង្គភាព"), ("rank_date", "ថ្ងៃឡើងស័ក្តិ"), ("time_in_rank", "រយៈពេលឡើងស័ក្តិ"),
                               ("min_years", "លក្ខខណ្ឌ (ឆ្នាំ)")]
        for s in promotion_due(db, user, unit_id):
            rows.append({**_soldier_cells(s), "rank_date": s.rank_date.isoformat(),
                         "time_in_rank": ym_text(diff_ym(s.rank_date)), "min_years": s.rank.min_years_to_next})

    elif key == "retirement_due":
        cols = SOLDIER_COLS + [("unit_name", "អង្គភាព"), ("date_of_birth", "ថ្ងៃខែឆ្នាំកំណើត"), ("age", "អាយុ"),
                               ("retire_date", "ថ្ងៃគ្រប់អាយុនិវត្តន៍")]
        for s, rd in retirement_due(db, user, unit_id):
            rows.append({**_soldier_cells(s), "date_of_birth": s.date_of_birth.isoformat(),
                         "age": age(s.date_of_birth), "retire_date": rd.isoformat()})

    elif key == "training":
        cols = [("course", "វគ្គ"), ("course_type", "ប្រភេទ"), ("level", "កម្រិត"), ("where", "ក្នុង/ក្រៅប្រទេស"),
                ("start_date", "ចាប់ពី"), ("end_date", "ដល់")] + SOLDIER_COLS + [("result", "លទ្ធផល")]
        cambodia = db.scalar(select(Country.id).where(Country.name_en == "Cambodia"))
        stmt = select(TrainingCourse, TrainingParticipant).join(
            TrainingParticipant, TrainingParticipant.course_id == TrainingCourse.id).where(
            TrainingCourse.deleted_at.is_(None), TrainingCourse.start_date.between(df, dt), *soldier_in_scope(TrainingParticipant))
        if kind:
            stmt = stmt.where(TrainingCourse.course_type == kind)
        for c, p in db.execute(stmt.order_by(TrainingCourse.start_date)).unique():
            rows.append({"course": c.name, "course_type": "រយៈពេលវែង" if c.course_type == "long" else "រយៈពេលខ្លី",
                         "level": "វគ្គបំប៉ន" if c.level == "refresher" else "វគ្គបណ្ដុះបណ្ដាល",
                         "where": "ក្រៅប្រទេស" if c.country_id and c.country_id != cambodia else "ក្នុងប្រទេស",
                         "start_date": c.start_date.isoformat() if c.start_date else "",
                         "end_date": c.end_date.isoformat() if c.end_date else "",
                         **_soldier_cells(p.soldier), "result": p.result or ""})

    elif key in ("discipline", "awards", "retirement", "separation"):
        model, date_col, extra = {
            "discipline": (DisciplineRecord, DisciplineRecord.decision_date,
                           [("type", "ប្រភេទទណ្ឌកម្ម"), ("reason", "មូលហេតុ")]),
            "awards": (AwardRecord, AwardRecord.decision_date, [("type", "ប្រភេទ"), ("reason", "មូលហេតុ")]),
            "retirement": (RetirementRecord, RetirementRecord.effective_date, [("type", "ប្រភេទ"), ("notes", "កំណត់សម្គាល់")]),
            "separation": (SeparationRecord, SeparationRecord.effective_date, [("type", "មូលហេតុ"), ("notes", "កំណត់សម្គាល់")]),
        }[key]
        cols = [("decision_no", "លេខលិខិត"), ("date", "កាលបរិច្ឆេទ")] + SOLDIER_COLS + [("unit_name", "អង្គភាព")] + extra
        stmt = select(model).where(model.deleted_at.is_(None), date_col.between(df, dt), *soldier_in_scope(model))
        for r in db.scalars(stmt.order_by(date_col)).unique():
            if key == "discipline":
                t = r.discipline_type.name_kh if r.discipline_type else ""
            elif key == "awards":
                t = r.award_type.name_kh if r.award_type else ""
            elif key == "retirement":
                t = "សោធននិវត្តន៍" if r.type == "pension" else "យោធិនប្រភេទ២"
            else:
                t = r.reason.name_kh if r.reason else ""
            dval = getattr(r, date_col.key)
            rows.append({"decision_no": r.decision_no or "", "date": dval.isoformat() if dval else "",
                         **_soldier_cells(r.soldier), "type": t, "reason": getattr(r, "reason", "") if key in ("discipline", "awards") else "",
                         "notes": getattr(r, "notes", "") or ""})

    elif key == "conscripts":
        cols = [("province", "រាជធានី/ខេត្ត")] + [(st, label) for st, label in REGISTRATION_STATUSES.items()] + \
               [("total", "សរុប")]
        counts = registration_counts(db, (df.year, dt.year))
        names = {p.id: p.name_kh for p in db.scalars(select(Province).order_by(Province.id))}
        for pid in [*names, None]:
            row = {"province": names.get(pid, "មិនបានកំណត់"), **{st: counts.get((pid, st), 0) for st in REGISTRATION_STATUSES}}
            row["total"] = sum(row[st] for st in REGISTRATION_STATUSES)
            if row["total"]:
                rows.append(row)
        totals = {"province": "សរុប", **{k: sum(r[k] for r in rows) for k, _ in cols[1:]}}

    for i, r in enumerate(rows, start=1):
        r["no"] = i
    cols = [("no", "ល.រ")] + cols
    return {"key": key, "title": REPORTS[key], "date_from": df.isoformat(), "date_to": dt.isoformat(),
            "available_fields": [{"key": k, "label": v} for k, v in SOLDIER_FIELDS.items()] if key == "soldier_list" else None,
            "columns": [{"key": k, "label": lbl} for k, lbl in cols], "rows": rows, "totals": totals,
            "org_name": get_setting(db, "org_name_kh")}


@router.get("/reports")
def report_catalog(_: User = Depends(require("reports", "view"))):
    return [{"key": k, "title": v} for k, v in REPORTS.items()]


@router.get("/reports/{key}")
def run_report(key: str, date_from: date | None = None, date_to: date | None = None, unit_id: int | None = None,
               kind: str | None = None, fields: str | None = None, format: str = Query("json", pattern="^(json|xlsx)$"),
               db: Session = Depends(get_db), user: User = Depends(require("reports", "view"))):
    if format == "xlsx" and not user.can("reports", "export"):
        raise HTTPException(403, "គ្មានសិទ្ធិនាំចេញ")
    rep = build_report(db, user, key, date_from, date_to, unit_id, kind, fields)
    if format == "json":
        return rep
    wb = Workbook()
    ws = wb.active
    ws.title = key[:30]
    ncol = len(rep["columns"])
    ws.append([rep["title"]])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.append([f"ចាប់ពី {rep['date_from']} ដល់ {rep['date_to']}"])
    ws.append([c["label"] for c in rep["columns"]])
    for c in ws[3]:
        c.font = Font(bold=True)
    for r in rep["rows"]:
        ws.append([r.get(c["key"], "") for c in rep["columns"]])
    if rep["totals"]:
        ws.append([rep["totals"].get(c["key"], "") for c in rep["columns"]])
        for c in ws[ws.max_row]:
            c.font = Font(bold=True)
    for col in ws.iter_cols(min_row=3, max_row=3):
        ws.column_dimensions[col[0].column_letter].width = 20
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={key}.xlsx"})
