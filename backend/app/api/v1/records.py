"""Training, discipline, awards, retirement/category-2, separation and strength movements."""

import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, delete, extract, not_, or_, select
from sqlalchemy.orm import Session

from app.api.crud import crud_router
from app.core.database import get_db
from app.core.deps import require
from app.models import (
    AwardRecord,
    Category2Record,
    Country,
    DisciplineRecord,
    MilitaryCard,
    RetirementRecord,
    SeparationRecord,
    Soldier,
    SoldierHistory,
    StrengthMovement,
    TrainingCourse,
    TrainingParticipant,
    Unit,
    User,
)
from app.schemas import (
    IN_REASONS,
    OUT_REASONS,
    AwardIn,
    Category2In,
    DisciplineIn,
    MilitaryCardIn,
    RankPositionCheckIn,
    RankPositionIn,
    RetirementBulkCheckIn,
    RetirementBulkIn,
    RetirementIn,
    SeparationIn,
    StrengthBulkCheckIn,
    StrengthBulkIn,
    StrengthIn,
    TrainingCourseIn,
)
from app.services.cards import CARD_REASONS, CARD_STATUS, OUTDATED, card_status, outdated_card_clause, outdated_reasons
from app.services.common import audit, check_unit_in_scope, scope_unit_ids, to_dict, unit_subtree_ids
from app.services.soldier import (
    add_history,
    add_movement,
    format_military_id,
    is_inactive,
    is_separated,
    status_id_by_code,
    unit_chain,
)

router = APIRouter()


def soldier_brief(s: Soldier | None) -> dict:
    if not s:
        return {}
    return {
        "soldier_name": s.name_kh, "military_id": s.military_id, "soldier_gender": s.gender,
        "rank_name": s.rank.name_kh if s.rank else None, "unit_name": s.unit.name_kh if s.unit else None,
        "position_name": s.position.name_kh if s.position else None,
    }


def scoped(model):
    """Restrict soldier-linked records to the user's unit scope."""

    def base(stmt, db: Session, user: User):
        ids = scope_unit_ids(db, user)
        if ids is not None:
            stmt = stmt.where(model.soldier_id.in_(select(Soldier.id).where(Soldier.current_unit_id.in_(ids))))
        return stmt

    return base


def _check_soldier(db: Session, user: User, soldier_id: int) -> Soldier:
    s = db.get(Soldier, soldier_id)
    if not s or s.deleted_at:
        raise HTTPException(400, "រកមិនឃើញយោធិន")
    ids = scope_unit_ids(db, user)
    if ids is not None and s.current_unit_id not in ids:
        raise HTTPException(403, "យោធិននេះនៅក្រៅសិទ្ធិរបស់អ្នក")
    return s


def _check_period(data: dict) -> None:
    if data.get("start_date") and data.get("end_date") and data["end_date"] < data["start_date"]:
        raise HTTPException(400, "ថ្ងៃបញ្ចប់ត្រូវនៅក្រោយថ្ងៃចាប់ផ្ដើម")


def _soldier_hook(db, user, obj, data, is_new):
    s = _check_soldier(db, user, data["soldier_id"])
    if is_new and is_separated(db, s):  # the record of a separated soldier is kept as it was
        raise HTTPException(400, "យោធិននេះបានចេញពីជួររួចហើយ")
    if not is_new and data["soldier_id"] != obj.soldier_id:
        raise HTTPException(400, "មិនអាចប្ដូរយោធិនក្នុងកំណត់ត្រានេះបានទេ")


def by_year(col):
    """`year` filter on a date column (ឆ្នាំទទួល / ឆ្នាំ...)."""
    return lambda stmt, v: stmt.where(extract("year", col) == int(v)) if str(v).isdigit() else stmt


def contains(col):
    return lambda stmt, v: stmt.where(col.ilike(f"%{v}%"))


def _discipline_hook(db, user, obj, data, is_new):
    _soldier_hook(db, user, obj, data, is_new)
    _check_period(data)


# ---------------- training ----------------

COURSE_STATUS = {"upcoming": "មិនទាន់ចាប់ផ្ដើម", "ongoing": "កំពុងរៀន", "finished": "បានបញ្ចប់"}
PARTICIPANT_STATUS = {"studying": "កំពុងរៀន", "completed": "បញ្ចប់", "dropped": "ឈប់"}


def course_status(c: TrainingCourse) -> str | None:
    today = date.today()
    if c.start_date and c.start_date > today:
        return "upcoming"
    if c.end_date and c.end_date < today:
        return "finished"
    return "ongoing" if c.start_date else None


def _course_status_filter(stmt, v):
    today = date.today()
    started = or_(TrainingCourse.start_date.is_(None), TrainingCourse.start_date <= today)
    return stmt.where({
        "upcoming": TrainingCourse.start_date > today,
        "finished": TrainingCourse.end_date < today,
        "ongoing": and_(TrainingCourse.start_date.is_not(None), started,
                        or_(TrainingCourse.end_date.is_(None), TrainingCourse.end_date >= today)),
    }.get(v, TrainingCourse.id.is_not(None)))


# the country rows that are Cambodia (none in some data: then every course with a country is abroad)
CAMBODIA_IDS = select(Country.id).where(or_(Country.name_en == "Cambodia", Country.name_kh.contains("កម្ពុជា")))


def course_abroad():
    """ក្នុង/ក្រៅប្រទេស: a course with a country other than Cambodia is abroad (no country: in Cambodia)."""
    return and_(TrainingCourse.country_id.is_not(None), TrainingCourse.country_id.not_in(CAMBODIA_IDS))


def _abroad_filter(stmt, v):
    return stmt.where(course_abroad() if v == "yes" else not_(course_abroad()))


def _participant_status_filter(stmt, v):
    return stmt.where(TrainingCourse.id.in_(select(TrainingParticipant.course_id).where(TrainingParticipant.status == v)))


def course_out(c: TrainingCourse) -> dict:
    st = course_status(c)
    return {**to_dict(c), "participant_count": len(c.participants), "status": st,
            "status_name": COURSE_STATUS.get(st),
            "participants": [{**to_dict(p), **soldier_brief(p.soldier)} for p in c.participants]}


def _course_before(db, user, obj, data, is_new):
    parts, seen = [], set()
    for p in data.pop("participants", []):
        if p["soldier_id"] in seen:
            continue
        seen.add(p["soldier_id"])
        _check_soldier(db, user, p["soldier_id"])
        parts.append(TrainingParticipant(**p))
    data["participants"] = parts
    _check_period(data)


router.include_router(crud_router(
    prefix="/training/courses", model=TrainingCourse, module="training", schema=TrainingCourseIn,
    search_fields=(TrainingCourse.name, TrainingCourse.institution),
    filter_fields={"course_type": TrainingCourse.course_type, "level": TrainingCourse.level,
                   "specialty_id": TrainingCourse.specialty_id, "sector": TrainingCourse.sector,
                   "country_id": TrainingCourse.country_id,
                   "date_from": TrainingCourse.start_date, "date_to": TrainingCourse.start_date},
    custom_filters={"status": _course_status_filter, "abroad": _abroad_filter,
                    "participant_status": _participant_status_filter, "institution": contains(TrainingCourse.institution),
                    "end_from": lambda st, v: st.where(TrainingCourse.end_date >= v),
                    "end_to": lambda st, v: st.where(TrainingCourse.end_date <= v)},
    order_by=(TrainingCourse.start_date.desc(), TrainingCourse.id.desc()),
    serialize=course_out, before_save=_course_before, tags=["training"],
))


# ---------------- discipline & awards ----------------

DISCIPLINE_STATUS = {"active": "កំពុងអនុវត្ត", "expired": "ផុតកំណត់", "cancelled": "លុបចោល"}


def discipline_status(r: DisciplineRecord) -> str:
    if r.cancelled:
        return "cancelled"
    return "expired" if r.end_date and r.end_date < date.today() else "active"


def _discipline_status_filter(stmt, v):
    today = date.today()
    live = DisciplineRecord.cancelled.is_(False)
    return stmt.where({
        "cancelled": DisciplineRecord.cancelled.is_(True),
        "expired": and_(live, DisciplineRecord.end_date < today),
        "active": and_(live, or_(DisciplineRecord.end_date.is_(None), DisciplineRecord.end_date >= today)),
    }.get(v, DisciplineRecord.id.is_not(None)))


def discipline_out(r: DisciplineRecord) -> dict:
    st = discipline_status(r)
    return {**to_dict(r), **soldier_brief(r.soldier), "status": st, "status_name": DISCIPLINE_STATUS[st],
            "discipline_type_name": r.discipline_type.name_kh if r.discipline_type else None}


def award_out(r: AwardRecord) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier), "award_type_name": r.award_type.name_kh if r.award_type else None}


router.include_router(crud_router(
    prefix="/discipline", model=DisciplineRecord, module="discipline", schema=DisciplineIn,
    search_fields=(DisciplineRecord.reason, DisciplineRecord.decision_no),
    filter_fields={"soldier_id": DisciplineRecord.soldier_id, "discipline_type_id": DisciplineRecord.discipline_type_id,
                   "date_from": DisciplineRecord.decision_date, "date_to": DisciplineRecord.decision_date},
    custom_filters={"status": _discipline_status_filter, "year": by_year(DisciplineRecord.decision_date),
                    "level": contains(DisciplineRecord.level), "decided_by": contains(DisciplineRecord.decided_by)},
    order_by=(DisciplineRecord.decision_date.desc(), DisciplineRecord.id.desc()),
    serialize=discipline_out, base_query=scoped(DisciplineRecord), before_save=_discipline_hook,
))
router.include_router(crud_router(
    prefix="/awards", model=AwardRecord, module="awards", schema=AwardIn,
    search_fields=(AwardRecord.reason, AwardRecord.decision_no),
    filter_fields={"soldier_id": AwardRecord.soldier_id, "award_type_id": AwardRecord.award_type_id,
                   "date_from": AwardRecord.decision_date, "date_to": AwardRecord.decision_date},
    custom_filters={"year": by_year(AwardRecord.decision_date), "level": contains(AwardRecord.level),
                    "awarded_by": contains(AwardRecord.awarded_by)},
    order_by=(AwardRecord.decision_date.desc(), AwardRecord.id.desc()),
    serialize=award_out, base_query=scoped(AwardRecord), before_save=_soldier_hook,
))


# ---------------- retirement / category 2 / separation ----------------

def _leave_before(db, user, obj, data, is_new):
    _soldier_hook(db, user, obj, data, is_new)
    if is_new and is_inactive(db, db.get(Soldier, data["soldier_id"])):
        # a second leave record would count the soldier out of the strength twice
        raise HTTPException(400, "យោធិននេះបានចូលនិវត្តន៍ ឬចេញពីជួររួចហើយ")


def _leave_after_save(table: str, status_code_fn, reason_fn):
    def hook(db: Session, user: User, obj, is_new: bool):
        s = db.get(Soldier, obj.soldier_id)
        if is_new:
            obj.previous_status_id, obj.previous_unit_id = s.status_id, s.current_unit_id
        s.status_id = status_id_by_code(db, status_code_fn(obj))
        db.execute(delete(StrengthMovement).where(StrengthMovement.source_table == table,
                                                  StrengthMovement.source_id == obj.id))
        add_movement(db, s.id, obj.previous_unit_id, "out", reason_fn(obj), obj.effective_date, table, obj.id)

    return hook


RETIRE_MOVE_NOTE = "ផ្លាស់អង្គភាព ពេលចូលនិវត្តន៍"


def _leave_after_delete(table: str):
    def hook(db: Session, user: User, obj):
        s = db.get(Soldier, obj.soldier_id)
        s.status_id = obj.previous_status_id or status_id_by_code(db, "active")
        db.execute(delete(StrengthMovement).where(StrengthMovement.source_table == table,
                                                  StrengthMovement.source_id == obj.id))
        # the move to another unit made on leaving (ផ្លាស់អង្គភាព ពេលចូលនិវត្តន៍) goes with the record: the soldier is
        # back in the unit they left, unless their unit changed again since (the move is then their latest history)
        last = db.scalar(select(SoldierHistory).where(SoldierHistory.soldier_id == s.id)
                         .order_by(SoldierHistory.id.desc()).limit(1))
        if obj.previous_unit_id and last and last.note == RETIRE_MOVE_NOTE \
                and (last.old_unit_id, last.new_unit_id) == (obj.previous_unit_id, s.current_unit_id):
            s.current_unit_id = obj.previous_unit_id
            s.unit_transfer_date = getattr(obj, "previous_unit_date", None) or s.unit_transfer_date
            db.delete(last)

    return hook


RETIREMENT_TYPES = {"pension": "សោធននិវត្តន៍ (គ្រប់អាយុ)", "voluntary": "ស្ម័គ្រចិត្តចូលនិវត្តន៍",
                    "disability": "ពិការ", "death": "ស្លាប់"}
CASE_STATUS = {"submitted": "ដាក់ឯកសារ", "processing": "កំពុងដំណើរការ", "done": "រួចរាល់"}
# the soldier's status once the record is saved
RETIREMENT_SOLDIER_STATUS = {"death": "deceased"}
CATEGORY2_TYPES = {"fallen": "ពលី", "fallen_dead": "ពលី-មរណ", "disabled": "ពិការ"}


def retirement_out(r: RetirementRecord) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier), "type_name": RETIREMENT_TYPES.get(r.type, r.type),
            "case_status_name": CASE_STATUS.get(r.case_status)}


def category2_out(r: Category2Record) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier), "type_name": CATEGORY2_TYPES.get(r.type, "មិនទាន់កំណត់")}


def separation_out(r: SeparationRecord) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier), "reason_name": r.reason.name_kh if r.reason else None}


_retirement_after_save = _leave_after_save(
    "retirement_records", lambda o: RETIREMENT_SOLDIER_STATUS.get(o.type, "retired"), lambda o: "retire")


@router.post("/retirements/bulk/check", tags=["retirement"])
def check_bulk_retirement(payload: RetirementBulkCheckIn, db: Session = Depends(get_db),
                          user: User = Depends(require("retirement", "create"))):
    """The pasted military IDs, each with its soldier and whether it can be retired (nothing is written)."""
    mids = list(dict.fromkeys(format_military_id(x) for x in re.split(r"[\s,;]+", payload.military_ids) if x))[:1000]
    found = {s.military_id: s for s in db.scalars(select(Soldier).where(
        Soldier.military_id.in_(mids), Soldier.deleted_at.is_(None)))} if mids else {}
    scope = scope_unit_ids(db, user)
    rows = []
    for mid in mids:
        s = found.get(mid)
        if s is None:
            rows.append({"military_id": mid, "status": "not_found", "message": "រកមិនឃើញអត្តលេខនេះ"})
            continue
        row = {"military_id": mid, "soldier_id": s.id, **soldier_brief(s), "unit_id": s.current_unit_id}
        if scope is not None and s.current_unit_id not in scope:
            rows.append({"military_id": mid, "status": "out_of_scope", "message": "នៅក្រៅសិទ្ធិរបស់អ្នក"})
        elif is_inactive(db, s):
            rows.append({**row, "status": "inactive", "message": "បានចូលនិវត្តន៍ ឬចេញពីជួររួចហើយ"})
        else:
            rows.append({**row, "status": "ok", "message": None})
    return rows


@router.post("/retirements/bulk", status_code=201, tags=["retirement"])
def create_bulk_retirement(payload: RetirementBulkIn, request: Request, db: Session = Depends(get_db),
                           user: User = Depends(require("retirement", "create"))):
    """One retirement record per soldier (all or none); with unit_id every soldier is also moved to that unit,
    which shows in the soldier list and in each soldier's history (no strength movement: they have left)."""
    from app.api.v1.soldiers import record_edit  # local import: soldiers imports a lot

    if payload.unit_id:
        check_unit_in_scope(db, user, payload.unit_id)
    data = payload.model_dump(exclude={"soldier_ids", "unit_id"})
    created = []
    for soldier_id in dict.fromkeys(payload.soldier_ids):
        values = {**data, "soldier_id": soldier_id}
        obj = RetirementRecord()
        try:
            _leave_before(db, user, obj, values, True)
        except HTTPException as e:
            s = db.get(Soldier, soldier_id)
            mid = s.military_id if s else soldier_id
            db.rollback()  # all or none: the soldiers already done in this batch are not kept
            raise HTTPException(e.status_code, f"{mid}: {e.detail}")
        for k, v in values.items():
            setattr(obj, k, v)
        obj.created_by = user.id
        db.add(obj)
        db.flush()
        _retirement_after_save(db, user, obj, True)  # the "out" movement is from the unit the soldier left
        s = obj.soldier
        if payload.unit_id and payload.unit_id != s.current_unit_id:
            old = (s.current_rank_id, s.current_position_id, s.current_unit_id)
            old_unit_date = obj.previous_unit_date = s.unit_transfer_date
            s.current_unit_id, s.unit_transfer_date, s.updated_by = payload.unit_id, payload.effective_date, user.id
            record_edit(db, s, old, old_unit_date, RETIRE_MOVE_NOTE)
        audit(db, user, "create", obj, request=request)
        created.append(obj)
    db.commit()
    return {"created": len(created), "items": [retirement_out(o) for o in created]}


router.include_router(crud_router(
    prefix="/retirements", model=RetirementRecord, module="retirement", schema=RetirementIn,
    search_fields=(RetirementRecord.decision_no, RetirementRecord.notes),
    filter_fields={"type": RetirementRecord.type, "soldier_id": RetirementRecord.soldier_id,
                   "case_status": RetirementRecord.case_status,
                   "date_from": RetirementRecord.effective_date, "date_to": RetirementRecord.effective_date},
    custom_filters={"year": by_year(RetirementRecord.effective_date)},
    order_by=(RetirementRecord.effective_date.desc(), RetirementRecord.id.desc()),
    serialize=retirement_out, base_query=scoped(RetirementRecord), before_save=_leave_before,
    after_save=_retirement_after_save, after_delete=_leave_after_delete("retirement_records"), tags=["retirement"],
))
router.include_router(crud_router(
    prefix="/category2", model=Category2Record, module="category2", schema=Category2In,
    search_fields=(Category2Record.decision_no, Category2Record.notes),
    filter_fields={"type": Category2Record.type, "soldier_id": Category2Record.soldier_id,
                   "date_from": Category2Record.effective_date, "date_to": Category2Record.effective_date},
    custom_filters={"year": by_year(Category2Record.effective_date)},
    order_by=(Category2Record.effective_date.desc(), Category2Record.id.desc()),
    serialize=category2_out, base_query=scoped(Category2Record), before_save=_leave_before,
    after_save=_leave_after_save("category2_records", lambda o: "category2", lambda o: "category2"),
    after_delete=_leave_after_delete("category2_records"), tags=["category2"],
))
router.include_router(crud_router(
    prefix="/separations", model=SeparationRecord, module="separation", schema=SeparationIn,
    search_fields=(SeparationRecord.decision_no, SeparationRecord.notes),
    filter_fields={"reason_id": SeparationRecord.reason_id, "soldier_id": SeparationRecord.soldier_id,
                   "date_from": SeparationRecord.effective_date, "date_to": SeparationRecord.effective_date},
    order_by=(SeparationRecord.effective_date.desc(), SeparationRecord.id.desc()),
    serialize=separation_out, base_query=scoped(SeparationRecord), before_save=_leave_before,
    after_save=_leave_after_save("separation_records", lambda o: "separated", lambda o: "separate"),
    after_delete=_leave_after_delete("separation_records"), tags=["separation"],
))


# ---------------- military ID cards (ការងារអត្តសញ្ញាណប័ណ្ណយោធិន) ----------------

def card_out(c: MilitaryCard) -> dict:
    st = card_status(c)
    days = (c.expiry_date - date.today()).days if c.expiry_date else None
    outdated = outdated_reasons(c)
    return {**to_dict(c), **soldier_brief(c.soldier), "status": st, "stored_status": c.status,
            "status_name": CARD_STATUS[st], "days_left": days, "reason_name": CARD_REASONS.get(c.reason or "", ""),
            "outdated": outdated, "outdated_text": ", ".join(OUTDATED[k] for k in outdated)}


def _card_status_filter(stmt, v):
    today = date.today()
    if v == "expired":
        return stmt.where(MilitaryCard.status == "issued", MilitaryCard.expiry_date < today)
    if v == "issued":
        return stmt.where(MilitaryCard.status == "issued",
                          or_(MilitaryCard.expiry_date.is_(None), MilitaryCard.expiry_date >= today))
    return stmt.where(MilitaryCard.status == v)


def _card_expiring_filter(stmt, v):
    """ផុតកំណត់ក្នុង ៣០/៦០/៩០ ថ្ងៃ: issued cards still valid today that expire within N days."""
    if not str(v).isdigit():
        return stmt
    today = date.today()
    return stmt.where(MilitaryCard.status == "issued",
                      MilitaryCard.expiry_date.between(today, today + timedelta(days=int(v))))


def _card_outdated_filter(stmt, v):
    """ត្រូវធ្វើប័ណ្ណថ្មី: rank / position / any (yes) change after the card was issued."""
    return stmt.where(outdated_card_clause(v if v in OUTDATED else None))


def _card_before(db, user, obj, data, is_new):
    _soldier_hook(db, user, obj, data, is_new)
    if data.get("status") == "expired":  # computed, never stored
        data["status"] = "issued"
    if data.get("issue_date") and data.get("expiry_date") and data["expiry_date"] < data["issue_date"]:
        raise HTTPException(400, "ថ្ងៃផុតកំណត់ត្រូវនៅក្រោយថ្ងៃចេញ")


router.include_router(crud_router(
    prefix="/military-cards", model=MilitaryCard, module="id_cards", schema=MilitaryCardIn,
    search_fields=(MilitaryCard.card_no, MilitaryCard.notes),
    filter_fields={"soldier_id": MilitaryCard.soldier_id,
                   "date_from": MilitaryCard.issue_date, "date_to": MilitaryCard.issue_date},
    custom_filters={"status": _card_status_filter, "expiring_within": _card_expiring_filter,
                    "outdated": _card_outdated_filter, "reason": lambda stmt, v: stmt.where(MilitaryCard.reason == v)},
    order_by=(MilitaryCard.issue_date.desc(), MilitaryCard.id.desc()),
    serialize=card_out, base_query=scoped(MilitaryCard), before_save=_card_before, tags=["id cards"],
))


# ---------------- strength movements (ការងារកើនថយ) ----------------

MOVEMENT_REASONS = {
    "recruit": "ចូលបម្រើថ្មី", "transfer_in": "ផ្លាស់មកពីអង្គភាពផ្សេង", "reinstate": "ចូលបម្រើវិញ",
    "transfer_out": "ផ្លាស់ទៅអង្គភាពផ្សេង", "retire": "សោធននិវត្តន៍", "category2": "យោធិនប្រភេទ២",
    "separate": "ចេញពីជួរ", "other": "ផ្សេងៗ",
    # ការផ្លាស់ប្ដូរស្ថាប័នកងឯកភាព: between units of the same ស្ថាប័នកងឯកភាព / joining from outside it
    "internal": "ផ្លាស់ប្ដូរផ្ទៃក្នុង", "outside_in": "កើនក្រៅស្ថាប័នកងឯកភាព",
}


def movement_out(m: StrengthMovement) -> dict:
    return {**to_dict(m), **soldier_brief(m.soldier), "unit_name": m.unit.name_kh if m.unit else None,
            "reason_name": MOVEMENT_REASONS.get(m.reason, m.reason)}


def _movement_scope(stmt, db, user):
    # movements of deleted soldiers no longer count
    stmt = stmt.where(StrengthMovement.soldier_id.in_(select(Soldier.id).where(Soldier.deleted_at.is_(None))))
    ids = scope_unit_ids(db, user)
    return stmt.where(StrengthMovement.unit_id.in_(ids)) if ids is not None else stmt


def _movement_before(db, user, obj, data, is_new):
    _check_soldier(db, user, data["soldier_id"])
    if not is_new:
        _movement_not_auto(db, user, obj)
    if data["movement_date"] > date.today():
        raise HTTPException(400, "កាលបរិច្ឆេទមិនអាចនៅថ្ងៃអនាគត")


def _movement_not_auto(db, user, obj):
    # rows written by soldiers/decisions/retirements are kept in sync by those modules
    if obj.source_table:
        raise HTTPException(400, "កំណត់ត្រានេះបង្កើតដោយស្វ័យប្រវត្តិ មិនអាចកែប្រែ ឬលុបបានទេ")


router.include_router(crud_router(
    prefix="/strength-movements", model=StrengthMovement, module="strength", schema=StrengthIn,
    search_fields=(StrengthMovement.note,),
    filter_fields={"direction": StrengthMovement.direction, "reason": StrengthMovement.reason,
                   "unit_id": StrengthMovement.unit_id, "soldier_id": StrengthMovement.soldier_id,
                   "date_from": StrengthMovement.movement_date, "date_to": StrengthMovement.movement_date},
    order_by=(StrengthMovement.movement_date.desc(), StrengthMovement.id.desc()),
    serialize=movement_out, base_query=_movement_scope, before_save=_movement_before,
    before_delete=_movement_not_auto, tags=["strength"],
))


# ---------------- ការផ្លាស់ប្ដូរស្ថាប័នកងឯកភាព: many soldiers at once ----------------
# កើន (in): every soldier entered joins the chosen ស្ថាប័នកងឯកភាព/អង្គភាព — the soldier's unit changes, with a history
# row and the strength movements (out of the old unit, into the new one). ថយ (out): a movement out of the chosen
# ស្ថាប័នកងឯកភាព is recorded for each soldier (the profile does not change; to move a soldier, use កើន at the new one).


def _institution_id(db: Session, unit_id: int | None) -> int | None:
    chain = unit_chain(db.get(Unit, unit_id)) if unit_id else []
    return chain[0].id if chain else None


def _unit_name(db: Session, unit_id: int | None) -> str | None:
    u = db.get(Unit, unit_id) if unit_id else None
    return u.name_kh if u else None


def _bulk_target(db: Session, user: User, direction: str, reason: str | None, unit_id: int | None) -> None:
    if reason is not None and reason not in (IN_REASONS if direction == "in" else OUT_REASONS):
        raise HTTPException(400, "មូលហេតុមិនត្រឹមត្រូវ")
    if unit_id is not None:
        u = db.get(Unit, unit_id)
        if not u or not u.active:
            raise HTTPException(400, "ស្ថាប័នកងឯកភាព/អង្គភាពមិនត្រឹមត្រូវ")
        check_unit_in_scope(db, user, unit_id)


def _bulk_problems(db: Session, user: User, soldiers: list[Soldier], direction: str, reason: str | None,
                   unit_id: int | None) -> list[tuple[list[str], list[str]]]:
    """(errors, warnings) per soldier. Errors stop saving; warnings (staffing table...) are only shown."""
    from app.api.v1.decisions import staffing_issues  # decisions -> ... -> records

    scope = scope_unit_ids(db, user)
    target = _institution_id(db, unit_id)
    inside = set(unit_subtree_ids(db, unit_id)) if unit_id else set()
    out, moving = [], []
    for s in soldiers:
        errors, warnings = [], []
        if scope is not None and s.current_unit_id not in scope:
            errors.append("នៅក្រៅសិទ្ធិរបស់អ្នក")
        elif is_inactive(db, s):
            errors.append("បានចូលនិវត្តន៍ ឬចេញពីជួររួចហើយ")
        elif unit_id and reason:
            current = _institution_id(db, s.current_unit_id)
            if direction == "out":
                if s.current_unit_id not in inside:
                    errors.append(f"មិនស្ថិតនៅក្នុង {_unit_name(db, unit_id)} (បច្ចុប្បន្ននៅ {s.unit.name_kh if s.unit else '-'})")
            elif s.current_unit_id == unit_id:
                errors.append("ស្ថិតនៅអង្គភាពនេះរួចហើយ")
            elif reason == "internal" and current != target:
                errors.append(f"ផ្លាស់ប្ដូរផ្ទៃក្នុង ត្រូវតែនៅក្នុងស្ថាប័នកងឯកភាពតែមួយ (បច្ចុប្បន្ននៅ {_unit_name(db, current) or '-'})")
            elif reason == "outside_in" and current and current == target:
                errors.append("នៅក្នុងស្ថាប័នកងឯកភាពនេះរួចហើយ — សូមជ្រើស «ផ្លាស់ប្ដូរផ្ទៃក្នុង»")
            elif reason == "transfer_in" and current and current == target:
                warnings.append("ផ្លាស់ក្នុងស្ថាប័នកងឯកភាពតែមួយ — គួរជ្រើស «ផ្លាស់ប្ដូរផ្ទៃក្នុង»")
        out.append((errors, warnings))
        if direction == "in" and unit_id and not errors:
            moving.append((len(out) - 1, s))
    # the staffing table (ក្របខណ្ឌ) of the new unit, all the soldiers of this entry counted together
    label = "ក្របខណ្ឌ"
    changes = [(s, None, None, unit_id, label) for _, s in moving]
    for (n, _), problems in zip(moving, staffing_issues(db, "transfer", changes), strict=True):
        out[n][1].extend(p.removeprefix(f"{label}: ") for p in problems)
    return out


@router.post("/strength-movements/bulk/check", tags=["strength"])
def check_bulk_movement(payload: StrengthBulkCheckIn, db: Session = Depends(get_db),
                        user: User = Depends(require("strength", "create"))):
    """The pasted military IDs, each with its soldier and what saving would do or refuse (nothing is written)."""
    _bulk_target(db, user, payload.direction, payload.reason, payload.unit_id)
    mids = list(dict.fromkeys(format_military_id(x) for x in re.split(r"[\s,;]+", payload.military_ids) if x))[:1000]
    found = {s.military_id: s for s in db.scalars(select(Soldier).where(
        Soldier.military_id.in_(mids), Soldier.deleted_at.is_(None)))} if mids else {}
    soldiers = [found[m] for m in mids if m in found]
    scope = scope_unit_ids(db, user)
    checked = dict(zip((s.id for s in soldiers),
                       _bulk_problems(db, user, soldiers, payload.direction, payload.reason, payload.unit_id), strict=True))
    rows = []
    for mid in mids:
        s = found.get(mid)
        if s is None:
            rows.append({"military_id": mid, "status": "not_found", "errors": ["រកមិនឃើញអត្តលេខនេះ"], "warnings": []})
            continue
        errors, warnings = checked[s.id]
        if scope is not None and s.current_unit_id not in scope:  # not even the name of a soldier outside one's units
            rows.append({"military_id": mid, "status": "error", "errors": errors, "warnings": []})
            continue
        rows.append({"military_id": mid, "soldier_id": s.id, **soldier_brief(s), "unit_id": s.current_unit_id,
                     "institution_name": _unit_name(db, _institution_id(db, s.current_unit_id)),
                     "status": "error" if errors else "warning" if warnings else "ok",
                     "errors": errors, "warnings": warnings})
    return rows


@router.post("/strength-movements/bulk", status_code=201, tags=["strength"])
def create_bulk_movement(payload: StrengthBulkIn, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(require("strength", "create"))):
    """All or none: refused while any soldier has an error (the check above shows them)."""
    _bulk_target(db, user, payload.direction, payload.reason, payload.unit_id)
    if payload.movement_date > date.today():
        raise HTTPException(400, "កាលបរិច្ឆេទមិនអាចនៅថ្ងៃអនាគត")
    soldiers = []
    for sid in dict.fromkeys(payload.soldier_ids):
        s = db.get(Soldier, sid)
        if not s or s.deleted_at:
            raise HTTPException(400, f"រកមិនឃើញយោធិន id={sid}")
        soldiers.append(s)
    problems = _bulk_problems(db, user, soldiers, payload.direction, payload.reason, payload.unit_id)
    refused = [f"{s.military_id} {s.name_kh}: {'; '.join(e)}" for s, (e, _) in zip(soldiers, problems, strict=True) if e]
    if refused:
        raise HTTPException(400, "មិនអាចរក្សាទុកបាន៖\n" + "\n".join(refused))
    when, reason, note = payload.movement_date, payload.reason, payload.note
    for s in soldiers:
        if payload.direction == "out":  # a record only: editable on the page like any manual movement
            m = StrengthMovement(soldier_id=s.id, unit_id=s.current_unit_id, direction="out", reason=reason,
                                 movement_date=when, note=note)
            db.add(m)
            db.flush()
            audit(db, user, "create", m, request=request)
            continue
        old = s.current_unit_id
        if old:
            add_movement(db, s.id, old, "out", "internal" if reason == "internal" else "transfer_out", when,
                         "soldiers", s.id, note=note)
        add_movement(db, s.id, payload.unit_id, "in", reason, when, "soldiers", s.id, note=note)
        add_history(db, s, "transfer", when, old_unit=old, new_unit=payload.unit_id,
                    note=" — ".join(x for x in (MOVEMENT_REASONS[reason], note) if x))
        s.from_unit_text = s.unit.name_kh if s.unit else s.from_unit_text
        s.current_unit_id, s.unit_transfer_date, s.updated_by = payload.unit_id, when, user.id
        audit(db, user, "update", s, request=request)
    db.commit()
    return {"saved": len(soldiers)}


# ---------------- Update ស័ក្តិ និងមុខតំណែង: many soldiers at once ----------------
# The rank, position and/or unit of the soldiers entered (and the date of each) are set as given, from an incoming
# document (ឯកសារចូល), outside of the decision workflow: a history row "update" per soldier whose rank, position or
# unit changes; a unit change also moves the soldier between unit strengths (out of the old unit, into the new one).
# Each soldier's values start as the soldier's own; a value left empty keeps the soldier's.

RP_FIELDS = ("rank_id", "rank_date", "position_id", "position_date", "unit_id", "unit_date")


def _rp_current(s: Soldier) -> dict:
    return {"rank_id": s.current_rank_id, "rank_date": s.rank_date, "position_id": s.current_position_id,
            "position_date": s.position_date, "unit_id": s.current_unit_id, "unit_date": s.unit_transfer_date}


def _rp_values(s: Soldier, values) -> dict:
    """The values the soldier would have (empty = the soldier's own)."""
    current = _rp_current(s)
    return {k: getattr(values, k, None) or current[k] for k in RP_FIELDS}


def _rp_changes(s: Soldier, v: dict) -> list[str]:
    current = _rp_current(s)
    return [k for k in RP_FIELDS if v[k] != current[k]]


def _rp_problems(db: Session, user: User, pairs: list[tuple[Soldier, dict]]) -> list[tuple[list[str], list[str]]]:
    """(errors, warnings) per soldier. Errors stop saving; warnings (a lower rank, the staffing table...) are shown."""
    from app.api.v1.decisions import IN_PROGRESS, staffing_issues  # decisions -> ... -> records
    from app.models import Decision, DecisionItem, Position, Rank

    scope = scope_unit_ids(db, user)
    today = date.today()
    out, changing = [], []
    for s, v in pairs:
        errors, warnings = [], []
        rank = db.get(Rank, v["rank_id"]) if v["rank_id"] else None
        position = db.get(Position, v["position_id"]) if v["position_id"] else None
        unit = db.get(Unit, v["unit_id"]) if v["unit_id"] else None
        moves = v["unit_id"] != s.current_unit_id
        if scope is not None and s.current_unit_id not in scope:
            errors.append("នៅក្រៅសិទ្ធិរបស់អ្នក")
        elif is_inactive(db, s):
            errors.append("បានចូលនិវត្តន៍ ឬចេញពីជួររួចហើយ")
        else:
            if v["rank_id"] and not rank:
                errors.append("ឋានន្តរស័ក្តិមិនត្រឹមត្រូវ")
            if v["position_id"] and (not position or (not position.active and v["position_id"] != s.current_position_id)):
                errors.append("មុខតំណែងមិនត្រឹមត្រូវ")
            if moves and (not unit or not unit.active):
                errors.append("អង្គភាពមិនត្រឹមត្រូវ")
            elif moves and scope is not None and v["unit_id"] not in scope:
                errors.append("អង្គភាពថ្មីនៅក្រៅសិទ្ធិរបស់អ្នក")
            for k, label in (("rank_date", "ថ្ងៃឡើងស័ក្តិ"), ("position_date", "ថ្ងៃមុខតំណែង"),
                             ("unit_date", "ថ្ងៃផ្លាស់អង្គភាព")):
                if v[k] and v[k] > today:
                    errors.append(f"{label} មិនអាចនៅថ្ងៃអនាគត")
                elif v[k] and s.date_of_birth and v[k] <= s.date_of_birth:
                    errors.append(f"{label} មុនថ្ងៃកំណើត")
                elif v[k] and s.enlistment_date and v[k] < s.enlistment_date:
                    warnings.append(f"{label} មុនថ្ងៃចូលបម្រើទ័ព")
            if rank and s.rank and v["rank_id"] != s.current_rank_id and rank.sort_order < s.rank.sort_order:
                warnings.append(f"ឋានន្តរស័ក្តិទាបជាងបច្ចុប្បន្ន ({s.rank.name_kh})")
            if v["rank_id"] != s.current_rank_id and not v["rank_date"]:
                warnings.append("ខ្វះថ្ងៃឡើងស័ក្តិ")
            if v["position_id"] != s.current_position_id and not v["position_date"]:
                warnings.append("ខ្វះថ្ងៃមុខតំណែង")
            if moves and v["unit_date"] == s.unit_transfer_date:
                warnings.append("ខ្វះថ្ងៃផ្លាស់អង្គភាព (នឹងប្រើថ្ងៃនេះ)")
            if db.scalar(select(Decision.id).join(DecisionItem).where(
                    DecisionItem.soldier_id == s.id, Decision.deleted_at.is_(None),
                    or_(Decision.status.in_(("draft", *IN_PROGRESS)),
                        and_(Decision.status == "approved", Decision.published_at.is_(None)))).limit(1)):
                warnings.append("មាននៅក្នុងសេចក្ដីសម្រេចដែលកំពុងដំណើរការ")
        out.append((errors, warnings))
        new_rank = v["rank_id"] if v["rank_id"] != s.current_rank_id else None
        new_position = v["position_id"] if v["position_id"] != s.current_position_id else None
        new_unit = v["unit_id"] if moves else None
        if not errors and (new_rank or new_position or new_unit):
            changing.append((len(out) - 1, s, new_rank, new_position, new_unit))
    # the staffing table (ក្របខណ្ឌ) and rank quotas, all the soldiers of this entry counted together
    label = "ក្របខណ្ឌ"
    changes = [(s, r, p, u, label) for _, s, r, p, u in changing]
    for (n, *_), problems in zip(changing, staffing_issues(db, "transfer", changes), strict=True):
        out[n][1].extend(p.removeprefix(f"{label}: ") for p in problems)
    return out


@router.post("/rank-position-updates/check", tags=["soldiers"])
def check_rank_position(payload: RankPositionCheckIn, db: Session = Depends(get_db),
                        user: User = Depends(require("rank_position_update", "update"))):
    """The soldiers listed and the military IDs added, each with its values and what saving would do or refuse."""
    pairs, seen, rows = [], set(), []
    for item in payload.items:
        s = db.get(Soldier, item.soldier_id)
        if s and not s.deleted_at and s.id not in seen:
            seen.add(s.id)
            pairs.append((s, _rp_values(s, item)))
    mids = list(dict.fromkeys(format_military_id(x) for x in re.split(r"[\s,;]+", payload.military_ids or "") if x))[:1000]
    found = {s.military_id: s for s in db.scalars(select(Soldier).where(
        Soldier.military_id.in_(mids), Soldier.deleted_at.is_(None)))} if mids else {}
    missing = []
    for mid in mids:
        s = found.get(mid)
        if s is None:
            missing.append({"military_id": mid, "status": "not_found", "errors": ["រកមិនឃើញអត្តលេខនេះ"], "warnings": []})
        elif s.id not in seen:
            seen.add(s.id)
            pairs.append((s, _rp_values(s, payload.defaults)))
    scope = scope_unit_ids(db, user)
    for (s, v), (errors, warnings) in zip(pairs, _rp_problems(db, user, pairs), strict=True):
        if scope is not None and s.current_unit_id not in scope:  # not even the name of a soldier outside one's units
            rows.append({"military_id": s.military_id, "status": "error", "errors": errors, "warnings": []})
            continue
        changed = _rp_changes(s, v)
        status = "error" if errors else "unchanged" if not changed else "warning" if warnings else "ok"
        rows.append({"military_id": s.military_id, "soldier_id": s.id, **soldier_brief(s),
                     "current": _rp_current(s), "current_unit_name": _unit_name(db, s.current_unit_id),
                     **v, "changed": changed, "status": status, "errors": errors, "warnings": warnings})
    return rows + missing


@router.post("/rank-position-updates", status_code=201, tags=["soldiers"])
def save_rank_position(payload: RankPositionIn, request: Request, db: Session = Depends(get_db),
                       user: User = Depends(require("rank_position_update", "update"))):
    """All or none: refused while any soldier has an error (the check above shows them). Soldiers whose values
    are their own already are left as they are."""
    from app.models import DocumentIncoming

    doc = None
    if payload.incoming_document_id:
        doc = db.get(DocumentIncoming, payload.incoming_document_id)
        if not doc or doc.deleted_at:
            raise HTTPException(400, "រកមិនឃើញឯកសារចូល")
    pairs = []
    for item in {i.soldier_id: i for i in payload.items}.values():
        s = db.get(Soldier, item.soldier_id)
        if not s or s.deleted_at:
            raise HTTPException(400, f"រកមិនឃើញយោធិន id={item.soldier_id}")
        pairs.append((s, _rp_values(s, item)))
    problems = _rp_problems(db, user, pairs)
    refused = [f"{s.military_id} {s.name_kh}: {'; '.join(e)}" for (s, _), (e, _) in zip(pairs, problems, strict=True) if e]
    if refused:
        raise HTTPException(400, "មិនអាចរក្សាទុកបាន៖\n" + "\n".join(refused))
    note = " — ".join(x for x in ("Update ស័ក្តិ និងមុខតំណែង",
                                  f"ឯកសារចូល លេខ {doc.incoming_no} ({doc.doc_date:%d/%m/%Y})" if doc else None,
                                  payload.note) if x)
    saved = 0
    for s, v in pairs:
        if not _rp_changes(s, v):
            continue
        before = to_dict(s)
        old_rank, old_position, old_unit = s.current_rank_id, s.current_position_id, s.current_unit_id
        moves = v["unit_id"] != old_unit
        unit_date = (v["unit_date"] if v["unit_date"] != s.unit_transfer_date else None) or date.today() if moves \
            else v["unit_date"]
        if (v["rank_id"], v["position_id"], v["unit_id"]) != (old_rank, old_position, old_unit):
            when = (v["rank_date"] if v["rank_id"] != old_rank else
                    v["position_date"] if v["position_id"] != old_position else unit_date) or date.today()
            add_history(db, s, "update", when, old_rank=old_rank, new_rank=v["rank_id"], old_position=old_position,
                        new_position=v["position_id"], old_unit=old_unit, new_unit=v["unit_id"], note=note[:500])
        if moves:  # out of the old unit, into the new one (within one ស្ថាប័នកងឯកភាព: ផ្លាស់ប្ដូរផ្ទៃក្នុង)
            internal = old_unit and _institution_id(db, old_unit) == _institution_id(db, v["unit_id"])
            if old_unit:
                add_movement(db, s.id, old_unit, "out", "internal" if internal else "transfer_out", unit_date,
                             "soldiers", s.id, note=note[:500])
            add_movement(db, s.id, v["unit_id"], "in", "internal" if internal else "transfer_in" if old_unit else "recruit",
                         unit_date, "soldiers", s.id, note=note[:500])
            s.from_unit_text = s.unit.name_kh if s.unit else s.from_unit_text
        s.current_rank_id, s.rank_date = v["rank_id"], v["rank_date"]
        s.current_position_id, s.position_date = v["position_id"], v["position_date"]
        s.current_unit_id, s.unit_transfer_date = v["unit_id"], unit_date
        s.updated_by = user.id
        audit(db, user, "update", s, before=before, request=request)
        saved += 1
    db.commit()
    return {"saved": saved}
