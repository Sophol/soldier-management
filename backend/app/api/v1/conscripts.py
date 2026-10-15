"""Conscription (ការងារជ្រើសរើសទ័ព និងយោធិនបម្រុង — យុវជនបំពេញកាតព្វកិច្ចយោធា): people, their registrations,
medical exams (separate permission: health data) and service periods."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, object_session

from app.api.crud import crud_router
from app.core.database import get_db
from app.core.deps import get_current_user, require
from app.models import (
    Conscript,
    ConscriptMedical,
    ConscriptRegistration,
    ConscriptService,
    District,
    Lookup,
    Province,
    Rank,
    Unit,
    User,
)
from app.models.conscript import EXEMPTION_REASONS, MEDICAL_RESULTS, REGISTRATION_STATUSES
from app.schemas import ConscriptIn, ConscriptMedicalIn, ConscriptRegistrationIn, ConscriptServiceIn
from app.services.common import audit, delete_storage_file, paginate, save_upload, storage_file, to_dict
from app.services.soldier import age

router = APIRouter()


@router.get("/meta/conscription", tags=["conscripts"])
def conscription_meta(_: User = Depends(get_current_user)):
    as_options = lambda d: [{"value": k, "label": v} for k, v in d.items()]  # noqa: E731
    return {"statuses": as_options(REGISTRATION_STATUSES), "reasons": as_options(EXEMPTION_REASONS),
            "results": as_options(MEDICAL_RESULTS)}


# ---------------- people ----------------

def _latest_registration(db: Session, conscript_id: int) -> ConscriptRegistration | None:
    return db.scalar(select(ConscriptRegistration).where(
        ConscriptRegistration.conscript_id == conscript_id, ConscriptRegistration.deleted_at.is_(None))
        .order_by(ConscriptRegistration.registration_year.desc(), ConscriptRegistration.id.desc()).limit(1))


def conscript_out(db: Session, c: Conscript) -> dict:
    reg = _latest_registration(db, c.id)
    return {**to_dict(c), "age": age(c.date_of_birth),
            "status": reg.status if reg else None,
            "status_name": REGISTRATION_STATUSES.get(reg.status) if reg else None,
            "registration_year": reg.registration_year if reg else None,
            "province_name": db.get(Province, reg.province_id).name_kh if reg and reg.province_id else None,
            "education_level_name": db.get(Lookup, c.education_level_id).name_kh if c.education_level_id else None}


def _get_conscript(db: Session, conscript_id: int) -> Conscript:
    c = db.get(Conscript, conscript_id)
    if not c or c.deleted_at:
        raise HTTPException(404, "រកមិនឃើញ")
    return c


# registered before the generic CRUD routes so that GET /conscripts uses these filters
@router.get("/conscripts", tags=["conscripts"])
def list_conscripts(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=500), q: str | None = None,
                    gender: str | None = None, status: str | None = None, registration_year: int | None = None,
                    province_id: int | None = None, db: Session = Depends(get_db),
                    _: User = Depends(require("conscripts", "view"))):
    """Filters on status / year / province look at the person's registrations."""
    stmt = select(Conscript).where(Conscript.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Conscript.name_kh.ilike(like), Conscript.name_latin.ilike(like),
                              Conscript.conscript_no.ilike(like), Conscript.national_id.ilike(like),
                              Conscript.phone.ilike(like)))
    if gender:
        stmt = stmt.where(Conscript.gender == gender)
    if status or registration_year or province_id:
        reg = select(ConscriptRegistration.conscript_id).where(ConscriptRegistration.deleted_at.is_(None))
        if status:
            reg = reg.where(ConscriptRegistration.status == status)
        if registration_year:
            reg = reg.where(ConscriptRegistration.registration_year == registration_year)
        if province_id:
            reg = reg.where(ConscriptRegistration.province_id == province_id)
        stmt = stmt.where(Conscript.id.in_(reg))
    items, total = paginate(db, stmt.order_by(Conscript.id.desc()), page, size)
    return {"items": [conscript_out(db, c) for c in items], "total": total, "page": page, "size": size}


@router.post("/conscripts/{conscript_id}/photo", tags=["conscripts"])
def upload_photo(conscript_id: int, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
                 user: User = Depends(require("conscripts", "update"))):
    c = _get_conscript(db, conscript_id)
    path, _ = save_upload(file, "conscripts", images_only=True)
    delete_storage_file(c.photo_path)
    c.photo_path = path
    audit(db, user, "upload_photo", table="conscripts", record_id=c.id, request=request)
    db.commit()
    return {"photo_path": path}


@router.get("/conscripts/{conscript_id}/photo", tags=["conscripts"])
def get_photo(conscript_id: int, db: Session = Depends(get_db), _: User = Depends(require("conscripts", "view"))):
    c = _get_conscript(db, conscript_id)
    if not c.photo_path:
        raise HTTPException(404, "គ្មានរូបថត")
    return FileResponse(storage_file(c.photo_path))


router.include_router(crud_router(
    prefix="/conscripts", model=Conscript, module="conscripts", schema=ConscriptIn,
    serialize=lambda c: conscript_out(object_session(c), c), tags=["conscripts"],
))


# ---------------- registrations, medical exams, service ----------------

def _check_conscript(db: Session, conscript_id: int) -> None:
    _get_conscript(db, conscript_id)


def _registration_before(db, user, obj, data, is_new):
    _check_conscript(db, data["conscript_id"])
    if data["status"] in ("exempted", "deferred") and not data.get("reason"):
        raise HTTPException(400, "សូមជ្រើសរើសមូលហេតុនៃការលើកលែង ឬពន្យារ")
    if data["status"] not in ("exempted", "deferred"):
        data["reason"] = None
    if data.get("district_id"):
        district = db.get(District, data["district_id"])
        if not district or (data.get("province_id") and district.province_id != data["province_id"]):
            raise HTTPException(400, "ស្រុក/ខណ្ឌមិនស្ថិតក្នុងរាជធានី/ខេត្តដែលបានជ្រើសរើស")
        data["province_id"] = district.province_id


def registration_out(r: ConscriptRegistration) -> dict:
    db = object_session(r)
    return {**to_dict(r), "conscript_name": r.conscript.name_kh, "conscript_no": r.conscript.conscript_no,
            "status_name": REGISTRATION_STATUSES.get(r.status), "reason_name": EXEMPTION_REASONS.get(r.reason),
            "province_name": db.get(Province, r.province_id).name_kh if r.province_id else None,
            "district_name": db.get(District, r.district_id).name_kh if r.district_id else None}


def medical_out(m: ConscriptMedical) -> dict:
    bmi = None
    if m.height_cm and m.weight_kg:
        bmi = round(float(m.weight_kg) / (float(m.height_cm) / 100) ** 2, 1)
    return {**to_dict(m), "conscript_name": m.conscript.name_kh, "result_name": MEDICAL_RESULTS.get(m.result), "bmi": bmi}


def _service_before(db, user, obj, data, is_new):
    _check_conscript(db, data["conscript_id"])
    if data.get("start_date") and data.get("end_date") and data["end_date"] < data["start_date"]:
        raise HTTPException(400, "ថ្ងៃបញ្ចប់ត្រូវនៅក្រោយថ្ងៃចាប់ផ្ដើម")
    if data.get("unit_id") and not db.get(Unit, data["unit_id"]):
        raise HTTPException(400, "អង្គភាពមិនត្រឹមត្រូវ")
    if data.get("rank_id") and not db.get(Rank, data["rank_id"]):
        raise HTTPException(400, "ឋានន្តរស័ក្តិមិនត្រឹមត្រូវ")


def service_out(sv: ConscriptService) -> dict:
    return {**to_dict(sv), "conscript_name": sv.conscript.name_kh,
            "unit_name": sv.unit.name_kh if sv.unit else sv.unit_text, "rank_name": sv.rank.name_kh if sv.rank else None}


router.include_router(crud_router(
    prefix="/conscript-registrations", model=ConscriptRegistration, module="conscripts", schema=ConscriptRegistrationIn,
    search_fields=(ConscriptRegistration.register_no,),
    filter_fields={"conscript_id": ConscriptRegistration.conscript_id, "status": ConscriptRegistration.status,
                   "registration_year": ConscriptRegistration.registration_year,
                   "province_id": ConscriptRegistration.province_id},
    order_by=(ConscriptRegistration.registration_year.desc(), ConscriptRegistration.id.desc()),
    serialize=registration_out, before_save=_registration_before, tags=["conscripts"],
))
router.include_router(crud_router(
    prefix="/conscript-medicals", model=ConscriptMedical, module="conscript_medical", schema=ConscriptMedicalIn,
    filter_fields={"conscript_id": ConscriptMedical.conscript_id, "result": ConscriptMedical.result},
    order_by=(ConscriptMedical.exam_date.desc(), ConscriptMedical.id.desc()),
    serialize=medical_out, before_save=lambda db, user, obj, data, is_new: _check_conscript(db, data["conscript_id"]),
    tags=["conscripts"],
))
router.include_router(crud_router(
    prefix="/conscript-services", model=ConscriptService, module="conscripts", schema=ConscriptServiceIn,
    filter_fields={"conscript_id": ConscriptService.conscript_id},
    order_by=(ConscriptService.start_date.desc(), ConscriptService.id.desc()),
    serialize=service_out, before_save=_service_before, tags=["conscripts"],
))


def registration_counts(db: Session, years: tuple[int, int]) -> dict:
    """{(province_id, status): count} of registrations in the year range (for the report)."""
    rows = db.execute(select(ConscriptRegistration.province_id, ConscriptRegistration.status, func.count())
                      .join(Conscript, Conscript.id == ConscriptRegistration.conscript_id)
                      .where(ConscriptRegistration.deleted_at.is_(None), Conscript.deleted_at.is_(None),
                             ConscriptRegistration.registration_year.between(*years))
                      .group_by(ConscriptRegistration.province_id, ConscriptRegistration.status)).all()
    return {(p, st): n for p, st, n in rows}
