"""Soldier records (គ្រប់គ្រងយោធិន): CRUD, search, photo, attachments, history, full profile."""

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import Select, extract, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require
from app.models import (
    AwardRecord,
    DisciplineRecord,
    District,
    Lookup,
    Position,
    Rank,
    Soldier,
    SoldierAttachment,
    SoldierChild,
    SoldierEducation,
    SoldierHistory,
    SoldierLanguage,
    Specialty,
    TrainingCourse,
    TrainingParticipant,
    Unit,
    UnitPosition,
    User,
    Village,
)
from app.models.geo import Commune
from app.schemas import SoldierIn
from app.services import soldier_io
from app.services.common import (
    audit,
    check_unit_in_scope,
    delete_storage_file,
    names_by_id,
    paginate,
    save_upload,
    scope_unit_ids,
    storage_file,
    to_dict,
    unit_subtree_ids,
)
from app.services.soldier import (
    add_history,
    add_movement,
    age,
    diff_ym,
    is_inactive,
    soldier_summary,
    status_id_by_code,
    years_ago,
    ym_text,
)

router = APIRouter(prefix="/soldiers", tags=["soldiers"])

SORTS = {
    "name": Soldier.name_kh,
    "military_id": Soldier.military_id,
    "enlistment_date": Soldier.enlistment_date,
    "date_of_birth": Soldier.date_of_birth,
    "rank_date": Soldier.rank_date,
    "created_at": Soldier.created_at,
}


def build_query(db: Session, user: User, *, q=None, rank_id=None, rank_class_id=None, unit_id=None,
                position_id=None, status_id=None, gender=None, age_min=None, age_max=None,
                enlist_year=None, specialty_id=None, birth_province_id=None, education_level_id=None,
                military_ids=None, section_id=None, sort="rank", order="desc") -> Select:
    stmt = select(Soldier).where(Soldier.deleted_at.is_(None))
    scope = scope_unit_ids(db, user)
    if scope is not None:
        stmt = stmt.where(Soldier.current_unit_id.in_(scope))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Soldier.name_kh.ilike(like), Soldier.name_latin.ilike(like),
                              Soldier.military_id.ilike(like), Soldier.national_id.ilike(like),
                              Soldier.phone.ilike(like)))
    if military_ids:
        # a pasted list of military IDs (one per line, or separated by commas/spaces)
        ids = [x for x in re.split(r"[\s,;]+", military_ids) if x]
        stmt = stmt.where(Soldier.military_id.in_(ids[:2000]))
    if rank_id:
        stmt = stmt.where(Soldier.current_rank_id == rank_id)
    if rank_class_id:
        stmt = stmt.where(Soldier.current_rank_id.in_(select(Rank.id).where(Rank.rank_class_id == rank_class_id)))
    if unit_id:
        stmt = stmt.where(Soldier.current_unit_id.in_(unit_subtree_ids(db, unit_id)))
    if position_id:
        stmt = stmt.where(Soldier.current_position_id == position_id)
    if status_id:
        stmt = stmt.where(Soldier.status_id == status_id)
    if gender:
        stmt = stmt.where(Soldier.gender == gender)
    if age_min is not None:
        stmt = stmt.where(Soldier.date_of_birth <= years_ago(age_min))
    if age_max is not None:
        stmt = stmt.where(Soldier.date_of_birth > years_ago(age_max + 1))
    if enlist_year:
        stmt = stmt.where(extract("year", Soldier.enlistment_date) == enlist_year)
    if specialty_id:
        stmt = stmt.where(Soldier.specialty_id == specialty_id)
    if section_id:  # ផ្នែក: every specialty of the section
        stmt = stmt.where(Soldier.specialty_id.in_(select(Specialty.id).where(Specialty.section_id == section_id)))
    if education_level_id:
        stmt = stmt.where(Soldier.education_level_id == education_level_id)
    if birth_province_id:
        stmt = stmt.where(Soldier.birth_village_id.in_(
            select(Village.id).join(Commune).join(District).where(District.province_id == birth_province_id)))
    if sort == "rank":
        stmt = stmt.outerjoin(Rank, Rank.id == Soldier.current_rank_id)
        col = Rank.sort_order
        stmt = stmt.order_by(col.desc() if order == "desc" else col.asc(), Soldier.name_kh)
    else:
        col = SORTS.get(sort, Soldier.id)
        stmt = stmt.order_by(col.desc() if order == "desc" else col.asc())
    return stmt


def _filters(
    q: str | None = None, rank_id: int | None = None, rank_class_id: int | None = None,
    unit_id: int | None = None, position_id: int | None = None, status_id: int | None = None,
    gender: str | None = None, age_min: int | None = None, age_max: int | None = None,
    enlist_year: int | None = None, specialty_id: int | None = None, birth_province_id: int | None = None,
    education_level_id: int | None = None, military_ids: str | None = None, section_id: int | None = None,
    sort: str = "rank", order: str = "desc",
) -> dict:
    return {k: v for k, v in locals().items()}


def get_soldier(db: Session, user: User, soldier_id: int) -> Soldier:
    s = db.get(Soldier, soldier_id)
    if not s or s.deleted_at:
        raise HTTPException(404, "រកមិនឃើញយោធិន")
    scope = scope_unit_ids(db, user)
    if scope is not None and s.current_unit_id not in scope:
        raise HTTPException(403, "យោធិននេះនៅក្រៅសិទ្ធិរបស់អ្នក")
    return s


def soldier_detail(s: Soldier) -> dict:
    data = to_dict(s)
    data.update(soldier_summary(s))
    data["educations"] = [to_dict(e) for e in s.educations]
    data["languages"] = [to_dict(lng) for lng in s.languages]
    data["children"] = [to_dict(c) for c in s.children]
    return data


@router.get("")
def list_soldiers(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=500),
                  f: dict = Depends(_filters), db: Session = Depends(get_db),
                  user: User = Depends(require("soldiers", "view"))):
    items, total = paginate(db, build_query(db, user, **f), page, size)
    return {"items": [soldier_summary(s) for s in items], "total": total, "page": page, "size": size}


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(buf, name: str) -> StreamingResponse:
    return StreamingResponse(buf, media_type=XLSX, headers={"Content-Disposition": f"attachment; filename={name}"})


@router.get("/export")
def export_soldiers(f: dict = Depends(_filters), db: Session = Depends(get_db),
                    user: User = Depends(require("soldiers", "export"))):
    """Same columns as the import template (so it can be imported or compared again), plus computed ones."""
    rows = db.scalars(build_query(db, user, **f)).unique().all()
    return _xlsx(soldier_io.export(db, rows, soldier_summary), "soldiers.xlsx")


# ---------------- Excel import (ការងារបញ្ចូលក្របខ័ណ្ឌយោធិនអាជីព) & comparison (ការប្រៀបធៀប) ----------------

@router.get("/import/fields")
def import_fields(_: User = Depends(require("soldiers", "view"))):
    """The Excel columns (for the comparison's field picker)."""
    return [{"key": f.key, "label": f.label, "required": f.required} for f in soldier_io.FIELDS]


@router.get("/import/template")
def import_template(db: Session = Depends(get_db), _: User = Depends(require("soldiers", "create"))):
    return _xlsx(soldier_io.template(db), "soldier-import-template.xlsx")


@router.post("/import")
def import_soldiers(request: Request, file: UploadFile = File(...), dry_run: bool = Form(True),
                    update_existing: bool = Form(False), db: Session = Depends(get_db),
                    user: User = Depends(require("soldiers", "create"))):
    """dry_run (default): check every row and report what would happen. Otherwise create/update the valid rows;
    rows with errors are skipped and listed."""
    if update_existing and not user.can("soldiers", "update"):
        raise HTTPException(403, "គ្មានសិទ្ធិកែប្រែយោធិនដែលមានស្រាប់")
    fields, data, unknown = soldier_io.read_sheet(file.file.read())
    rows = soldier_io.plan_import(db, soldier_io.parse_rows(db, data, fields), update_existing, scope_unit_ids(db, user))
    if not dry_run:
        active = status_id_by_code(db, "active")
        for r in rows:
            if r["action"] == "error":
                continue
            try:
                with db.begin_nested():  # one bad row must not undo the others
                    _import_row(db, user, r, active)
            except IntegrityError as e:
                r["action"], r["errors"] = "error", [_integrity_message(e)]
        audit(db, user, "import", table="soldiers", record_id="*", request=request,
              before={"file": file.filename, "created": sum(r["action"] == "create" for r in rows)})
        db.commit()
    return {**soldier_io.import_summary(rows), "dry_run": dry_run,
            "columns": [f.label for f in fields], "unknown_columns": unknown}


def _import_row(db: Session, user: User, r: dict, active_status: int | None) -> None:
    values = r["values"]
    if r["action"] == "create":
        s = Soldier(**values, created_by=user.id)
        s.status_id = s.status_id or active_status
        db.add(s)
        db.flush()
        record_new(db, s)
        r["soldier_id"] = s.id
    else:
        s = db.get(Soldier, r["soldier_id"])
        old = (s.current_rank_id, s.current_position_id, s.current_unit_id)
        old_unit_date = s.unit_transfer_date
        for k, v in values.items():  # empty cells leave the current value
            setattr(s, k, v)
        s.updated_by = user.id
        db.flush()
        record_edit(db, s, old, old_unit_date, "កែប្រែតាមការនាំចូល Excel")


@router.post("/compare")
def compare_soldiers(file: UploadFile = File(...), fields: str | None = Form(None), unit_id: int | None = Form(None),
                     format: str = Form("json"), db: Session = Depends(get_db),
                     user: User = Depends(require("soldiers", "view"))):
    """Compare an Excel list with the soldier list on the chosen fields (default: every column in the file).
    Soldiers of `unit_id` (and its sub-units) that are missing from the file are listed too."""
    file_fields, data, _ = soldier_io.read_sheet(file.file.read())
    wanted = [soldier_io.BY_KEY[k] for k in (fields or "").split(",") if k in soldier_io.BY_KEY]
    chosen = [f for f in (wanted or file_fields) if f in file_fields and f.key != "military_id"]
    expected = db.scalars(build_query(db, user, unit_id=unit_id)).unique().all() if unit_id else []
    result = soldier_io.compare(db, data, chosen, expected)
    scope = scope_unit_ids(db, user)
    if scope is not None:  # never reveal soldiers outside the user's units
        visible = set(db.scalars(select(Soldier.id).where(Soldier.current_unit_id.in_(scope))))
        result["rows"] = [x for x in result["rows"] if not x.get("soldier_id") or x["soldier_id"] in visible]
    if format == "xlsx":
        return _xlsx(soldier_io.compare_workbook(result), "compare.xlsx")
    return result


@router.get("/{soldier_id}")
def get_one(soldier_id: int, db: Session = Depends(get_db), user: User = Depends(require("soldiers", "view"))):
    return soldier_detail(get_soldier(db, user, soldier_id))


def _apply(s: Soldier, data: SoldierIn) -> None:
    payload = data.model_dump(exclude={"educations", "languages", "children"})
    for k, v in payload.items():
        setattr(s, k, v)
    s.educations = [SoldierEducation(**e.model_dump()) for e in data.educations]
    s.languages = [SoldierLanguage(**lng.model_dump()) for lng in data.languages]
    s.children = [SoldierChild(**c.model_dump()) for c in data.children]
    if data.children and not data.children_count:
        s.children_count = len(data.children)


def _integrity_message(e: IntegrityError) -> str:
    msg = str(e.orig.args[-1]) if e.orig else str(e)
    if "military_id" in msg:
        return "អត្តលេខនេះមានរួចហើយ"
    if "national_id" in msg:
        return "លេខអត្តសញ្ញាណប័ណ្ណនេះមានរួចហើយ"
    return f"ទិន្នន័យមិនត្រឹមត្រូវ: {msg}"


def record_new(db: Session, s: Soldier) -> None:
    """A soldier entered for the first time: initial history row and, with a unit, the 'joined' movement."""
    add_history(db, s, "initial", s.rank_date or s.enlistment_date, new_rank=s.current_rank_id,
                new_position=s.current_position_id, new_unit=s.current_unit_id, note="ទិន្នន័យដំបូង")
    if s.current_unit_id:
        add_movement(db, s.id, s.current_unit_id, "in", "recruit",
                     s.unit_transfer_date or s.enlistment_date or date.today(), "soldiers", s.id)


def record_edit(db: Session, s: Soldier, old: tuple, old_unit_date: date | None, note: str) -> None:
    """Rank/position/unit changed outside of a decision (profile edit, Excel import): a correction in the history,
    and a unit change moves the soldier between unit strengths like a transfer decision."""
    new = (s.current_rank_id, s.current_position_id, s.current_unit_id)
    if old != new:
        add_history(db, s, "correction", date.today(), old_rank=old[0], new_rank=new[0],
                    old_position=old[1], new_position=new[1], old_unit=old[2], new_unit=new[2], note=note)
    if old[2] != new[2] and not is_inactive(db, s):
        moved = (s.unit_transfer_date if s.unit_transfer_date != old_unit_date else None) or date.today()
        if old[2]:
            add_movement(db, s.id, old[2], "out", "transfer_out", moved, "soldiers", s.id, note=note)
        if new[2]:
            add_movement(db, s.id, new[2], "in", "transfer_in" if old[2] else "recruit", moved, "soldiers", s.id,
                         note=note)


@router.post("", status_code=201)
def create_soldier(payload: SoldierIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(require("soldiers", "create"))):
    if payload.current_unit_id:
        check_unit_in_scope(db, user, payload.current_unit_id)
    s = Soldier(created_by=user.id)
    _apply(s, payload)
    db.add(s)
    try:
        db.flush()
        record_new(db, s)
        audit(db, user, "create", s, request=request)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, _integrity_message(e))
    return soldier_detail(s)


@router.put("/{soldier_id}")
def update_soldier(soldier_id: int, payload: SoldierIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(require("soldiers", "update"))):
    s = get_soldier(db, user, soldier_id)
    if payload.current_unit_id and payload.current_unit_id != s.current_unit_id:
        check_unit_in_scope(db, user, payload.current_unit_id)
    before = to_dict(s)
    old = (s.current_rank_id, s.current_position_id, s.current_unit_id)
    old_unit_date = s.unit_transfer_date
    _apply(s, payload)
    s.updated_by = user.id
    try:
        record_edit(db, s, old, old_unit_date, "កែតម្រូវដោយផ្ទាល់ពីប្រវត្តិរូប")
        db.flush()
        audit(db, user, "update", s, before=before, request=request)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, _integrity_message(e))
    return soldier_detail(s)


@router.delete("/{soldier_id}")
def delete_soldier(soldier_id: int, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(require("soldiers", "delete"))):
    s = get_soldier(db, user, soldier_id)
    s.deleted_at = datetime.now()
    audit(db, user, "delete", table="soldiers", record_id=s.id, before=to_dict(s), request=request)
    db.commit()
    return {"ok": True}


# ---------------- photo ----------------

@router.post("/{soldier_id}/photo")
def upload_photo(soldier_id: int, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
                 user: User = Depends(require("soldiers", "update"))):
    s = get_soldier(db, user, soldier_id)
    path, _ = save_upload(file, "photos", images_only=True)
    delete_storage_file(s.photo_path)
    s.photo_path = path
    audit(db, user, "upload_photo", table="soldiers", record_id=s.id, request=request)
    db.commit()
    return {"photo_path": path}


@router.get("/{soldier_id}/photo")
def get_photo(soldier_id: int, db: Session = Depends(get_db), user: User = Depends(require("soldiers", "view"))):
    s = get_soldier(db, user, soldier_id)
    if not s.photo_path:
        raise HTTPException(404, "គ្មានរូបថត")
    return FileResponse(storage_file(s.photo_path))


# ---------------- attachments ----------------

@router.get("/{soldier_id}/attachments")
def list_attachments(soldier_id: int, db: Session = Depends(get_db), user: User = Depends(require("soldiers", "view"))):
    get_soldier(db, user, soldier_id)
    rows = db.scalars(select(SoldierAttachment).where(SoldierAttachment.soldier_id == soldier_id)
                      .order_by(SoldierAttachment.id.desc()))
    return [to_dict(a) for a in rows]


@router.post("/{soldier_id}/attachments", status_code=201)
def add_attachment(soldier_id: int, request: Request, file: UploadFile = File(...),
                   description: str | None = Form(None), db: Session = Depends(get_db),
                   user: User = Depends(require("soldiers", "update"))):
    get_soldier(db, user, soldier_id)
    path, size = save_upload(file, "soldiers")
    a = SoldierAttachment(soldier_id=soldier_id, file_path=path, file_name=file.filename or "file",
                          file_size=size, description=description, uploaded_by=user.id)
    db.add(a)
    db.flush()
    audit(db, user, "create", a, request=request)
    db.commit()
    return to_dict(a)


@router.get("/{soldier_id}/attachments/{att_id}")
def download_attachment(soldier_id: int, att_id: int, db: Session = Depends(get_db),
                        user: User = Depends(require("soldiers", "view"))):
    get_soldier(db, user, soldier_id)
    a = db.get(SoldierAttachment, att_id)
    if not a or a.soldier_id != soldier_id:
        raise HTTPException(404, "រកមិនឃើញ")
    return FileResponse(storage_file(a.file_path), filename=a.file_name)


@router.delete("/{soldier_id}/attachments/{att_id}")
def delete_attachment(soldier_id: int, att_id: int, request: Request, db: Session = Depends(get_db),
                      user: User = Depends(require("soldiers", "update"))):
    get_soldier(db, user, soldier_id)
    a = db.get(SoldierAttachment, att_id)
    if not a or a.soldier_id != soldier_id:
        raise HTTPException(404, "រកមិនឃើញ")
    delete_storage_file(a.file_path)
    db.delete(a)
    audit(db, user, "delete", table="soldier_attachments", record_id=att_id, request=request)
    db.commit()
    return {"ok": True}


# ---------------- history & full profile ----------------

def history_rows(db: Session, soldier_id: int) -> list[dict]:
    rows = db.scalars(select(SoldierHistory).where(SoldierHistory.soldier_id == soldier_id)
                      .order_by(SoldierHistory.effective_date.desc(), SoldierHistory.id.desc())).all()
    ranks = names_by_id(db, Rank, {r.old_rank_id for r in rows} | {r.new_rank_id for r in rows})
    poss = names_by_id(db, Position, {r.old_position_id for r in rows} | {r.new_position_id for r in rows})
    units = names_by_id(db, Unit, {r.old_unit_id for r in rows} | {r.new_unit_id for r in rows})
    return [{
        **to_dict(r),
        "old_rank": ranks.get(r.old_rank_id), "new_rank": ranks.get(r.new_rank_id),
        "old_position": poss.get(r.old_position_id), "new_position": poss.get(r.new_position_id),
        "old_unit": units.get(r.old_unit_id), "new_unit": units.get(r.new_unit_id),
    } for r in rows]


@router.get("/{soldier_id}/history")
def soldier_history(soldier_id: int, db: Session = Depends(get_db), user: User = Depends(require("soldiers", "view"))):
    get_soldier(db, user, soldier_id)
    return history_rows(db, soldier_id)


@router.get("/{soldier_id}/profile")
def soldier_profile(soldier_id: int, db: Session = Depends(get_db), user: User = Depends(require("soldiers", "view"))):
    """Everything needed for the profile page and the A4 print (names resolved)."""
    s = get_soldier(db, user, soldier_id)
    d = soldier_detail(s)
    lk = names_by_id(db, Lookup, {s.blood_type_id, s.education_level_id, s.marital_status_id, s.spouse_job_id}
                | {e.education_level_id for e in s.educations} | {lg.language_id for lg in s.languages})
    d.update({
        "blood_type_name": lk.get(s.blood_type_id),
        "education_level_name": lk.get(s.education_level_id),
        "marital_status_name": lk.get(s.marital_status_id),
        "spouse_job_name": lk.get(s.spouse_job_id),
        "age": age(s.date_of_birth),
    })
    for e in d["educations"]:
        e["education_level_name"] = lk.get(e["education_level_id"])
    for lg in d["languages"]:
        lg["language_name"] = lk.get(lg["language_id"])
    from app.api.v1.master import village_path  # local import to avoid a cycle

    for key in ("birth_village_id", "current_village_id"):
        vid = getattr(s, key)
        d[key.replace("_id", "_text")] = village_path(vid, db, user)["text"] if vid else None
    d["history"] = history_rows(db, s.id)
    d["awards"] = [{**to_dict(a), "award_type_name": a.award_type.name_kh if a.award_type else None}
                   for a in db.scalars(select(AwardRecord).where(AwardRecord.soldier_id == s.id,
                                                                 AwardRecord.deleted_at.is_(None))
                                       .order_by(AwardRecord.decision_date))]
    d["disciplines"] = [{**to_dict(x), "discipline_type_name": x.discipline_type.name_kh if x.discipline_type else None}
                        for x in db.scalars(select(DisciplineRecord).where(DisciplineRecord.soldier_id == s.id,
                                                                           DisciplineRecord.deleted_at.is_(None))
                                            .order_by(DisciplineRecord.decision_date))]
    trainings = db.execute(
        select(TrainingCourse, TrainingParticipant)
        .join(TrainingParticipant, TrainingParticipant.course_id == TrainingCourse.id)
        .where(TrainingParticipant.soldier_id == s.id, TrainingCourse.deleted_at.is_(None))
        .order_by(TrainingCourse.start_date)
    ).all()
    d["trainings"] = [{**to_dict(c), "result": p.result, "certificate_no": p.certificate_no} for c, p in trainings]
    d["service_length"] = ym_text(diff_ym(s.enlistment_date))
    d["specialty_name"] = db.get(Specialty, s.specialty_id).name_kh if s.specialty_id else None
    # salaries: the rank's, and the position's (the unit's staffing table may override the position allowance)
    up = db.scalar(select(UnitPosition).where(UnitPosition.unit_id == s.current_unit_id,
                                              UnitPosition.position_id == s.current_position_id)) \
        if s.current_unit_id and s.current_position_id else None
    pos_salary = up.salary if up and up.salary is not None else (s.position.salary if s.position else None)
    d["rank_salary"] = float(s.rank.salary) if s.rank and s.rank.salary is not None else None
    d["position_salary"] = float(pos_salary) if pos_salary is not None else None
    return d
