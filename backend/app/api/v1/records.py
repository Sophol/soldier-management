"""Training, discipline, awards, retirement/category-2, separation and strength movements."""

from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.crud import crud_router
from app.models import (
    AwardRecord,
    DisciplineRecord,
    RetirementRecord,
    SeparationRecord,
    Soldier,
    StrengthMovement,
    TrainingCourse,
    TrainingParticipant,
    User,
)
from app.schemas import AwardIn, DisciplineIn, RetirementIn, SeparationIn, StrengthIn, TrainingCourseIn
from app.services.common import scope_unit_ids, to_dict
from app.services.soldier import add_movement, status_id_by_code

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


def _soldier_hook(db, user, obj, data, is_new):
    _check_soldier(db, user, data["soldier_id"])
    if not is_new and data["soldier_id"] != obj.soldier_id:
        raise HTTPException(400, "មិនអាចប្ដូរយោធិនក្នុងកំណត់ត្រានេះបានទេ")


# ---------------- training ----------------

def course_out(c: TrainingCourse) -> dict:
    return {**to_dict(c), "participant_count": len(c.participants),
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
    if data.get("start_date") and data.get("end_date") and data["end_date"] < data["start_date"]:
        raise HTTPException(400, "ថ្ងៃបញ្ចប់ត្រូវនៅក្រោយថ្ងៃចាប់ផ្ដើម")


router.include_router(crud_router(
    prefix="/training/courses", model=TrainingCourse, module="training", schema=TrainingCourseIn,
    search_fields=(TrainingCourse.name, TrainingCourse.institution),
    filter_fields={"course_type": TrainingCourse.course_type, "specialty_id": TrainingCourse.specialty_id,
                   "date_from": TrainingCourse.start_date, "date_to": TrainingCourse.start_date},
    order_by=(TrainingCourse.start_date.desc(), TrainingCourse.id.desc()),
    serialize=course_out, before_save=_course_before, tags=["training"],
))


# ---------------- discipline & awards ----------------

def discipline_out(r: DisciplineRecord) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier),
            "discipline_type_name": r.discipline_type.name_kh if r.discipline_type else None}


def award_out(r: AwardRecord) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier), "award_type_name": r.award_type.name_kh if r.award_type else None}


router.include_router(crud_router(
    prefix="/discipline", model=DisciplineRecord, module="discipline", schema=DisciplineIn,
    search_fields=(DisciplineRecord.reason, DisciplineRecord.decision_no),
    filter_fields={"soldier_id": DisciplineRecord.soldier_id, "discipline_type_id": DisciplineRecord.discipline_type_id,
                   "date_from": DisciplineRecord.decision_date, "date_to": DisciplineRecord.decision_date},
    order_by=(DisciplineRecord.decision_date.desc(), DisciplineRecord.id.desc()),
    serialize=discipline_out, base_query=scoped(DisciplineRecord), before_save=_soldier_hook,
))
router.include_router(crud_router(
    prefix="/awards", model=AwardRecord, module="awards", schema=AwardIn,
    search_fields=(AwardRecord.reason, AwardRecord.decision_no),
    filter_fields={"soldier_id": AwardRecord.soldier_id, "award_type_id": AwardRecord.award_type_id,
                   "date_from": AwardRecord.decision_date, "date_to": AwardRecord.decision_date},
    order_by=(AwardRecord.decision_date.desc(), AwardRecord.id.desc()),
    serialize=award_out, base_query=scoped(AwardRecord), before_save=_soldier_hook,
))


# ---------------- retirement / category 2 / separation ----------------

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


def retirement_out(r: RetirementRecord) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier),
            "type_name": "សោធននិវត្តន៍" if r.type == "pension" else "យោធិនប្រភេទ២"}


def separation_out(r: SeparationRecord) -> dict:
    return {**to_dict(r), **soldier_brief(r.soldier), "reason_name": r.reason.name_kh if r.reason else None}


router.include_router(crud_router(
    prefix="/retirements", model=RetirementRecord, module="retirement", schema=RetirementIn,
    search_fields=(RetirementRecord.decision_no, RetirementRecord.notes),
    filter_fields={"type": RetirementRecord.type, "soldier_id": RetirementRecord.soldier_id,
                   "date_from": RetirementRecord.effective_date, "date_to": RetirementRecord.effective_date},
    order_by=(RetirementRecord.effective_date.desc(), RetirementRecord.id.desc()),
    serialize=retirement_out, base_query=scoped(RetirementRecord), before_save=_soldier_hook,
    after_save=_leave_after_save("retirement_records", lambda o: "retired" if o.type == "pension" else "category2",
                                 lambda o: "retire" if o.type == "pension" else "category2"),
    after_delete=_leave_after_delete("retirement_records"), tags=["retirement"],
))
router.include_router(crud_router(
    prefix="/separations", model=SeparationRecord, module="separation", schema=SeparationIn,
    search_fields=(SeparationRecord.decision_no, SeparationRecord.notes),
    filter_fields={"reason_id": SeparationRecord.reason_id, "soldier_id": SeparationRecord.soldier_id,
                   "date_from": SeparationRecord.effective_date, "date_to": SeparationRecord.effective_date},
    order_by=(SeparationRecord.effective_date.desc(), SeparationRecord.id.desc()),
    serialize=separation_out, base_query=scoped(SeparationRecord), before_save=_soldier_hook,
    after_save=_leave_after_save("separation_records", lambda o: "separated", lambda o: "separate"),
    after_delete=_leave_after_delete("separation_records"), tags=["separation"],
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
    ids = scope_unit_ids(db, user)
    return stmt.where(StrengthMovement.unit_id.in_(ids)) if ids is not None else stmt


def _movement_before(db, user, obj, data, is_new):
    _check_soldier(db, user, data["soldier_id"])
    data["source_table"] = None if is_new else obj.source_table
    if not is_new and obj.source_table:
        raise HTTPException(400, "កំណត់ត្រានេះបង្កើតដោយស្វ័យប្រវត្តិ មិនអាចកែប្រែបានទេ")
    if data["movement_date"] > date.today():
        raise HTTPException(400, "កាលបរិច្ឆេទមិនអាចនៅថ្ងៃអនាគត")


router.include_router(crud_router(
    prefix="/strength-movements", model=StrengthMovement, module="strength", schema=StrengthIn,
    search_fields=(StrengthMovement.note,),
    filter_fields={"direction": StrengthMovement.direction, "reason": StrengthMovement.reason,
                   "unit_id": StrengthMovement.unit_id, "soldier_id": StrengthMovement.soldier_id,
                   "date_from": StrengthMovement.movement_date, "date_to": StrengthMovement.movement_date},
    order_by=(StrengthMovement.movement_date.desc(), StrengthMovement.id.desc()),
    serialize=movement_out, base_query=_movement_scope, before_save=_movement_before, tags=["strength"],
))
