"""Generic list/get/create/update/delete router for simple tables."""

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require
from app.models import User
from app.services.common import audit, paginate, to_dict


def crud_router(
    *,
    prefix: str,
    model,
    module: str,
    schema: type[BaseModel],
    search_fields: tuple = (),
    filter_fields: dict | None = None,
    order_by: tuple = (),
    serialize: Callable | None = None,
    public_read: bool = False,
    base_query: Callable | None = None,
    before_save: Callable | None = None,
    after_save: Callable | None = None,
    after_delete: Callable | None = None,
    tags: list[str] | None = None,
) -> APIRouter:
    """
    filter_fields: {"query_param": column}
    base_query(stmt, db, user) -> stmt   : extra filtering (e.g. unit scope)
    before_save(db, user, obj, data, is_new): validation / derived fields
    after_save(db, user, obj, is_new): side effects (e.g. strength movements)
    after_delete(db, user, obj): undo side effects
    """
    router = APIRouter(prefix=prefix, tags=tags or [prefix.strip("/")])
    filter_fields = filter_fields or {}
    soft = hasattr(model, "deleted_at")
    ser = serialize or (lambda o: to_dict(o))
    read_dep = get_current_user if public_read else require(module, "view")

    def _base(db: Session, user: User):
        stmt = select(model)
        if soft:
            stmt = stmt.where(model.deleted_at.is_(None))
        if base_query:
            stmt = base_query(stmt, db, user)
        return stmt

    def _get(db: Session, user: User, item_id: int):
        obj = db.scalars(_base(db, user).where(model.id == item_id)).unique().first()
        if not obj:
            raise HTTPException(404, "រកមិនឃើញទិន្នន័យ")
        return obj

    @router.get("")
    def list_items(
        request: Request,
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=1000),
        q: str | None = None,
        db: Session = Depends(get_db),
        user: User = Depends(read_dep),
    ):
        stmt = _base(db, user)
        if q and search_fields:
            stmt = stmt.where(or_(*[f.ilike(f"%{q}%") for f in search_fields]))
        for param, col in filter_fields.items():
            val = request.query_params.get(param)
            if val not in (None, ""):
                if param.endswith("_from"):
                    stmt = stmt.where(col >= val)
                elif param.endswith("_to"):
                    stmt = stmt.where(col <= val)
                else:
                    stmt = stmt.where(col == val)
        stmt = stmt.order_by(*(order_by or (model.id.desc(),)))
        items, total = paginate(db, stmt, page, size)
        return {"items": [ser(i) for i in items], "total": total, "page": page, "size": size}

    @router.get("/{item_id}")
    def get_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(read_dep)):
        return ser(_get(db, user, item_id))

    @router.post("", status_code=201)
    def create_item(payload: schema, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(require(module, "create"))):
        data = payload.model_dump()
        obj = model()
        if before_save:
            before_save(db, user, obj, data, True)
        for k, v in data.items():
            setattr(obj, k, v)
        if hasattr(model, "created_by"):
            obj.created_by = user.id
        db.add(obj)
        try:
            db.flush()
            if after_save:
                after_save(db, user, obj, True)
            audit(db, user, "create", obj, request=request)
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(409, f"ទិន្នន័យស្ទួន ឬមិនត្រឹមត្រូវ: {e.orig.args[-1] if e.orig else e}")
        db.refresh(obj)
        return ser(obj)

    @router.put("/{item_id}")
    def update_item(item_id: int, payload: schema, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(require(module, "update"))):
        obj = _get(db, user, item_id)
        before = to_dict(obj)
        data = payload.model_dump()
        if before_save:
            before_save(db, user, obj, data, False)
        for k, v in data.items():
            setattr(obj, k, v)
        if hasattr(model, "updated_by"):
            obj.updated_by = user.id
        try:
            db.flush()
            if after_save:
                after_save(db, user, obj, False)
            audit(db, user, "update", obj, before=before, request=request)
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(409, f"ទិន្នន័យស្ទួន ឬមិនត្រឹមត្រូវ: {e.orig.args[-1] if e.orig else e}")
        db.refresh(obj)
        return ser(obj)

    @router.delete("/{item_id}")
    def delete_item(item_id: int, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(require(module, "delete"))):
        obj = _get(db, user, item_id)
        before = to_dict(obj)
        try:
            if soft:
                obj.deleted_at = datetime.now()
            else:
                db.delete(obj)
            db.flush()
            if after_delete:
                after_delete(db, user, obj)
            audit(db, user, "delete", before=before, table=model.__tablename__, record_id=item_id, request=request)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "មិនអាចលុបបានទេ ព្រោះទិន្នន័យនេះកំពុងត្រូវបានប្រើប្រាស់")
        return {"ok": True}

    return router
