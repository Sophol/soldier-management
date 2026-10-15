"""Shared helpers: serialisation, audit logging, unit scope, file storage, paging."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy import Select, func, inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuditLog, Unit, User

ALLOWED_UPLOAD_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".doc", ".docx", ".xls", ".xlsx"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _jsonable(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def to_dict(obj, exclude: set[str] | None = None) -> dict:
    exclude = exclude or set()
    return {
        c.key: _jsonable(getattr(obj, c.key))
        for c in inspect(obj).mapper.column_attrs
        if c.key not in exclude
    }


def names_by_id(db: Session, model, ids) -> dict:
    """{id: name_kh} for the given ids of a model with a name_kh column (None ids ignored)."""
    ids = {i for i in ids if i}
    return {o.id: o.name_kh for o in db.scalars(select(model).where(model.id.in_(ids)))} if ids else {}


def audit(db: Session, user: User | None, action: str, obj=None, before: dict | None = None,
          request: Request | None = None, table: str | None = None, record_id=None) -> None:
    after = to_dict(obj) if obj is not None and action != "delete" else None
    db.add(AuditLog(
        user_id=user.id if user else None,
        action=action,
        table_name=table or (obj.__tablename__ if obj is not None else "-"),
        record_id=str(record_id if record_id is not None else getattr(obj, "id", "")),
        before=before,
        after=after,
        ip=request.client.host if request and request.client else None,
    ))


def paginate(db: Session, stmt: Select, page: int, size: int) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset((page - 1) * size).limit(size)).unique().all()
    return list(rows), total or 0


# ---------- unit scope ----------

def unit_subtree_ids(db: Session, unit_id: int) -> list[int]:
    unit = db.get(Unit, unit_id)
    if not unit:
        return []
    return list(db.scalars(select(Unit.id).where(Unit.path.like(f"{unit.path}%"))))


def scope_unit_ids(db: Session, user: User) -> list[int] | None:
    """None = no restriction; otherwise the ids the user may see."""
    if user.role.is_super or not user.unit_scope_id:
        return None
    return unit_subtree_ids(db, user.unit_scope_id)


def check_unit_in_scope(db: Session, user: User, unit_id: int | None) -> None:
    ids = scope_unit_ids(db, user)
    if ids is not None and unit_id not in ids:
        raise HTTPException(403, "អង្គភាពនេះនៅក្រៅសិទ្ធិរបស់អ្នក")


# ---------- files ----------

def save_upload(file: UploadFile, folder: str, images_only: bool = False) -> tuple[str, int]:
    ext = Path(file.filename or "").suffix.lower()
    allowed = IMAGE_EXT if images_only else ALLOWED_UPLOAD_EXT
    if ext not in allowed:
        raise HTTPException(400, f"ប្រភេទឯកសារមិនអនុញ្ញាត ({ext}). អនុញ្ញាត: {', '.join(sorted(allowed))}")
    data = file.file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"ឯកសារធំពេក (អតិបរមា {settings.MAX_UPLOAD_MB}MB)")
    sub = Path(folder) / datetime.now().strftime("%Y/%m")
    target_dir = settings.storage_path / sub
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (target_dir / name).write_bytes(data)
    return str(sub / name), len(data)


def storage_file(rel_path: str) -> Path:
    root = settings.storage_path.resolve()
    p = (root / rel_path).resolve()
    if not p.is_relative_to(root) or not p.is_file():
        raise HTTPException(404, "រកមិនឃើញឯកសារ")
    return p


def delete_storage_file(rel_path: str | None) -> None:
    if not rel_path:
        return
    try:
        storage_file(rel_path).unlink()
    except HTTPException:
        pass
