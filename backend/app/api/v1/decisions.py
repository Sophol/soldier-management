"""Appointment / transfer / promotion decisions (ការងារតែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងឋានន្តរស័ក្តិ).

A decision lists one or more soldiers with their new rank/position/unit. Nothing changes on the
soldier until the decision is approved; approving writes history + strength movements, cancelling
an approved decision reverts it (only if nothing newer has changed the soldier since).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permissions import DECISION_MODULE
from app.models import Decision, DecisionItem, Position, Rank, Soldier, SoldierHistory, StrengthMovement, Unit, User
from app.models.decision import DECISION_KINDS
from app.schemas import DecisionIn
from app.services.common import audit, paginate, scope_unit_ids, to_dict
from app.services.soldier import add_history, add_movement, diff_ym

router = APIRouter(prefix="/decisions", tags=["decisions"])


def _need(user: User, kind: str, action: str) -> None:
    module = DECISION_MODULE.get(kind)
    if not module or not user.can(module, action):
        raise HTTPException(403, f"គ្មានសិទ្ធិ: {module}.{action}")


def _names(db: Session, model, ids) -> dict:
    ids = {i for i in ids if i}
    return {o.id: o.name_kh for o in db.scalars(select(model).where(model.id.in_(ids)))} if ids else {}


def decision_out(db: Session, d: Decision, with_items: bool = True) -> dict:
    out = {**to_dict(d), "kind_name": DECISION_KINDS.get(d.kind), "item_count": len(d.items)}
    if with_items:
        ranks = _names(db, Rank, [i.old_rank_id for i in d.items] + [i.new_rank_id for i in d.items])
        poss = _names(db, Position, [i.old_position_id for i in d.items] + [i.new_position_id for i in d.items])
        units = _names(db, Unit, [i.old_unit_id for i in d.items] + [i.new_unit_id for i in d.items])
        out["items"] = [{
            **to_dict(i),
            "military_id": i.soldier.military_id, "name_kh": i.soldier.name_kh, "name_latin": i.soldier.name_latin,
            "gender": i.soldier.gender,
            "date_of_birth": i.soldier.date_of_birth.isoformat() if i.soldier.date_of_birth else None,
            "old_rank": ranks.get(i.old_rank_id), "new_rank": ranks.get(i.new_rank_id),
            "old_position": poss.get(i.old_position_id), "new_position": poss.get(i.new_position_id),
            "old_unit": units.get(i.old_unit_id), "new_unit": units.get(i.new_unit_id),
        } for i in d.items]
    return out


def _validate_items(db: Session, user: User, payload: DecisionIn) -> tuple[list[DecisionItem], list[str]]:
    items, warnings, seen = [], [], set()
    scope = scope_unit_ids(db, user)
    for it in payload.items:
        if it.soldier_id in seen:
            raise HTTPException(400, "យោធិនម្នាក់ត្រូវបានបញ្ចូលច្រើនដង")
        seen.add(it.soldier_id)
        s = db.get(Soldier, it.soldier_id)
        if not s or s.deleted_at:
            raise HTTPException(400, f"រកមិនឃើញយោធិន id={it.soldier_id}")
        if scope is not None and s.current_unit_id not in scope:
            raise HTTPException(403, f"{s.name_kh}: នៅក្រៅសិទ្ធិរបស់អ្នក")
        label = f"{s.name_kh} ({s.military_id})"
        if payload.kind == "promote":
            if not it.new_rank_id:
                raise HTTPException(400, f"{label}: សូមជ្រើសរើសឋានន្តរស័ក្តិថ្មី")
            new_rank = db.get(Rank, it.new_rank_id)
            if not new_rank or not new_rank.active:
                raise HTTPException(400, f"{label}: ឋានន្តរស័ក្តិថ្មីមិនត្រឹមត្រូវ")
            if s.rank and new_rank.sort_order <= s.rank.sort_order:
                raise HTTPException(400, f"{label}: ឋានន្តរស័ក្តិថ្មីត្រូវតែខ្ពស់ជាងឋានន្តរស័ក្តិបច្ចុប្បន្ន ({s.rank.name_kh})")
            if s.rank and s.rank.min_years_to_next:
                ym = diff_ym(s.rank_date, payload.effective_date)
                if ym is None or ym[0] < s.rank.min_years_to_next:
                    warnings.append(f"{label}: រយៈពេលឡើងស័ក្តិមិនទាន់គ្រប់ {s.rank.min_years_to_next} ឆ្នាំ")
        elif payload.kind == "appoint":
            if not it.new_position_id:
                raise HTTPException(400, f"{label}: សូមជ្រើសរើសមុខតំណែងថ្មី")
        elif payload.kind == "transfer":
            if not it.new_unit_id and not it.new_position_id:
                raise HTTPException(400, f"{label}: សូមជ្រើសរើសអង្គភាព ឬមុខតំណែងថ្មី")
        if it.new_unit_id:
            u = db.get(Unit, it.new_unit_id)
            if not u or not u.active:
                raise HTTPException(400, f"{label}: អង្គភាពថ្មីមិនត្រឹមត្រូវ")
        if it.new_position_id:
            p = db.get(Position, it.new_position_id)
            if not p or not p.active:
                raise HTTPException(400, f"{label}: មុខតំណែងថ្មីមិនត្រឹមត្រូវ")
        items.append(DecisionItem(
            soldier_id=s.id, old_rank_id=s.current_rank_id, old_position_id=s.current_position_id,
            old_unit_id=s.current_unit_id, new_rank_id=it.new_rank_id if payload.kind == "promote" else None,
            new_position_id=it.new_position_id, new_unit_id=it.new_unit_id, note=it.note,
        ))
    return items, warnings


@router.get("")
def list_decisions(kind: str, page: int = Query(1, ge=1), size: int = Query(20, le=200), q: str | None = None,
                   status: str | None = None, date_from: str | None = None, date_to: str | None = None,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _need(user, kind, "view")
    stmt = select(Decision).where(Decision.kind == kind, Decision.deleted_at.is_(None))
    if q:
        stmt = stmt.where(or_(Decision.decision_no.ilike(f"%{q}%"), Decision.notes.ilike(f"%{q}%"),
                              Decision.id.in_(select(DecisionItem.decision_id).join(Soldier).where(
                                  or_(Soldier.name_kh.ilike(f"%{q}%"), Soldier.military_id.ilike(f"%{q}%"))))))
    if status:
        stmt = stmt.where(Decision.status == status)
    if date_from:
        stmt = stmt.where(Decision.decision_date >= date_from)
    if date_to:
        stmt = stmt.where(Decision.decision_date <= date_to)
    items, total = paginate(db, stmt.order_by(Decision.decision_date.desc(), Decision.id.desc()), page, size)
    return {"items": [decision_out(db, d, with_items=False) for d in items], "total": total, "page": page, "size": size}


def _get(db: Session, decision_id: int) -> Decision:
    d = db.get(Decision, decision_id)
    if not d or d.deleted_at:
        raise HTTPException(404, "រកមិនឃើញសេចក្ដីសម្រេច")
    return d


@router.get("/{decision_id}")
def get_decision(decision_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = _get(db, decision_id)
    _need(user, d.kind, "view")
    return decision_out(db, d)


@router.post("", status_code=201)
def create_decision(payload: DecisionIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    _need(user, payload.kind, "create")
    items, warnings = _validate_items(db, user, payload)
    d = Decision(**payload.model_dump(exclude={"items"}), status="draft", created_by=user.id)
    d.items = items
    db.add(d)
    db.flush()
    audit(db, user, "create", d, request=request)
    db.commit()
    return {**decision_out(db, d), "warnings": warnings}


@router.put("/{decision_id}")
def update_decision(decision_id: int, payload: DecisionIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    d = _get(db, decision_id)
    _need(user, d.kind, "update")
    if d.status != "draft":
        raise HTTPException(400, "អាចកែប្រែបានតែសេចក្ដីសម្រេចព្រាងប៉ុណ្ណោះ")
    if payload.kind != d.kind:
        raise HTTPException(400, "មិនអាចប្ដូរប្រភេទសេចក្ដីសម្រេចបានទេ")
    items, warnings = _validate_items(db, user, payload)
    before = to_dict(d)
    for k, v in payload.model_dump(exclude={"items", "kind"}).items():
        setattr(d, k, v)
    d.items = items
    d.updated_by = user.id
    audit(db, user, "update", d, before=before, request=request)
    db.commit()
    return {**decision_out(db, d), "warnings": warnings}


@router.delete("/{decision_id}")
def delete_decision(decision_id: int, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    d = _get(db, decision_id)
    _need(user, d.kind, "delete")
    if d.status == "approved":
        raise HTTPException(400, "សេចក្ដីសម្រេចដែលបានអនុម័ត ត្រូវលុបចោល (cancel) ជាមុនសិន")
    d.deleted_at = datetime.now()
    audit(db, user, "delete", table="decisions", record_id=d.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/{decision_id}/approve")
def approve_decision(decision_id: int, request: Request, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    d = _get(db, decision_id)
    _need(user, d.kind, "approve")
    if d.status != "draft":
        raise HTTPException(400, "សេចក្ដីសម្រេចនេះមិនមែនជាសេចក្ដីព្រាងទេ")
    eff = d.effective_date
    for it in d.items:
        s = db.get(Soldier, it.soldier_id)
        if not s or s.deleted_at:
            raise HTTPException(400, f"យោធិន id={it.soldier_id} មិនមានទៀតទេ")
        # snapshot the state at approval time (it may have changed since the draft was made)
        it.old_rank_id, it.old_position_id, it.old_unit_id = s.current_rank_id, s.current_position_id, s.current_unit_id
        it.old_rank_date, it.old_position_date = s.rank_date, s.position_date
        it.old_unit_date, it.old_from_unit_text = s.unit_transfer_date, s.from_unit_text
        if it.new_rank_id:
            s.current_rank_id, s.rank_date = it.new_rank_id, eff
        if it.new_position_id:
            s.current_position_id, s.position_date = it.new_position_id, eff
        if it.new_unit_id and it.new_unit_id != s.current_unit_id:
            if s.current_unit_id:
                add_movement(db, s.id, s.current_unit_id, "out", "transfer_out", eff, "decisions", d.id)
            add_movement(db, s.id, it.new_unit_id, "in", "transfer_in", eff, "decisions", d.id)
            s.from_unit_text = s.unit.name_kh if s.unit else s.from_unit_text
            s.current_unit_id, s.unit_transfer_date = it.new_unit_id, eff
        s.updated_by = user.id
        add_history(db, s, d.kind, eff, old_rank=it.old_rank_id, new_rank=it.new_rank_id or None,
                    old_position=it.old_position_id, new_position=it.new_position_id,
                    old_unit=it.old_unit_id, new_unit=it.new_unit_id, decision_id=d.id,
                    note=f"{DECISION_KINDS[d.kind]} លេខ {d.decision_no}")
    d.status, d.approved_by, d.approved_at = "approved", user.id, datetime.now()
    audit(db, user, "approve", d, request=request)
    db.commit()
    return decision_out(db, d)


@router.post("/{decision_id}/cancel")
def cancel_decision(decision_id: int, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    d = _get(db, decision_id)
    _need(user, d.kind, "approve")
    if d.status == "cancelled":
        raise HTTPException(400, "សេចក្ដីសម្រេចនេះត្រូវបានលុបចោលរួចហើយ")
    if d.status == "approved":
        for it in d.items:
            s = db.get(Soldier, it.soldier_id)
            newer = db.scalar(select(SoldierHistory.id).where(
                SoldierHistory.soldier_id == s.id, SoldierHistory.decision_id != d.id,
                SoldierHistory.created_at > d.approved_at).limit(1))
            if newer:
                raise HTTPException(409, f"{s.name_kh}: មានការផ្លាស់ប្ដូរថ្មីជាងនេះ មិនអាចត្រឡប់វិញបានទេ")
        for it in d.items:
            s = db.get(Soldier, it.soldier_id)
            if it.new_rank_id:
                s.current_rank_id, s.rank_date = it.old_rank_id, it.old_rank_date
            if it.new_position_id:
                s.current_position_id, s.position_date = it.old_position_id, it.old_position_date
            if it.new_unit_id:
                s.current_unit_id, s.unit_transfer_date = it.old_unit_id, it.old_unit_date
                s.from_unit_text = it.old_from_unit_text
        db.execute(delete(SoldierHistory).where(SoldierHistory.decision_id == d.id))
        db.execute(delete(StrengthMovement).where(StrengthMovement.source_table == "decisions",
                                                  StrengthMovement.source_id == d.id))
    d.status = "cancelled"
    audit(db, user, "cancel", d, request=request)
    db.commit()
    return decision_out(db, d)
