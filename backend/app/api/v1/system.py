"""Auth, users, roles & permissions, system settings, audit log."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require
from app.core.permissions import ACTIONS, MODULES
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import AuditLog, Permission, Role, Setting, User
from app.schemas import ChangePasswordIn, LoginIn, RefreshIn, RoleIn, RolePermissionsIn, SettingsIn, UserIn
from app.services.common import audit, paginate, to_dict

router = APIRouter()


def user_out(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "full_name": u.full_name, "phone": u.phone,
        "role_id": u.role_id, "role_name": u.role.name, "is_super": u.role.is_super,
        "unit_scope_id": u.unit_scope_id, "unit_scope_name": u.unit_scope.name_kh if u.unit_scope else None,
        "active": u.active, "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


def me_out(u: User) -> dict:
    perms = sorted(f"{m}.{a}" for m in MODULES for a in ACTIONS) if u.role.is_super else sorted(u.permission_keys())
    return {**user_out(u), "permissions": perms}


# ---------------- auth ----------------

@router.post("/auth/login", tags=["auth"])
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    now = datetime.now()
    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(423, f"គណនីត្រូវបានចាក់សោបណ្ដោះអាសន្ន រហូតដល់ {user.locked_until:%H:%M}")
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= settings.MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
                user.failed_logins = 0
            db.commit()
        raise HTTPException(401, "ឈ្មោះអ្នកប្រើ ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវ")
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    audit(db, user, "login", table="users", record_id=user.id, request=request)
    db.commit()
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "user": me_out(user),
    }


@router.post("/auth/refresh", tags=["auth"])
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    user_id = decode_token(payload.refresh_token, "refresh")
    user = db.get(User, user_id) if user_id else None
    if not user or not user.active:
        raise HTTPException(401, "Refresh token មិនត្រឹមត្រូវ")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/auth/me", tags=["auth"])
def me(user: User = Depends(get_current_user)):
    return me_out(user)


@router.post("/auth/change-password", tags=["auth"])
def change_password(payload: ChangePasswordIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(400, "ពាក្យសម្ងាត់ចាស់មិនត្រឹមត្រូវ")
    user.password_hash = hash_password(payload.new_password)
    audit(db, user, "change_password", table="users", record_id=user.id, request=request)
    db.commit()
    return {"ok": True}


# ---------------- users ----------------

@router.get("/users", tags=["users"])
def list_users(page: int = Query(1, ge=1), size: int = Query(20, le=200), q: str | None = None,
               db: Session = Depends(get_db), _: User = Depends(require("users", "view"))):
    stmt = select(User)
    if q:
        stmt = stmt.where(or_(User.username.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    items, total = paginate(db, stmt.order_by(User.id), page, size)
    return {"items": [user_out(u) for u in items], "total": total, "page": page, "size": size}


def _apply_user(db: Session, u: User, data: UserIn, actor: User) -> None:
    role = db.get(Role, data.role_id)
    if not role:
        raise HTTPException(400, "តួនាទីមិនត្រឹមត្រូវ")
    if role.is_super and not actor.role.is_super:
        raise HTTPException(403, "មានតែ Super Admin ទេដែលអាចកំណត់តួនាទី Super Admin")
    u.username, u.full_name, u.phone = data.username, data.full_name, data.phone
    u.role_id, u.unit_scope_id, u.active = data.role_id, data.unit_scope_id, data.active
    if data.password:
        u.password_hash = hash_password(data.password)


@router.post("/users", tags=["users"], status_code=201)
def create_user(payload: UserIn, request: Request, db: Session = Depends(get_db),
                actor: User = Depends(require("users", "create"))):
    if not payload.password:
        raise HTTPException(400, "សូមបញ្ចូលពាក្យសម្ងាត់ (យ៉ាងតិច ៨ តួ)")
    u = User()
    _apply_user(db, u, payload, actor)
    db.add(u)
    try:
        db.flush()
        audit(db, actor, "create", table="users", record_id=u.id, request=request)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "ឈ្មោះអ្នកប្រើនេះមានរួចហើយ")
    db.refresh(u)
    return user_out(u)


@router.put("/users/{user_id}", tags=["users"])
def update_user(user_id: int, payload: UserIn, request: Request, db: Session = Depends(get_db),
                actor: User = Depends(require("users", "update"))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "រកមិនឃើញ")
    if u.role.is_super and not actor.role.is_super:
        raise HTTPException(403, "មិនអាចកែប្រែ Super Admin")
    if u.id == actor.id and not payload.active:
        raise HTTPException(400, "មិនអាចបិទគណនីខ្លួនឯងបានទេ")
    _apply_user(db, u, payload, actor)
    try:
        audit(db, actor, "update", table="users", record_id=u.id, request=request)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "ឈ្មោះអ្នកប្រើនេះមានរួចហើយ")
    db.refresh(u)
    return user_out(u)


@router.delete("/users/{user_id}", tags=["users"])
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db),
                actor: User = Depends(require("users", "delete"))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "រកមិនឃើញ")
    if u.id == actor.id or (u.role.is_super and not actor.role.is_super):
        raise HTTPException(400, "មិនអាចលុបគណនីនេះបានទេ")
    # keep history: deactivate rather than hard delete
    u.active = False
    audit(db, actor, "deactivate", table="users", record_id=u.id, request=request)
    db.commit()
    return {"ok": True}


# ---------------- roles & permissions ----------------

@router.get("/permissions/catalog", tags=["roles"])
def permission_catalog(_: User = Depends(get_current_user)):
    return {"modules": [{"key": k, "name": v} for k, v in MODULES.items()], "actions": ACTIONS}


@router.get("/roles", tags=["roles"])
def list_roles(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    roles = db.scalars(select(Role).order_by(Role.id)).all()
    return {"items": [{**to_dict(r), "permissions": sorted(p.key for p in r.permissions)} for r in roles],
            "total": len(roles)}


@router.post("/roles", tags=["roles"], status_code=201)
def create_role(payload: RoleIn, request: Request, db: Session = Depends(get_db),
                actor: User = Depends(require("roles", "create"))):
    r = Role(name=payload.name, description=payload.description)
    db.add(r)
    try:
        db.flush()
        audit(db, actor, "create", r, request=request)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "ឈ្មោះតួនាទីមានរួចហើយ")
    return to_dict(r)


@router.put("/roles/{role_id}", tags=["roles"])
def update_role(role_id: int, payload: RoleIn, request: Request, db: Session = Depends(get_db),
                actor: User = Depends(require("roles", "update"))):
    r = db.get(Role, role_id)
    if not r:
        raise HTTPException(404, "រកមិនឃើញ")
    r.name, r.description = payload.name, payload.description
    audit(db, actor, "update", r, request=request)
    db.commit()
    return to_dict(r)


@router.put("/roles/{role_id}/permissions", tags=["roles"])
def set_role_permissions(role_id: int, payload: RolePermissionsIn, request: Request, db: Session = Depends(get_db),
                         actor: User = Depends(require("roles", "update"))):
    r = db.get(Role, role_id)
    if not r:
        raise HTTPException(404, "រកមិនឃើញ")
    if r.is_super:
        raise HTTPException(400, "Super Admin មានសិទ្ធិទាំងអស់ដោយស្វ័យប្រវត្តិ")
    wanted = set(payload.permissions)
    before = {"permissions": sorted(p.key for p in r.permissions)}
    r.permissions = [p for p in db.scalars(select(Permission)) if p.key in wanted]
    audit(db, actor, "update_permissions", table="roles", record_id=r.id, before=before, request=request)
    db.commit()
    return {"ok": True, "count": len(r.permissions)}


@router.delete("/roles/{role_id}", tags=["roles"])
def delete_role(role_id: int, request: Request, db: Session = Depends(get_db),
                actor: User = Depends(require("roles", "delete"))):
    r = db.get(Role, role_id)
    if not r or r.is_super:
        raise HTTPException(400, "មិនអាចលុបតួនាទីនេះបានទេ")
    if db.scalar(select(User.id).where(User.role_id == role_id).limit(1)):
        raise HTTPException(409, "តួនាទីនេះកំពុងប្រើដោយអ្នកប្រើប្រាស់")
    db.delete(r)
    audit(db, actor, "delete", table="roles", record_id=role_id, request=request)
    db.commit()
    return {"ok": True}


# ---------------- settings ----------------

@router.get("/settings", tags=["settings"])
def get_settings(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return {s.key: {"value": s.value, "description": s.description} for s in db.scalars(select(Setting))}


@router.put("/settings", tags=["settings"])
def put_settings(payload: SettingsIn, request: Request, db: Session = Depends(get_db),
                 actor: User = Depends(require("settings", "update"))):
    for k, v in payload.values.items():
        s = db.get(Setting, k)
        if s:
            s.value = v
        else:
            db.add(Setting(key=k, value=v))
    audit(db, actor, "update", table="settings", record_id="*", request=request)
    db.commit()
    return {"ok": True}


def get_setting(db: Session, key: str, default: str = "") -> str:
    s = db.get(Setting, key)
    return s.value if s and s.value is not None else default


# ---------------- audit log ----------------

@router.get("/audit-logs", tags=["audit"])
def audit_logs(page: int = Query(1, ge=1), size: int = Query(50, le=200), table: str | None = None,
               user_id: int | None = None, action: str | None = None,
               db: Session = Depends(get_db), _: User = Depends(require("audit", "view"))):
    stmt = select(AuditLog)
    if table:
        stmt = stmt.where(AuditLog.table_name == table)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    items, total = paginate(db, stmt.order_by(AuditLog.id.desc()), page, size)
    return {
        "items": [{**to_dict(a), "username": a.user.username if a.user else None} for a in items],
        "total": total, "page": page, "size": size,
    }
