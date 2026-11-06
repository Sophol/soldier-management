"""Dashboard statistics, alerts and reports (JSON for screen/print, XLSX for export)."""

from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from sqlalchemy import and_, case, extract, false, func, or_, select, true
from sqlalchemy.orm import Session

from app.api.v1.conscripts import registration_counts
from app.api.v1.decisions import IN_PROGRESS, can_act_at, overdue_cutoff, visible_condition
from app.api.v1.records import (
    CAMBODIA_IDS,
    CASE_STATUS,
    CATEGORY2_TYPES,
    DISCIPLINE_STATUS,
    MOVEMENT_REASONS,
    PARTICIPANT_STATUS,
    RETIREMENT_TYPES,
    discipline_status,
)
from app.api.v1.soldiers import ID_EXPIRY_STATES, MISSING, id_expiry_state, search_clause
from app.api.v1.system import get_setting
from app.core.database import get_db
from app.core.deps import require
from app.core.permissions import DECISION_STATUSES
from app.models import (
    AuditLog,
    AwardRecord,
    Category2Record,
    Decision,
    DecisionItem,
    DisciplineRecord,
    DocumentIncoming,
    DocumentOutgoing,
    DocumentType,
    Lookup,
    MilitaryCard,
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
    UnitPosition,
    User,
)
from app.models.conscript import REGISTRATION_STATUSES
from app.models.decision import DECISION_KINDS
from app.services.cards import CARD_REASONS, CARD_STATUS, OUTDATED, card_status, outdated_card_clause, outdated_reasons
from app.services.common import in_batches, paginate, scope_unit_ids, unit_subtree_ids
from app.services.soldier import age, diff_ym, soldier_summary, years_to_next_rank, ym_text
from app.services.soldier_io import MAX_EXPORT_ROWS
from app.services.staffing import serving

router = APIRouter(tags=["reports"])

# strength movements of soldiers that still exist (deleted soldiers no longer count)
LIVE_MOVEMENT = StrengthMovement.soldier_id.in_(select(Soldier.id).where(Soldier.deleted_at.is_(None)))


def active_soldiers(db: Session, user: User, unit_id: int | None = None, stmt=None):
    """Serving soldiers in the user's scope (and unit). `stmt` replaces select(Soldier), e.g. for counts."""
    stmt = serving(stmt if stmt is not None else select(Soldier))
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


def _born_by(day: date, years: int) -> date:
    """The latest birth date whose `years`-th anniversary (_add_years) falls on or before `day`
    (one day later than _add_years(day, -years) when that misses a 29 February birthday)."""
    born = _add_years(day, -years)
    nxt = born + timedelta(days=1)
    return nxt if _add_years(nxt, years) <= day else born


def promotion_clause(db: Session):
    """SQL condition: time in rank reached the minimum for the soldier's service track (administrative / combat),
    the same rule as years_to_next_rank; one cut-off date per rank, so no soldier is loaded to check it."""
    today = date.today()
    combat = func.coalesce(Soldier.service_track, "admin") == "combat"
    conds = []
    for r in db.scalars(select(Rank)):
        admin_years = r.min_years_to_next
        combat_years = r.min_years_combat if r.min_years_combat is not None else r.min_years_to_next
        if admin_years is not None:
            conds.append(and_(Soldier.current_rank_id == r.id, ~combat,
                              Soldier.rank_date <= _add_years(today, -admin_years)))
        if combat_years is not None:
            conds.append(and_(Soldier.current_rank_id == r.id, combat,
                              Soldier.rank_date <= _add_years(today, -combat_years)))
    return or_(*conds) if conds else false()


def promotion_due(db: Session, user: User, unit_id: int | None = None) -> list[Soldier]:
    """Soldiers whose time in rank reached the minimum for their service track (administrative / combat)."""
    stmt = active_soldiers(db, user, unit_id).join(Rank, Rank.id == Soldier.current_rank_id).where(
        promotion_clause(db)).order_by(Rank.sort_order.desc(), Soldier.rank_date)
    return list(db.scalars(stmt).unique())


def retirement_ages(db: Session) -> dict[str, int]:
    return {"M": int(get_setting(db, "retirement_age_male", "60") or 60),
            "F": int(get_setting(db, "retirement_age_female", "55") or 55)}


def retirement_age(s: Soldier, by_gender: dict[str, int]) -> int:
    """The rank's retirement age when the rank defines one, otherwise the per-gender setting."""
    if s.rank and s.rank.retirement_age:
        return s.rank.retirement_age
    return by_gender.get(s.gender, by_gender["M"])


def retiring_clause(db: Session, horizon: date):
    """SQL condition: the soldier reaches the retirement age (retirement_age) on or before `horizon`."""
    by_gender = retirement_ages(db)
    by_rank = {r.id: r.retirement_age for r in db.scalars(select(Rank)) if r.retirement_age}
    dob = Soldier.date_of_birth
    conds = [and_(Soldier.current_rank_id == rid, dob <= _born_by(horizon, a)) for rid, a in by_rank.items()]
    gender_age = or_(Soldier.current_rank_id.is_(None), Soldier.current_rank_id.not_in(list(by_rank))) if by_rank else true()
    female = Soldier.gender == "F"
    conds.append(and_(gender_age, female, dob <= _born_by(horizon, by_gender["F"])))
    conds.append(and_(gender_age, or_(Soldier.gender.is_(None), ~female), dob <= _born_by(horizon, by_gender["M"])))
    return or_(*conds)


def retirement_horizon(db: Session) -> date:
    months = int(get_setting(db, "alert_months_ahead", "6") or 6)
    return date.today() + timedelta(days=months * 30)


def retirement_due(db: Session, user: User, unit_id: int | None = None) -> list[tuple[Soldier, date]]:
    return retiring_by(db, active_soldiers(db, user, unit_id), retirement_horizon(db))


def retiring_by(db: Session, stmt, horizon: date) -> list[tuple[Soldier, date]]:
    """Soldiers of `stmt` who reach their retirement age on or before `horizon`, with that date (soonest first)."""
    by_gender = retirement_ages(db)
    out = [(s, _add_years(s.date_of_birth, retirement_age(s, by_gender)))
           for s in db.scalars(stmt.where(retiring_clause(db, horizon))).unique()]
    return sorted(out, key=lambda x: x[1])


@router.get("/dashboard/summary")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require("dashboard", "view"))):
    today = date.today()
    # every count is done by the database (COUNT / GROUP BY): no soldier is loaded, whatever the strength
    def counts(*cols, joins=()):
        stmt = select(*cols, func.count(Soldier.id)).select_from(Soldier)
        for target, on in joins:
            stmt = stmt.outerjoin(target, on)
        return db.execute(active_soldiers(db, user, stmt=stmt).group_by(*cols)).all()

    def count_where(cond) -> int:
        return db.scalar(active_soldiers(db, user, stmt=select(func.count(Soldier.id)).select_from(Soldier)).where(cond))

    missing_conds = {
        "photo": or_(Soldier.photo_path.is_(None), Soldier.photo_path == ""),
        "national_id": or_(Soldier.national_id.is_(None), Soldier.national_id == ""),
        "unit": Soldier.current_unit_id.is_(None),
        "dob": Soldier.date_of_birth.is_(None),
        "enlistment": Soldier.enlistment_date.is_(None),
        "rank_date": Soldier.rank_date.is_(None),
    }
    totals = db.execute(active_soldiers(db, user, stmt=select(
        func.count(Soldier.id), *(func.coalesce(func.sum(case((cond, 1), else_=0)), 0) for cond in missing_conds.values()),
    ).select_from(Soldier))).one()
    total_active, missing = totals[0], dict(zip(missing_conds, totals[1:], strict=True))

    by_class, by_gender, by_status, by_institution = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    for name, n in counts(RankClass.name_kh, joins=[(Rank, Rank.id == Soldier.current_rank_id),
                                                     (RankClass, RankClass.id == Rank.rank_class_id)]):
        by_class[name or "មិនទាន់កំណត់"] += n
    for gender, n in counts(Soldier.gender):
        by_gender["ប្រុស" if gender == "M" else "ស្រី"] += n
    for name, n in counts(Lookup.name_kh):  # serving() already joins the status lookup
        by_status[name or "មិនទាន់កំណត់"] += n
    institutions = {u.id: u.name_kh for u in db.scalars(select(Unit).where(Unit.level == 1))}
    paths = dict(db.execute(select(Unit.id, Unit.path)).all())
    for unit_id, n in counts(Soldier.current_unit_id):
        root = int(paths[unit_id].strip("/").split("/")[0]) if unit_id in paths else None
        by_institution[institutions.get(root, "មិនទាន់កំណត់")] += n

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
    if (visible := visible_condition(db, user)) is not None:  # what the lists behind these counts show
        live = live.where(visible)
    in_workflow = db.execute(live).all()
    pending = defaultdict(int)
    for k, _, _ in in_workflow:
        pending[k] += 1
    mine = {st for st in IN_PROGRESS if can_act_at(user, st)}
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
        DisciplineRecord.deleted_at.is_(None), DisciplineRecord.cancelled.is_(False),
        DisciplineRecord.end_date.between(today, today + timedelta(days=30))))
    cards_stmt = select(func.count(MilitaryCard.id)).join(Soldier, Soldier.id == MilitaryCard.soldier_id).where(
        MilitaryCard.deleted_at.is_(None), MilitaryCard.status == "issued", Soldier.deleted_at.is_(None),
        MilitaryCard.expiry_date.between(today, today + timedelta(days=30)))
    if scope is not None:
        cards_stmt = cards_stmt.where(Soldier.current_unit_id.in_(scope))
    cards_expiring = db.scalar(cards_stmt)

    return {
        "total_active": total_active,
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
            "promotion_due": count_where(promotion_clause(db)),
            "retirement_due": count_where(retiring_clause(db, retirement_horizon(db))),
            "discipline_ending": disc_ending,
            "cards_expiring": cards_expiring,
            **{f"missing_{k}": int(v) for k, v in missing.items()},
        },
        # យោធិនប្រភេទ១ = serving soldiers; ប្រភេទ២ = soldiers moved to category 2 (no longer in the strength)
        "categories": {"category1": total_active, **_category2_counts(db, scope)},
        "requests": {  # សំណើ (document type "request") registered this year
            "incoming": _requests(db, DocumentIncoming, today.year), "outgoing": _requests(db, DocumentOutgoing, today.year)},
        "studying": _studying(db, scope, today),
    }


def _category2_counts(db: Session, scope) -> dict:
    """យោធិនប្រភេទ២ (ពលី, ពលី-មរណ, ពិការ): soldiers with a category-2 record, by type."""
    stmt = select(Category2Record.type, func.count(func.distinct(Category2Record.soldier_id))).join(
        Soldier, Soldier.id == Category2Record.soldier_id).where(
        Category2Record.deleted_at.is_(None), Soldier.deleted_at.is_(None))
    if scope is not None:
        stmt = stmt.where(Soldier.current_unit_id.in_(scope))
    by_type = dict(db.execute(stmt.group_by(Category2Record.type)).all())
    return {"category2": sum(by_type.values()),
            "category2_by_type": {k: by_type.get(k, 0) for k in CATEGORY2_TYPES} | {"none": by_type.get(None, 0)}}


def _requests(db: Session, model, year: int) -> int:
    return db.scalar(select(func.count(model.id)).join(DocumentType, DocumentType.id == model.document_type_id).where(
        model.deleted_at.is_(None), model.year == year, DocumentType.name_kh == "សំណើ")) or 0


def _studying(db: Session, scope, today: date) -> dict:
    """Serving soldiers still studying (participant status កំពុងរៀន) in a course that has not ended,
    in Cambodia (no country, or Cambodia) and abroad. A course without dates counts as running."""
    stmt = serving(select(TrainingCourse.country_id, func.count(func.distinct(Soldier.id)))
                   .select_from(Soldier).join(TrainingParticipant, TrainingParticipant.soldier_id == Soldier.id)
                   .join(TrainingCourse, TrainingCourse.id == TrainingParticipant.course_id)).where(
        TrainingCourse.deleted_at.is_(None), TrainingParticipant.status == "studying",
        or_(TrainingCourse.start_date.is_(None), TrainingCourse.start_date <= today),
        or_(TrainingCourse.end_date.is_(None), TrainingCourse.end_date >= today))
    if scope is not None:
        stmt = stmt.where(Soldier.current_unit_id.in_(scope))
    cambodia = set(db.scalars(CAMBODIA_IDS))
    rows = db.execute(stmt.group_by(TrainingCourse.country_id)).all()
    abroad = sum(n for country, n in rows if country and country not in cambodia)
    return {"in_country": sum(n for _, n in rows) - abroad, "abroad": abroad}


# ---------------- activity feed (who is doing what) ----------------

ACTION_NAMES = {
    "create": "បានបន្ថែម", "update": "បានកែប្រែ", "delete": "បានលុប", "login": "បានចូលប្រព័ន្ធ",
    "submit": "បានដាក់ជូន", "approve": "បានអនុម័ត", "return": "បានត្រឡប់ទៅកែ", "reject": "បានបដិសេធ",
    "cancel": "បានលុបចោល", "upload": "បានភ្ជាប់ឯកសារ", "upload_photo": "បានដាក់រូបថត",
    "change_password": "បានប្ដូរពាក្យសម្ងាត់", "deactivate": "បានបិទគណនី", "update_permissions": "បានកែសិទ្ធិ",
    "upload_logo": "បានប្ដូរឡូហ្គោ", "import": "បាននាំចូល Excel",
}
TABLE_NAMES = {
    "soldiers": "ប្រវត្តិរូបយោធិន", "decisions": "សេចក្ដីសម្រេច", "documents_incoming": "ឯកសារចូល",
    "documents_outgoing": "ឯកសារចេញ", "training_courses": "វគ្គបណ្ដុះបណ្ដាល", "award_records": "ការសរសើរ",
    "discipline_records": "វិន័យ", "retirement_records": "សោធននិវត្តន៍",
    "category2_records": "យោធិនប្រភេទ២", "separation_records": "ចេញពីជួរ",
    "strength_movements": "កើនថយ", "conscripts": "យុវជនកាតព្វកិច្ច", "conscript_registrations": "ការចុះឈ្មោះកាតព្វកិច្ច",
    "conscript_medicals": "ការពិនិត្យសុខភាព", "conscript_services": "ការបម្រើកាតព្វកិច្ច", "users": "អ្នកប្រើប្រាស់",
    "roles": "តួនាទី", "units": "អង្គភាព", "unit_positions": "ក្របខណ្ឌ", "document_files": "ឯកសារភ្ជាប់",
    "soldier_attachments": "ឯកសារភ្ជាប់យោធិន", "settings": "ការកំណត់",
}


def _what(log: AuditLog) -> str | None:
    data = log.after or log.before or {}
    for key in ("name_kh", "decision_no", "incoming_no", "outgoing_no", "name", "username", "subject"):
        if data.get(key):
            return str(data[key])[:80]
    return None


@router.get("/dashboard/activity")
def activity(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
             _: User = Depends(require("audit", "view"))):
    """The latest actions of every user, for leadership to follow the work in progress."""
    logs = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
    return [{"id": a.id, "at": a.created_at.isoformat(), "user": a.user.full_name if a.user else "-",
             "action": ACTION_NAMES.get(a.action, a.action), "action_code": a.action,
             "table": TABLE_NAMES.get(a.table_name, a.table_name), "what": _what(a)} for a in logs]


# ---------------- reports ----------------

REPORTS = {
    "strength_by_unit": "តារាងកម្លាំងតាមអង្គភាព",
    "strength_by_rank": "តារាងកម្លាំងតាមឋានន្តរស័ក្តិ",
    "strength_by_age": "តារាងកម្លាំងតាមក្រុមអាយុ និងភេទ",
    "staffing": "ក្របខណ្ឌកំណត់ និងជាក់ស្ដែង (ទំនេរ/ខ្វះ/លើស)",
    "missing_data": "ទិន្នន័យខ្វះ តាមអង្គភាព",
    "soldier_list": "បញ្ជីយោធិន",
    "movements": "របាយការណ៍កើនថយ",
    "decisions": "បញ្ជីតែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងឋានន្តរស័ក្តិ",
    "decision_status": "សំណើតាមស្ថានភាពអនុម័ត",
    "promotion_due": "បញ្ជីយោធិនគ្រប់លក្ខខណ្ឌដំឡើងឋានន្តរស័ក្តិ",
    "retirement_due": "បញ្ជីយោធិនជិតដល់អាយុចូលនិវត្តន៍",
    "training": "របាយការណ៍បណ្ដុះបណ្ដាល",
    "discipline": "របាយការណ៍វិន័យ និងទណ្ឌកម្ម",
    "awards": "របាយការណ៍សរសើរ និងគ្រឿងឥស្សរិយយស",
    "retirement": "បញ្ជីសោធននិវត្តន៍",
    "category2": "បញ្ជីយោធិនប្រភេទ២ (ពលី ពលី-មរណ ពិការ)",
    "separation": "បញ្ជីយោធិនចេញពីជួរ",
    "id_cards": "របាយការណ៍អត្តសញ្ញាណប័ណ្ណយោធិន",
    "policy": "ការងារគោលនយោបាយ — អត្តសញ្ញាណប័ណ្ណសញ្ជាតិជិតផុត/ផុតកំណត់",
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


KH_DIGITS = str.maketrans("0123456789", "០១២៣៤៥៦៧៨៩")
# ក្រុមអាយុ: (from, to) inclusive; None = open-ended
AGE_GROUPS = [(None, 24), (25, 29), (30, 34), (35, 39), (40, 44), (45, 49), (50, 54), (55, 59), (60, None)]


def _age_group_label(lo: int | None, hi: int | None) -> str:
    if lo is None:
        return f"ក្រោម {hi + 1} ឆ្នាំ".translate(KH_DIGITS)
    if hi is None:
        return f"{lo} ឆ្នាំឡើង".translate(KH_DIGITS)
    return f"{lo}–{hi} ឆ្នាំ".translate(KH_DIGITS)


def _age_group(age_years: int | None) -> int:
    """Index in AGE_GROUPS (-1 = unknown birth date)."""
    if age_years is None:
        return -1
    for i, (lo, hi) in enumerate(AGE_GROUPS):
        if (lo is None or age_years >= lo) and (hi is None or age_years <= hi):
            return i
    return -1


MISSING_COLS = [("photo", "ខ្វះរូបថត"), ("dob", "ខ្វះថ្ងៃកំណើត"), ("enlistment", "ខ្វះថ្ងៃចូលទ័ព"),
                ("rank_date", "ខ្វះថ្ងៃឡើងស័ក្តិ"), ("national_id", "ខ្វះលេខអត្តសញ្ញាណប័ណ្ណ"), ("phone", "ខ្វះទូរស័ព្ទ"),
                ("attachments", "ខ្វះឯកសារភ្ជាប់")]


def _numbered(rows, start: int = 0):
    for i, r in enumerate(rows, start=start + 1):
        r["no"] = i
        yield r


def build_report(db: Session, user: User, key: str, date_from: date | None, date_to: date | None,
                 unit_id: int | None, kind: str | None, fields: str | None = None,
                 page: int | None = None, size: int = 100) -> dict:
    """page/size: the soldier list shows one page on screen and in print; without a page (Excel) its rows are a
    stream loaded in batches, so a list of any length never sits in memory at once."""
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
    totals = paging = None
    first = 0  # number of rows before this page

    if key == "strength_by_unit":
        # kind="rank": one column per rank (ឋានន្តរស័ក្តិ) instead of per rank class
        by_rank = kind == "rank"
        if by_rank:
            groups = [(f"r{r.id}", r.name_kh) for r in db.scalars(select(Rank).order_by(Rank.sort_order.desc()))]
        else:
            groups = [(f"c{c.id}", c.name_kh) for c in db.scalars(select(RankClass).order_by(RankClass.sort_order))]

        rank_class = {r.id: r.rank_class_id for r in db.scalars(select(Rank))}

        def group_key(rank_id: int | None) -> str:
            if not rank_id:
                return "none"
            return f"r{rank_id}" if by_rank else f"c{rank_class[rank_id]}"

        cols = [("unit", "អង្គភាព")] + groups + [("none", "មិនទាន់កំណត់"), ("female", "ស្រី"), ("total", "សរុប")]
        all_units = db.scalars(select(Unit).order_by(Unit.path)).all()
        paths = {u.id: u.path for u in all_units}
        units = all_units
        if unit_ids is not None:
            units = [u for u in units if u.id in unit_ids]
        if scope is not None:
            units = [u for u in units if u.id in scope]
        # one row per unit / rank / gender, counted by the database
        stmt = select(Soldier.current_unit_id, Soldier.current_rank_id, Soldier.gender, func.count(Soldier.id)) \
            .select_from(Soldier)
        grouped = db.execute(active_soldiers(db, user, unit_id, stmt).group_by(
            Soldier.current_unit_id, Soldier.current_rank_id, Soldier.gender)).all()
        counts = defaultdict(lambda: defaultdict(int))
        totals = {"unit": "សរុបរួម", **{k: 0 for k, _ in cols[1:]}}
        for soldier_unit, rank_id, gender, n in grouped:
            path_ids = [int(p) for p in paths[soldier_unit].strip("/").split("/")] if soldier_unit in paths else []
            for target in [*(counts[uid] for uid in path_ids), totals]:  # the unit, all of its parents, the total
                target[group_key(rank_id)] += n
                target["female"] += n if gender == "F" else 0
                target["total"] += n
        for u in units:
            rows.append({"unit": ("　" * (u.level - 1)) + u.name_kh, "_level": u.level,
                         **{k: counts[u.id].get(k, 0) for k, _ in cols[1:]}})

    elif key == "strength_by_rank":
        cols = [("rank_class", "ថ្នាក់"), ("rank", "ឋានន្តរស័ក្តិ"), ("male", "ប្រុស"), ("female", "ស្រី"), ("total", "សរុប")]
        stmt = select(Soldier.current_rank_id, Soldier.gender, func.count(Soldier.id)).select_from(Soldier)
        c = defaultdict(lambda: {"male": 0, "female": 0})
        for rank_id, gender, n in db.execute(active_soldiers(db, user, unit_id, stmt).group_by(
                Soldier.current_rank_id, Soldier.gender)):
            c[rank_id]["female" if gender == "F" else "male"] += n
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
        stmt = active_soldiers(db, user, unit_id).order_by(Soldier.rank_sort.desc(), Soldier.name_kh)
        if page:
            soldiers, total = paginate(db, stmt, page, size)
            paging, first = {"page": page, "size": size, "total": total}, (page - 1) * size
        else:
            total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
            if total > MAX_EXPORT_ROWS:
                raise HTTPException(400, f"ទិន្នន័យច្រើនពេកសម្រាប់ Excel ({total:,} ជួរ; អតិបរមា {MAX_EXPORT_ROWS:,})"
                                         " — សូមជ្រើសរើសអង្គភាព")
            soldiers = in_batches(db, stmt)

        def list_row(s: Soldier) -> dict:
            d = soldier_summary(s)
            d["gender"] = "ប្រុស" if s.gender == "M" else "ស្រី"
            return d
        rows = (list_row(s) for s in soldiers)

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
        stmt = select(Decision).where(Decision.status == "approved", Decision.deleted_at.is_(None),
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
                         "time_in_rank": ym_text(diff_ym(s.rank_date)), "min_years": years_to_next_rank(s)})

    elif key == "retirement_due":
        cols = SOLDIER_COLS + [("unit_name", "អង្គភាព"), ("date_of_birth", "ថ្ងៃខែឆ្នាំកំណើត"), ("age", "អាយុ"),
                               ("retire_date", "ថ្ងៃគ្រប់អាយុនិវត្តន៍")]
        for s, rd in retirement_due(db, user, unit_id):
            rows.append({**_soldier_cells(s), "date_of_birth": s.date_of_birth.isoformat(),
                         "age": age(s.date_of_birth), "retire_date": rd.isoformat()})

    elif key == "training":
        cols = [("course", "វគ្គ"), ("course_type", "ប្រភេទ"), ("level", "កម្រិត"), ("where", "ក្នុង/ក្រៅប្រទេស"),
                ("start_date", "ចាប់ពី"), ("end_date", "ដល់")] + SOLDIER_COLS + [("participant_status", "ស្ថានភាព"), ("result", "លទ្ធផល")]
        cambodia = set(db.scalars(CAMBODIA_IDS))
        stmt = select(TrainingCourse, TrainingParticipant).join(
            TrainingParticipant, TrainingParticipant.course_id == TrainingCourse.id).where(
            TrainingCourse.deleted_at.is_(None), TrainingCourse.start_date.between(df, dt), *soldier_in_scope(TrainingParticipant))
        if kind:
            stmt = stmt.where(TrainingCourse.course_type == kind)
        for c, p in db.execute(stmt.order_by(TrainingCourse.start_date)).unique():
            rows.append({"course": c.name, "course_type": "រយៈពេលវែង" if c.course_type == "long" else "រយៈពេលខ្លី",
                         "level": "វគ្គបំប៉ន" if c.level == "refresher" else "វគ្គបណ្ដុះបណ្ដាល",
                         "where": "ក្រៅប្រទេស" if c.country_id and c.country_id not in cambodia else "ក្នុងប្រទេស",
                         "start_date": c.start_date.isoformat() if c.start_date else "",
                         "end_date": c.end_date.isoformat() if c.end_date else "",
                         **_soldier_cells(p.soldier), "result": p.result or "",
                         "participant_status": PARTICIPANT_STATUS.get(p.status, "")})

    elif key in ("discipline", "awards", "retirement", "category2", "separation"):
        model, date_col, extra = {
            "discipline": (DisciplineRecord, DisciplineRecord.decision_date,
                           [("type", "ប្រភេទទណ្ឌកម្ម"), ("level", "កម្រិត"), ("reason", "មូលហេតុ"),
                            ("status", "ស្ថានភាព")]),
            "awards": (AwardRecord, AwardRecord.decision_date, [("type", "ប្រភេទ"), ("level", "កម្រិត/ថ្នាក់"),
                                                                ("by", "អ្នកផ្ដល់"), ("reason", "មូលហេតុ")]),
            "retirement": (RetirementRecord, RetirementRecord.effective_date, [("type", "ប្រភេទ"),
                                                                              ("status", "ស្ថានភាពសំណុំរឿង"),
                                                                              ("notes", "កំណត់សម្គាល់")]),
            "category2": (Category2Record, Category2Record.effective_date, [("type", "ប្រភេទ"), ("notes", "កំណត់សម្គាល់")]),
            "separation": (SeparationRecord, SeparationRecord.effective_date, [("type", "មូលហេតុ"), ("notes", "កំណត់សម្គាល់")]),
        }[key]
        cols = [("decision_no", "លេខលិខិត"), ("date", "កាលបរិច្ឆេទ")] + SOLDIER_COLS + [("unit_name", "អង្គភាព")] + extra
        stmt = select(model).where(model.deleted_at.is_(None), date_col.between(df, dt), *soldier_in_scope(model))
        if key == "retirement" and kind:  # pension / voluntary
            stmt = stmt.where(RetirementRecord.type == kind)
        if key == "category2" and kind:  # fallen / fallen_dead / disabled
            stmt = stmt.where(Category2Record.type == kind)
        for r in db.scalars(stmt.order_by(date_col)).unique():
            status = ""
            if key == "discipline":
                t = r.discipline_type.name_kh if r.discipline_type else ""
                status = DISCIPLINE_STATUS[discipline_status(r)]
            elif key == "awards":
                t = r.award_type.name_kh if r.award_type else ""
            elif key == "retirement":
                t = RETIREMENT_TYPES.get(r.type, r.type)
                status = CASE_STATUS.get(r.case_status, "")
            elif key == "category2":
                t = CATEGORY2_TYPES.get(r.type, "មិនទាន់កំណត់")
            else:
                t = r.reason.name_kh if r.reason else ""
            dval = getattr(r, date_col.key)
            rows.append({"decision_no": r.decision_no or "", "date": dval.isoformat() if dval else "",
                         **_soldier_cells(r.soldier), "type": t, "reason": getattr(r, "reason", "") if key in ("discipline", "awards") else "",
                         "notes": getattr(r, "notes", "") or "", "level": getattr(r, "level", "") or "",
                         "by": getattr(r, "awarded_by", "") or "", "status": status})

    elif key == "strength_by_age":
        classes = [(f"c{c.id}", c.name_kh) for c in db.scalars(select(RankClass).order_by(RankClass.sort_order))]
        rank_class = {r.id: r.rank_class_id for r in db.scalars(select(Rank))}
        cols = [("age_group", "ក្រុមអាយុ")] + classes + [("male", "ប្រុស"), ("female", "ស្រី"), ("total", "សរុប")]
        groups = [_age_group_label(lo, hi) for lo, hi in AGE_GROUPS]
        counts = {i: {k: 0 for k, _ in cols[1:]} for i in [*range(len(AGE_GROUPS)), -1]}
        # grouped by birth date (a few thousand distinct days at most), then put into age groups here
        stmt = select(Soldier.date_of_birth, Soldier.current_rank_id, Soldier.gender, func.count(Soldier.id)).select_from(Soldier)
        for dob, rank_id, gender, n in db.execute(active_soldiers(db, user, unit_id, stmt).group_by(
                Soldier.date_of_birth, Soldier.current_rank_id, Soldier.gender)):
            c = counts[_age_group(age(dob))]
            if rank_id in rank_class:
                c[f"c{rank_class[rank_id]}"] += n
            c["female" if gender == "F" else "male"] += n
            c["total"] += n
        for i, label in [*enumerate(groups), (-1, "មិនស្គាល់ថ្ងៃកំណើត")]:
            if i >= 0 or counts[-1]["total"]:
                rows.append({"age_group": label, **counts[i]})
        totals = {"age_group": "សរុប", **{k: sum(r[k] for r in rows) for k, _ in cols[1:]}}

    elif key == "staffing":
        # kind: vacant (ខ្វះ) / full (គ្រប់) / over (លើស)
        cols = [("unit", "អង្គភាព"), ("position", "មុខតំណែង"), ("ranks", "ឋានន្តរស័ក្តិ"), ("quota", "ក្របខណ្ឌកំណត់"),
                ("filled", "ជាក់ស្ដែង"), ("vacant", "ទំនេរ (ខ្វះ)"), ("over", "លើស")]
        stmt = select(UnitPosition).join(Unit, Unit.id == UnitPosition.unit_id).join(
            Position, Position.id == UnitPosition.position_id)
        if scope is not None:
            stmt = stmt.where(UnitPosition.unit_id.in_(scope))
        if unit_ids is not None:
            stmt = stmt.where(UnitPosition.unit_id.in_(unit_ids))
        filled_stmt = select(Soldier.current_unit_id, Soldier.current_position_id, func.count(Soldier.id)).select_from(Soldier)
        filled = {(u, p): n for u, p, n in db.execute(active_soldiers(db, user, unit_id, filled_stmt).group_by(
            Soldier.current_unit_id, Soldier.current_position_id))}
        rank_names = {r.id: r.name_kh for r in db.scalars(select(Rank))}
        for up in db.scalars(stmt.order_by(Unit.path, Unit.sort_order, Position.sort_order, Position.name_kh)).unique():
            n = filled.get((up.unit_id, up.position_id), 0)
            state = "vacant" if n < up.quota else "over" if n > up.quota else "full"
            if kind in ("vacant", "full", "over") and kind != state:
                continue
            ranks = " – ".join(x for x in (rank_names.get(up.min_rank_id), rank_names.get(up.max_rank_id)) if x)
            rows.append({"unit": up.unit.name_kh, "position": up.position.name_kh, "ranks": ranks, "quota": up.quota,
                         "filled": n, "vacant": max(up.quota - n, 0), "over": max(n - up.quota, 0)})
        totals = {"unit": "សរុប", **{k: sum(r[k] for r in rows) for k in ("quota", "filled", "vacant", "over")}}

    elif key == "missing_data":
        keys = [k for k, _ in MISSING_COLS]
        cols = [("unit", "អង្គភាព"), ("total", "យោធិនសរុប")] + MISSING_COLS
        stmt = select(Soldier.current_unit_id, func.count(Soldier.id),
                      *(func.sum(case((MISSING[k], 1), else_=0)) for k in keys)).select_from(Soldier)
        grouped = db.execute(active_soldiers(db, user, unit_id, stmt).group_by(Soldier.current_unit_id)).all()
        all_units = db.scalars(select(Unit).order_by(Unit.path)).all()
        paths = {u.id: u.path for u in all_units}
        counts = defaultdict(lambda: defaultdict(int))
        totals = {"unit": "សរុបរួម", **{k: 0 for k, _ in cols[1:]}}
        no_unit = None
        for soldier_unit, total, *missing in grouped:
            values = {"total": total, **{k: int(v or 0) for k, v in zip(keys, missing, strict=True)}}
            if soldier_unit is None:
                no_unit = values
            path_ids = [int(p) for p in paths[soldier_unit].strip("/").split("/")] if soldier_unit in paths else []
            for target in [*(counts[uid] for uid in path_ids), totals]:  # the unit, all of its parents, the total
                for k, v in values.items():
                    target[k] += v
        for u in all_units:
            if (unit_ids is None or u.id in unit_ids) and (scope is None or u.id in scope) and counts[u.id]["total"]:
                rows.append({"unit": ("　" * (u.level - 1)) + u.name_kh, "_level": u.level,
                             **{k: counts[u.id].get(k, 0) for k, _ in cols[1:]}})
        if no_unit:
            rows.append({"unit": "មិនទាន់មានអង្គភាព", **no_unit})

    elif key == "decision_status":
        statuses = list(DECISION_STATUSES)
        cols = [("kind", "ប្រភេទសំណើ")] + [(st, DECISION_STATUSES[st]) for st in statuses] + [("total", "សរុប")]
        stmt = select(Decision.kind, Decision.status, func.count(Decision.id)).where(
            Decision.deleted_at.is_(None), Decision.decision_date.between(df, dt))
        if (visible := visible_condition(db, user)) is not None:
            stmt = stmt.where(visible)
        if unit_ids is not None:
            stmt = stmt.where(Decision.id.in_(select(DecisionItem.decision_id).where(
                or_(DecisionItem.new_unit_id.in_(unit_ids), DecisionItem.old_unit_id.in_(unit_ids)))))
        if kind:
            stmt = stmt.where(Decision.kind == kind)
        counts = {(k, st): n for k, st, n in db.execute(stmt.group_by(Decision.kind, Decision.status))}
        for k, label in DECISION_KINDS.items():
            if kind and k != kind:
                continue
            row = {"kind": label, **{st: counts.get((k, st), 0) for st in statuses}}
            row["total"] = sum(row[st] for st in statuses)
            rows.append(row)
        totals = {"kind": "សរុប", **{c: sum(r[c] for r in rows) for c, _ in cols[1:]}}

    elif key == "id_cards":
        # kind: expiring (within 90 days) / expired / outdated (old rank/position) / pending / lost; by default every
        # card except those already replaced
        cols = SOLDIER_COLS + [("unit_name", "អង្គភាព"), ("card_no", "លេខប័ណ្ណ"), ("issue_date", "ថ្ងៃចេញ"),
                               ("expiry_date", "ថ្ងៃផុតកំណត់"), ("days_left", "នៅសល់ (ថ្ងៃ)"), ("status", "ស្ថានភាព"),
                               ("reason", "មូលហេតុ"), ("outdated", "ត្រូវធ្វើប័ណ្ណថ្មី")]
        today = date.today()
        stmt = select(MilitaryCard).where(MilitaryCard.deleted_at.is_(None), *soldier_in_scope(MilitaryCard))
        if kind == "expiring":
            stmt = stmt.where(MilitaryCard.status == "issued", MilitaryCard.expiry_date.between(today, today + timedelta(days=90)))
        elif kind == "expired":
            stmt = stmt.where(MilitaryCard.status == "issued", MilitaryCard.expiry_date < today)
        elif kind == "outdated":
            stmt = stmt.where(outdated_card_clause())
        elif kind in ("pending", "lost"):
            stmt = stmt.where(MilitaryCard.status == kind)
        else:
            stmt = stmt.where(MilitaryCard.status != "replaced")
        for c in db.scalars(stmt.order_by(MilitaryCard.expiry_date.is_(None), MilitaryCard.expiry_date)).unique():
            st = card_status(c)
            rows.append({**_soldier_cells(c.soldier), "card_no": c.card_no or "",
                         "issue_date": c.issue_date.isoformat() if c.issue_date else "",
                         "expiry_date": c.expiry_date.isoformat() if c.expiry_date else "",
                         "days_left": (c.expiry_date - today).days if c.expiry_date and st == "issued" else "",
                         "status": CARD_STATUS[st], "reason": CARD_REASONS.get(c.reason or "", ""),
                         "outdated": ", ".join(OUTDATED[k] for k in outdated_reasons(c))})
        by_status = defaultdict(int)
        for r in rows:
            by_status[r["status"]] += 1
        totals = {"military_id": "សរុប", "rank_name": f"{len(rows)} ប័ណ្ណ",
                  "status": " / ".join(f"{k} {v}" for k, v in by_status.items())}

    elif key == "policy":
        # kind: soon (within the alert horizon) / expired; both by default
        cols = SOLDIER_COLS + [("unit_name", "អង្គភាព"), ("national_id", "លេខអត្តសញ្ញាណប័ណ្ណ"),
                               ("expiry", "ថ្ងៃផុតកំណត់"), ("days_left", "នៅសល់ (ថ្ងៃ)"), ("state", "ស្ថានភាព"),
                               ("phone", "ទូរស័ព្ទ")]
        horizon_days = int(get_setting(db, "alert_months_ahead", "6") or 6) * 30
        today = date.today()
        upto = today - timedelta(days=1) if kind == "expired" else today + timedelta(days=horizon_days)
        stmt = active_soldiers(db, user, unit_id).where(Soldier.national_id_expiry.is_not(None),
                                                        Soldier.national_id_expiry <= upto)
        if kind == "soon":
            stmt = stmt.where(Soldier.national_id_expiry >= today)
        for s in db.scalars(stmt.order_by(Soldier.national_id_expiry)).unique():
            rows.append({**_soldier_cells(s), "national_id": s.national_id or "", "expiry": s.national_id_expiry.isoformat(),
                         "days_left": (s.national_id_expiry - today).days, "phone": s.phone or "",
                         "state": ID_EXPIRY_STATES[id_expiry_state(s.national_id_expiry, horizon_days)]})

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

    rows = _numbered(rows, first)
    if not (key == "soldier_list" and not page):
        rows = list(rows)
    cols = [("no", "ល.រ")] + cols
    return {"key": key, "title": REPORTS[key], "date_from": df.isoformat(), "date_to": dt.isoformat(),
            "available_fields": [{"key": k, "label": v} for k, v in SOLDIER_FIELDS.items()] if key == "soldier_list" else None,
            "columns": [{"key": k, "label": lbl} for k, lbl in cols], "rows": rows, "totals": totals,
            "paging": paging, "org_name": get_setting(db, "org_name_kh")}


@router.get("/retirement-due", tags=["retirement"])
def list_retirement_due(months: int | None = Query(None, ge=0, le=120), unit_id: int | None = None,
                        q: str | None = None, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=1000),
                        db: Session = Depends(get_db), user: User = Depends(require("retirement", "view"))):
    """បង្ហាញទិន្នន័យជិតដល់អាយុចូលនិវត្តន៍: serving soldiers who reach their retirement age within `months`
    (default: the alert setting), those already past it included; soonest first."""
    today = date.today()
    horizon = today + timedelta(days=months * 30) if months is not None else retirement_horizon(db)
    stmt = active_soldiers(db, user, unit_id)
    if q and q.strip():
        stmt = stmt.where(search_clause(db, q))
    found = retiring_by(db, stmt, horizon)
    by_gender = retirement_ages(db)
    items = [{**soldier_summary(s), "retire_date": rd.isoformat(), "retire_age": retirement_age(s, by_gender),
              "days_left": (rd - today).days} for s, rd in found[(page - 1) * size: page * size]]
    return {"items": items, "total": len(found), "page": page, "size": size, "horizon": horizon.isoformat()}


@router.get("/reports")
def report_catalog(_: User = Depends(require("reports", "view"))):
    return [{"key": k, "title": v} for k, v in REPORTS.items()]


@router.get("/reports/{key}")
def run_report(key: str, date_from: date | None = None, date_to: date | None = None, unit_id: int | None = None,
               kind: str | None = None, fields: str | None = None, format: str = Query("json", pattern="^(json|xlsx)$"),
               page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=1000),
               db: Session = Depends(get_db), user: User = Depends(require("reports", "view"))):
    if format == "xlsx" and not user.can("reports", "export"):
        raise HTTPException(403, "គ្មានសិទ្ធិនាំចេញ")
    # the Excel file has every row (page=None); the screen and print get one page
    rep = build_report(db, user, key, date_from, date_to, unit_id, kind, fields,
                       page=page if format == "json" else None, size=size)
    if format == "json":
        return rep
    # write-only: rows go straight to the file (the soldier list's rows are streamed from the database)
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(key[:30])
    ncol = len(rep["columns"])
    for i in range(ncol):
        ws.column_dimensions[get_column_letter(i + 1)].width = 20

    def styled(value, **font):
        c = WriteOnlyCell(ws, value=value)
        c.font = Font(bold=True, **font)
        return c

    title = styled(rep["title"], size=14)
    title.alignment = Alignment(horizontal="center")
    ws.append([title])
    ws.merged_cells.add(f"A1:{get_column_letter(ncol)}1")
    ws.append([f"ចាប់ពី {rep['date_from']} ដល់ {rep['date_to']}"])
    ws.append([styled(c["label"]) for c in rep["columns"]])
    for r in rep["rows"]:
        ws.append([r.get(c["key"], "") for c in rep["columns"]])
    if rep["totals"]:
        ws.append([styled(rep["totals"].get(c["key"], "")) for c in rep["columns"]])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={key}.xlsx"})
