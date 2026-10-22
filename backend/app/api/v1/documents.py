"""Incoming / outgoing official documents (ឯកសារគតិយុទ្ធ) and shared file attachments."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from app.api.crud import crud_router
from app.api.v1.system import get_setting
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import DocumentFile, DocumentIncoming, DocumentOutgoing, DocumentType, Unit, User
from app.schemas import DocumentInIn, DocumentOutIn
from app.services.common import audit, delete_storage_file, save_upload, storage_file, to_dict

router = APIRouter()

# owner_type -> permission module for attachments
FILE_OWNERS = {
    "doc_in": "doc_in",
    "doc_out": "doc_out",
    "decision": "decisions_promote",  # checked more precisely below
    "training": "training",
    "discipline": "discipline",
    "award": "awards",
    "retirement": "retirement",
    "separation": "separation",
    "conscript": "conscripts",  # scanned record (ស្កេនប្រវត្តិរូប), exemption papers
}


def file_count(obj, owner_type: str) -> int:
    db = object_session(obj)
    return db.scalar(select(func.count(DocumentFile.id)).where(
        DocumentFile.owner_type == owner_type, DocumentFile.owner_id == obj.id)) or 0


def doc_in_out(d: DocumentIncoming) -> dict:
    unit = object_session(d).get(Unit, d.from_unit_id) if d.from_unit_id else None
    return {**to_dict(d), "document_type_name": d.document_type.name_kh if d.document_type else None,
            "from_unit_name": unit.name_kh if unit else d.from_unit, "file_count": file_count(d, "doc_in")}


def doc_out_out(d: DocumentOutgoing) -> dict:
    return {**to_dict(d), "document_type_name": d.document_type.name_kh if d.document_type else None,
            "unit_name": d.unit.name_kh if d.unit else None, "file_count": file_count(d, "doc_out")}


def _doc_in_before(db, user, obj, data, is_new):
    data["year"] = data["doc_date"].year
    if data.get("from_unit_id"):  # a unit of the tree; the text field stays for senders outside it
        unit = db.get(Unit, data["from_unit_id"])
        if not unit:
            raise HTTPException(400, "អង្គភាពមិនត្រឹមត្រូវ")
        data["from_unit"] = data.get("from_unit") or unit.name_kh


def allocate_outgoing_number(db: Session, year: int) -> tuple[int, str]:
    """Next sequence number of the year and its formatted document number."""
    seq = (db.scalar(select(func.max(DocumentOutgoing.seq)).where(DocumentOutgoing.year == year)) or 0) + 1
    fmt = get_setting(db, "outgoing_number_format", "{seq}/{yy}")
    return seq, fmt.format(seq=seq, yyyy=year, yy=str(year)[-2:])


def _doc_out_before(db: Session, user, obj, data, is_new):
    year = data["doc_date"].year
    data["year"] = year
    if not data.get("outgoing_no"):
        if not is_new and obj.outgoing_no and obj.year == year:
            data["outgoing_no"] = obj.outgoing_no
            return
        data["seq"], data["outgoing_no"] = allocate_outgoing_number(db, year)


@router.get("/documents/by-type", tags=["documents"])
def documents_by_type(year: int | None = None, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """ឯកសារគតិយុទ្ធ: incoming and outgoing documents counted per document type."""
    if not (user.can("doc_in", "view") or user.can("doc_out", "view")):
        raise HTTPException(403, "គ្មានសិទ្ធិ")
    counts = {}
    for key, model in (("incoming", DocumentIncoming), ("outgoing", DocumentOutgoing)):
        stmt = select(model.document_type_id, func.count(model.id)).where(model.deleted_at.is_(None))
        if year:
            stmt = stmt.where(model.year == year)
        counts[key] = dict(db.execute(stmt.group_by(model.document_type_id)).all())
    types = db.scalars(select(DocumentType).order_by(DocumentType.id)).all()
    rows = [{"id": t.id, "name_kh": t.name_kh, "direction": t.direction, "active": t.active,
             "incoming": counts["incoming"].get(t.id, 0), "outgoing": counts["outgoing"].get(t.id, 0)} for t in types]
    if counts["incoming"].get(None) or counts["outgoing"].get(None):
        rows.append({"id": None, "name_kh": "មិនបានកំណត់ប្រភេទ", "direction": "both", "active": True,
                     "incoming": counts["incoming"].get(None, 0), "outgoing": counts["outgoing"].get(None, 0)})
    return rows


@router.get("/documents/outgoing/next-number", tags=["documents"])
def next_outgoing_number(year: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    seq, number = allocate_outgoing_number(db, year)
    return {"seq": seq, "number": number}


router.include_router(crud_router(
    prefix="/documents/incoming", model=DocumentIncoming, module="doc_in", schema=DocumentInIn,
    search_fields=(DocumentIncoming.incoming_no, DocumentIncoming.subject, DocumentIncoming.from_unit),
    filter_fields={"document_type_id": DocumentIncoming.document_type_id, "year": DocumentIncoming.year,
                   "from_unit_id": DocumentIncoming.from_unit_id,
                   "date_from": DocumentIncoming.doc_date, "date_to": DocumentIncoming.doc_date,
                   "status": DocumentIncoming.status},
    order_by=(DocumentIncoming.doc_date.desc(), DocumentIncoming.id.desc()),
    serialize=doc_in_out, before_save=_doc_in_before, tags=["documents"],
))
router.include_router(crud_router(
    prefix="/documents/outgoing", model=DocumentOutgoing, module="doc_out", schema=DocumentOutIn,
    search_fields=(DocumentOutgoing.outgoing_no, DocumentOutgoing.subject, DocumentOutgoing.recipient_name),
    filter_fields={"document_type_id": DocumentOutgoing.document_type_id, "year": DocumentOutgoing.year,
                   "unit_id": DocumentOutgoing.unit_id, "date_from": DocumentOutgoing.doc_date,
                   "date_to": DocumentOutgoing.doc_date, "status": DocumentOutgoing.status},
    order_by=(DocumentOutgoing.doc_date.desc(), DocumentOutgoing.id.desc()),
    serialize=doc_out_out, before_save=_doc_out_before, tags=["documents"],
))


# ---------------- shared attachments ----------------

def _check_file_perm(user: User, owner_type: str, action: str) -> None:
    if owner_type not in FILE_OWNERS:
        raise HTTPException(400, "owner_type មិនត្រឹមត្រូវ")
    # attaching files is allowed with either create or update permission
    actions = ("create", "update") if action == "update" else (action,)
    modules = ("decisions_appoint", "decisions_transfer", "decisions_promote") if owner_type == "decision" \
        else (FILE_OWNERS[owner_type],)
    ok = any(user.can(m, a) for m in modules for a in actions)
    if not ok:
        raise HTTPException(403, "គ្មានសិទ្ធិ")


# must be registered before /files/{owner_type}/{owner_id}, which would otherwise match "download"
@router.get("/files/download/{file_id}", tags=["files"])
def download_file(file_id: int, inline: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = db.get(DocumentFile, file_id)
    if not f:
        raise HTTPException(404, "រកមិនឃើញ")
    _check_file_perm(user, f.owner_type, "view")
    return FileResponse(storage_file(f.file_path), filename=f.file_name,
                        content_disposition_type="inline" if inline else "attachment")


@router.get("/files/{owner_type}/{owner_id}", tags=["files"])
def list_files(owner_type: str, owner_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    _check_file_perm(user, owner_type, "view")
    rows = db.scalars(select(DocumentFile).where(DocumentFile.owner_type == owner_type,
                                                 DocumentFile.owner_id == owner_id).order_by(DocumentFile.id))
    return [to_dict(f) for f in rows]


@router.post("/files/{owner_type}/{owner_id}", tags=["files"], status_code=201)
def upload_file(owner_type: str, owner_id: int, request: Request, file: UploadFile = File(...),
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_file_perm(user, owner_type, "update")
    path, size = save_upload(file, owner_type)
    f = DocumentFile(owner_type=owner_type, owner_id=owner_id, file_path=path,
                     file_name=file.filename or "file", file_size=size, uploaded_by=user.id)
    db.add(f)
    db.flush()
    audit(db, user, "upload", f, request=request)
    db.commit()
    return to_dict(f)


@router.delete("/files/{file_id}", tags=["files"])
def delete_file(file_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = db.get(DocumentFile, file_id)
    if not f:
        raise HTTPException(404, "រកមិនឃើញ")
    _check_file_perm(user, f.owner_type, "update")
    delete_storage_file(f.file_path)
    db.delete(f)
    audit(db, user, "delete", table="document_files", record_id=file_id, request=request)
    db.commit()
    return {"ok": True}
