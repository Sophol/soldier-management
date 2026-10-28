"""Training, discipline, awards, retirement/category-2, separation and strength movements."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, delete, extract, not_, or_, select
from sqlalchemy.orm import Session

from app.api.crud import crud_router
from app.models import (
    AwardRecord,
    Country,
    DisciplineRecord,
    MilitaryCard,
    RetirementRecord,
    SeparationRecord,
    Soldier,
    StrengthMovement,
    TrainingCourse,
    TrainingParticipant,
    User,
)
from app.schemas import (
    AwardIn,
    DisciplineIn,
    MilitaryCardIn,
    RetirementIn,
    SeparationIn,
    StrengthIn,
    TrainingCourseIn,
)
from app.services.common import scope_unit_ids, to_dict
from app.services.soldier import add_movement, is_inactive, status_id_by_code

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
    _check_soldier(db, user, data["soldier_id"])
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


def _abroad_filter(stmt, v):
    """ក្នុង/ក្រៅប្រទេស: a course with a country other than Cambodia is abroad."""
    cambodia = select(Country.id).where(Country.name_en == "Cambodia").scalar_subquery()
    abroad = and_(TrainingCourse.country_id.is_not(None), TrainingCourse.country_id != cambodia)
    return stmt.where(abroad if v == "yes" else not_(abroad))


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


def _leave_after_delete(table: str):
    def hook(db: Session, user: User, obj):
        s = db.get(Soldier, obj.soldier_id)
        s.status_id = obj.previous_status_id or status_id_by_code(db, "active")
        db.execute(delete(StrengthMovement).where(StrengthMovement.source_table == table,
                                                  StrengthMovement.source_id == obj.id))

    return hook


RETIREMENT_TYPES = {"pension": "សោធននិវត្តន៍ (គ្រប់អាយុ)", "voluntary": "ស្ម័គ្រចិត្តចូលនិវត្តន៍",
                    "disability": "ពិការ", "death": "ស្លាប់", "category2": "យោធិនប្រភេទ២"}
CASE_STATUS = {"submitted": "ដាក់ឯកសារ", "processing": "កំពុងដំណើរការ", "done": "រួចរាល់"}
# the soldier's status once the record is saved
RETIREMENT_SOLDIER_STATUS = {"category2": "category2", "death": "deceased"}


def retirement_out(r: RetirementRecord) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier), "type_name": RETIREMENT_TYPES.get(r.type, r.type),
            "case_status_name": CASE_STATUS.get(r.case_status)}


def separation_out(r: SeparationRecord) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier), "reason_name": r.reason.name_kh if r.reason else None}


router.include_router(crud_router(
    prefix="/retirements", model=RetirementRecord, module="retirement", schema=RetirementIn,
    search_fields=(RetirementRecord.decision_no, RetirementRecord.notes),
    filter_fields={"type": RetirementRecord.type, "soldier_id": RetirementRecord.soldier_id,
                   "case_status": RetirementRecord.case_status,
                   "date_from": RetirementRecord.effective_date, "date_to": RetirementRecord.effective_date},
    custom_filters={"year": by_year(RetirementRecord.effective_date)},
    order_by=(RetirementRecord.effective_date.desc(), RetirementRecord.id.desc()),
    serialize=retirement_out, base_query=scoped(RetirementRecord), before_save=_leave_before,
    after_save=_leave_after_save("retirement_records", lambda o: RETIREMENT_SOLDIER_STATUS.get(o.type, "retired"),
                                 lambda o: "category2" if o.type == "category2" else "retire"),
    after_delete=_leave_after_delete("retirement_records"), tags=["retirement"],
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

CARD_STATUS = {"issued": "ចេញរួច", "pending": "មិនទាន់ចេញ", "expired": "ផុតកំណត់", "lost": "បាត់", "replaced": "ជំនួស"}


def card_status(c: MilitaryCard) -> str:
    """An issued card past its expiry date is expired (ផុតកំណត់)."""
    if c.status == "issued" and c.expiry_date and c.expiry_date < date.today():
        return "expired"
    return c.status


def card_out(c: MilitaryCard) -> dict:
    st = card_status(c)
    days = (c.expiry_date - date.today()).days if c.expiry_date else None
    return {**to_dict(c), **soldier_brief(c.soldier), "status": st, "stored_status": c.status,
            "status_name": CARD_STATUS[st], "days_left": days}


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
    custom_filters={"status": _card_status_filter, "expiring_within": _card_expiring_filter},
    order_by=(MilitaryCard.issue_date.desc(), MilitaryCard.id.desc()),
    serialize=card_out, base_query=scoped(MilitaryCard), before_save=_card_before, tags=["id cards"],
))


# ---------------- strength movements (ការងារកើនថយ) ----------------

MOVEMENT_REASONS = {
    "recruit": "ចូលបម្រើថ្មី", "transfer_in": "ផ្លាស់មកពីអង្គភាពផ្សេង", "reinstate": "ចូលបម្រើវិញ",
    "transfer_out": "ផ្លាស់ទៅអង្គភាពផ្សេង", "retire": "សោធននិវត្តន៍", "category2": "យោធិនប្រភេទ២",
    "separate": "ចេញពីជួរ", "other": "ផ្សេងៗ",
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
