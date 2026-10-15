"""Appointment / transfer / promotion decisions (ការងារតែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងឋានន្តរស័ក្តិ).

A decision lists one or more soldiers with their new rank/position/unit and goes through the approval
workflow (answer.txt): draft -> review by a specialist -> deputy chief of office -> chief of office ->
deputy director -> director -> top leadership -> approved -> published. Each level approves, returns
(one step back, with a reason) or rejects (with a reason); every step is logged in decision_steps.
Nothing changes on the soldier until the decision is published (outgoing letter registered); publishing
writes history + strength movements, cancelling a published decision reverts it (only if nothing newer
has changed the soldier since).
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.documents import allocate_outgoing_number
from app.api.v1.system import get_setting
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permissions import DECISION_MODULE, DECISION_STATUSES, FLOW, WORKFLOW_STAGES
from app.models import (
    Decision,
    DecisionItem,
    DecisionStep,
    DocumentIncoming,
    DocumentOutgoing,
    DocumentType,
    Position,
    Rank,
    Soldier,
    SoldierHistory,
    StrengthMovement,
    Unit,
    User,
)
from app.models.decision import DECISION_KINDS
from app.schemas import DecisionIn, PublishIn, WorkflowStepIn
from app.services.common import audit, names_by_id, paginate, scope_unit_ids, to_dict
from app.services.soldier import add_history, add_movement, diff_ym, is_inactive
from app.services.staffing import staffing_warnings

router = APIRouter(prefix="/decisions", tags=["decisions"])


def _need(user: User, kind: str, action: str) -> None:
    module = DECISION_MODULE.get(kind)
    if not module or not user.can(module, action):
        raise HTTPException(403, f"គ្មានសិទ្ធិ: {module}.{action}")


IN_PROGRESS = (*WORKFLOW_STAGES, "approved")  # waiting for someone to act
STATUS_ACTIONS = {"draft": ("edit", "submit", "delete"), **dict.fromkeys(WORKFLOW_STAGES, ("approve", "return", "reject")),
                  "approved": ("publish",), "published": ("cancel",), "rejected": ("delete",)}


def allowed_actions(user: User, d: Decision) -> list[str]:
    """What this user may do with the decision now (the UI shows only these buttons)."""
    module = DECISION_MODULE[d.kind]
    if d.status == "draft":
        acts = ["edit", "submit"] if user.can(module, "update") else []
        return acts + (["delete"] if user.can(module, "delete") else [])
    if d.status in WORKFLOW_STAGES:
        return ["approve", "return", "reject"] if user.can(f"wf_{d.status}", "approve") else []
    if d.status == "approved":
        return ["publish"] if user.can("wf_publish", "approve") else []
    if d.status == "published":
        return ["cancel"] if user.can(module, "approve") else []
    if d.status == "rejected":
        return ["delete"] if user.can(module, "delete") else []
    return []


def overdue_cutoff(db: Session) -> datetime:
    return datetime.now() - timedelta(days=int(get_setting(db, "workflow_overdue_days", "3") or 3))


def decision_out(db: Session, d: Decision, with_items: bool = True, user: User | None = None,
                 overdue_before: datetime | None = None) -> dict:
    overdue_before = overdue_before or overdue_cutoff(db)
    out = {**to_dict(d), "kind_name": DECISION_KINDS.get(d.kind), "item_count": len(d.items),
           "status_name": DECISION_STATUSES.get(d.status, d.status),
           "overdue": d.status in IN_PROGRESS and d.status_changed_at is not None and d.status_changed_at < overdue_before,
           "actions": allowed_actions(user, d) if user else [],
           "incoming_no": db.scalar(select(DocumentIncoming.incoming_no).where(
               DocumentIncoming.id == d.incoming_document_id)) if d.incoming_document_id else None,
           "outgoing_no": db.scalar(select(DocumentOutgoing.outgoing_no).where(
               DocumentOutgoing.id == d.outgoing_document_id)) if d.outgoing_document_id else None}
    if with_items:
        ranks = names_by_id(db, Rank, [i.old_rank_id for i in d.items] + [i.new_rank_id for i in d.items])
        poss = names_by_id(db, Position, [i.old_position_id for i in d.items] + [i.new_position_id for i in d.items])
        units = names_by_id(db, Unit, [i.old_unit_id for i in d.items] + [i.new_unit_id for i in d.items])
        out["items"] = [{
            **to_dict(i),
            "military_id": i.soldier.military_id, "name_kh": i.soldier.name_kh, "name_latin": i.soldier.name_latin,
            "gender": i.soldier.gender,
            "date_of_birth": i.soldier.date_of_birth.isoformat() if i.soldier.date_of_birth else None,
            "old_rank": ranks.get(i.old_rank_id), "new_rank": ranks.get(i.new_rank_id),
            "old_position": poss.get(i.old_position_id), "new_position": poss.get(i.new_position_id),
            "old_unit": units.get(i.old_unit_id), "new_unit": units.get(i.new_unit_id),
        } for i in d.items]
        out["steps"] = [{**to_dict(st), "user_name": st.user.full_name if st.user else None,
                         "from_name": DECISION_STATUSES.get(st.from_status), "to_name": DECISION_STATUSES.get(st.to_status)}
                        for st in d.steps]
    return out


def _in_scope_condition(db: Session, user: User):
    """SQL condition: the decision lists at least one soldier of the user's units (None = no unit limit)."""
    scope = scope_unit_ids(db, user)
    if scope is None:
        return None
    return Decision.id.in_(select(DecisionItem.decision_id).join(Soldier, Soldier.id == DecisionItem.soldier_id).where(
        or_(Soldier.current_unit_id.in_(scope), DecisionItem.old_unit_id.in_(scope))))


def _check_scope(db: Session, user: User, d: Decision, *, allow_old_unit: bool = False) -> None:
    """Acting on a decision needs every soldier in it to be within the user's units. When cancelling, the unit
    before the decision also counts (an approved transfer may have moved the soldier out of the user's units)."""
    scope = scope_unit_ids(db, user)
    if scope is None:
        return
    for it in d.items:
        s = db.get(Soldier, it.soldier_id)
        if s.current_unit_id not in scope and not (allow_old_unit and it.old_unit_id in scope):
            raise HTTPException(403, f"{s.name_kh}: នៅក្រៅសិទ្ធិរបស់អ្នក")


def _check_change(db: Session, s: Soldier, kind: str, new_rank_id, new_position_id, new_unit_id, label: str) -> None:
    """Rules that must hold both when the draft is saved and again when it is approved
    (the soldier may have been promoted, moved or retired in between)."""
    if is_inactive(db, s):
        raise HTTPException(400, f"{label}: យោធិននេះបានចូលនិវត្តន៍ ឬចេញពីជួររួចហើយ")
    if kind == "promote" or new_rank_id:  # transfers may promote at the same time
        new_rank = db.get(Rank, new_rank_id) if new_rank_id else None
        if not new_rank or not new_rank.active:
            raise HTTPException(400, f"{label}: ឋានន្តរស័ក្តិថ្មីមិនត្រឹមត្រូវ")
        cur = db.get(Rank, s.current_rank_id) if s.current_rank_id else None
        if cur and new_rank.sort_order <= cur.sort_order:
            raise HTTPException(400, f"{label}: ឋានន្តរស័ក្តិថ្មីត្រូវតែខ្ពស់ជាងឋានន្តរស័ក្តិបច្ចុប្បន្ន ({cur.name_kh})")
        if cur and "all" not in (cur.branch, new_rank.branch) and cur.branch != new_rank.branch:
            raise HTTPException(400, f"{label}: មិនអាចដំឡើងពីស័ក្តិជើងគោក ទៅស័ក្តិជើងទឹក (ឬផ្ទុយមកវិញ) បានទេ")
    if new_unit_id:
        u = db.get(Unit, new_unit_id)
        if not u or not u.active:
            raise HTTPException(400, f"{label}: អង្គភាពថ្មីមិនត្រឹមត្រូវ")
    if new_position_id:
        p = db.get(Position, new_position_id)
        if not p or not p.active:
            raise HTTPException(400, f"{label}: មុខតំណែងថ្មីមិនត្រឹមត្រូវ")


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
        new_rank_id = it.new_rank_id if payload.kind in ("promote", "transfer") else None
        if payload.kind == "promote" and not new_rank_id:
            raise HTTPException(400, f"{label}: សូមជ្រើសរើសឋានន្តរស័ក្តិថ្មី")
        if payload.kind == "appoint" and not it.new_position_id:
            raise HTTPException(400, f"{label}: សូមជ្រើសរើសមុខតំណែងថ្មី")
        if payload.kind == "transfer" and not (it.new_unit_id or it.new_position_id or new_rank_id):
            raise HTTPException(400, f"{label}: សូមជ្រើសរើសអង្គភាព មុខតំណែង ឬឋានន្តរស័ក្តិថ្មី")
        if new_rank_id and s.rank and s.rank.min_years_to_next:
            ym = diff_ym(s.rank_date, payload.effective_date)
            if ym is None or ym[0] < s.rank.min_years_to_next:
                warnings.append(f"{label}: រយៈពេលឡើងស័ក្តិមិនទាន់គ្រប់ {s.rank.min_years_to_next} ឆ្នាំ")
        _check_change(db, s, payload.kind, new_rank_id, it.new_position_id, it.new_unit_id, label)
        if it.new_position_id or it.new_unit_id or new_rank_id:
            warnings += staffing_warnings(
                db, s, unit_id=it.new_unit_id or s.current_unit_id,
                position_id=it.new_position_id or s.current_position_id,
                rank_id=new_rank_id or s.current_rank_id, rank_changes=bool(new_rank_id), label=label)
        items.append(DecisionItem(
            soldier_id=s.id, old_rank_id=s.current_rank_id, old_position_id=s.current_position_id,
            old_unit_id=s.current_unit_id, new_rank_id=new_rank_id,
            new_position_id=it.new_position_id, new_unit_id=it.new_unit_id, note=it.note,
        ))
    return items, warnings


@router.get("")
def list_decisions(kind: str, page: int = Query(1, ge=1), size: int = Query(20, le=200), q: str | None = None,
                   status: str | None = None, date_from: str | None = None, date_to: str | None = None,
                   waiting: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """waiting=true: only decisions waiting at a step this user can act on (their inbox)."""
    _need(user, kind, "view")
    stmt = select(Decision).where(Decision.kind == kind, Decision.deleted_at.is_(None))
    visible = _in_scope_condition(db, user)
    if visible is not None:
        stmt = stmt.where(visible)
    if q:
        stmt = stmt.where(or_(Decision.decision_no.ilike(f"%{q}%"), Decision.notes.ilike(f"%{q}%"),
                              Decision.id.in_(select(DecisionItem.decision_id).join(Soldier).where(
                                  or_(Soldier.name_kh.ilike(f"%{q}%"), Soldier.military_id.ilike(f"%{q}%"))))))
    if status:
        stmt = stmt.where(Decision.status == status)
    if waiting:
        mine = [st for st in WORKFLOW_STAGES if user.can(f"wf_{st}", "approve")]
        mine += ["approved"] if user.can("wf_publish", "approve") else []
        stmt = stmt.where(Decision.status.in_(mine))
    if date_from:
        stmt = stmt.where(Decision.decision_date >= date_from)
    if date_to:
        stmt = stmt.where(Decision.decision_date <= date_to)
    items, total = paginate(db, stmt.order_by(Decision.decision_date.desc(), Decision.id.desc()), page, size)
    cutoff = overdue_cutoff(db)
    return {"items": [decision_out(db, d, with_items=False, user=user, overdue_before=cutoff) for d in items],
            "total": total, "page": page, "size": size}


def _get(db: Session, decision_id: int) -> Decision:
    d = db.get(Decision, decision_id)
    if not d or d.deleted_at:
        raise HTTPException(404, "រកមិនឃើញសេចក្ដីសម្រេច")
    return d


@router.get("/{decision_id}")
def get_decision(decision_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = _get(db, decision_id)
    _need(user, d.kind, "view")
    visible = _in_scope_condition(db, user)
    if visible is not None and not db.scalar(select(Decision.id).where(Decision.id == d.id, visible)):
        raise HTTPException(403, "សេចក្ដីសម្រេចនេះនៅក្រៅសិទ្ធិរបស់អ្នក")
    return decision_out(db, d, user=user)


@router.post("", status_code=201)
def create_decision(payload: DecisionIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    _need(user, payload.kind, "create")
    items, warnings = _validate_items(db, user, payload)
    d = Decision(**payload.model_dump(exclude={"items", "decision_no"}), decision_no=payload.decision_no or "",
                 status="draft", status_changed_at=datetime.now(), created_by=user.id)
    d.items = items
    db.add(d)
    db.flush()
    audit(db, user, "create", d, request=request)
    db.commit()
    return {**decision_out(db, d, user=user), "warnings": warnings}


@router.put("/{decision_id}")
def update_decision(decision_id: int, payload: DecisionIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    d = _get(db, decision_id)
    _need(user, d.kind, "update")
    _check_scope(db, user, d)
    if d.status != "draft":
        raise HTTPException(400, "អាចកែប្រែបានតែសេចក្ដីសម្រេចព្រាងប៉ុណ្ណោះ")
    if payload.kind != d.kind:
        raise HTTPException(400, "មិនអាចប្ដូរប្រភេទសេចក្ដីសម្រេចបានទេ")
    items, warnings = _validate_items(db, user, payload)
    before = to_dict(d)
    data = payload.model_dump(exclude={"items", "kind"})
    for link in ("outgoing_document_id", "incoming_document_id"):
        if link not in payload.model_fields_set:
            data.pop(link)  # a client that does not send the link must not erase it
    data["decision_no"] = data["decision_no"] or ""
    for k, v in data.items():
        setattr(d, k, v)
    d.items = items
    d.updated_by = user.id
    audit(db, user, "update", d, before=before, request=request)
    db.commit()
    return {**decision_out(db, d, user=user), "warnings": warnings}


@router.delete("/{decision_id}")
def delete_decision(decision_id: int, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    d = _get(db, decision_id)
    _need(user, d.kind, "delete")
    _check_scope(db, user, d)
    if d.status not in ("draft", "rejected", "cancelled"):
        raise HTTPException(400, "អាចលុបបានតែសេចក្ដីព្រាង ឬសេចក្ដីសម្រេចដែលបានបដិសេធ/លុបចោល")
    d.deleted_at = datetime.now()
    audit(db, user, "delete", table="decisions", record_id=d.id, request=request)
    db.commit()
    return {"ok": True}


# ---------------- workflow ----------------

def _act(db: Session, user: User, decision_id: int, action: str) -> Decision:
    """Load the decision and check that `action` is one the user may do now."""
    d = _get(db, decision_id)
    _need(user, d.kind, "view")
    _check_scope(db, user, d, allow_old_unit=action == "cancel")
    if action not in STATUS_ACTIONS.get(d.status, ()):
        raise HTTPException(400, f"មិនអាចធ្វើសកម្មភាពនេះនៅដំណាក់កាល '{DECISION_STATUSES.get(d.status, d.status)}' បានទេ")
    if action not in allowed_actions(user, d):
        raise HTTPException(403, f"គ្មានសិទ្ធិសម្រាប់ដំណាក់កាល '{DECISION_STATUSES.get(d.status, d.status)}'")
    return d


def _move(db: Session, d: Decision, user: User, action: str, to_status: str, comment: str | None) -> None:
    db.add(DecisionStep(decision_id=d.id, action=action, from_status=d.status, to_status=to_status,
                        user_id=user.id, comment=comment))
    d.status, d.status_changed_at, d.updated_by = to_status, datetime.now(), user.id


def _recheck(db: Session, d: Decision) -> None:
    """Soldiers may have been promoted, moved or retired since the draft: the items must still be valid."""
    for it in d.items:
        s = db.get(Soldier, it.soldier_id)
        if not s or s.deleted_at:
            raise HTTPException(400, f"យោធិន id={it.soldier_id} មិនមានទៀតទេ")
        _check_change(db, s, d.kind, it.new_rank_id, it.new_position_id, it.new_unit_id, f"{s.name_kh} ({s.military_id})")


def _done(db: Session, user: User, d: Decision, action: str, request: Request) -> dict:
    audit(db, user, action, d, request=request)
    db.commit()
    db.refresh(d)
    return decision_out(db, d, user=user)


@router.post("/{decision_id}/submit")
def submit_decision(decision_id: int, request: Request, payload: WorkflowStepIn | None = None,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Step 1 -> 2: the registered request goes to the specialist for the conditions check."""
    d = _act(db, user, decision_id, "submit")
    _recheck(db, d)
    _move(db, d, user, "submit", FLOW[1], payload.comment if payload else None)
    return _done(db, user, d, "submit", request)


@router.post("/{decision_id}/approve")
def approve_decision(decision_id: int, request: Request, payload: WorkflowStepIn | None = None,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The current level approves: the decision moves to the next level (after top leadership: approved)."""
    d = _act(db, user, decision_id, "approve")
    _recheck(db, d)
    to_status = FLOW[FLOW.index(d.status) + 1]
    _move(db, d, user, "approve", to_status, payload.comment if payload else None)
    if to_status == "approved":
        d.approved_by, d.approved_at = user.id, datetime.now()
    return _done(db, user, d, "approve", request)


def _reason(payload: WorkflowStepIn | None) -> str:
    if not payload or not payload.comment:
        raise HTTPException(400, "សូមបញ្ចូលមូលហេតុ")
    return payload.comment


@router.post("/{decision_id}/return")
def return_decision(decision_id: int, payload: WorkflowStepIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Send back one level for corrections (the specialist sends it back to the draft)."""
    d = _act(db, user, decision_id, "return")
    _move(db, d, user, "return", FLOW[FLOW.index(d.status) - 1], _reason(payload))
    return _done(db, user, d, "return", request)


@router.post("/{decision_id}/reject")
def reject_decision(decision_id: int, payload: WorkflowStepIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Close the file with a reason."""
    d = _act(db, user, decision_id, "reject")
    _move(db, d, user, "reject", "rejected", _reason(payload))
    return _done(db, user, d, "reject", request)


@router.post("/{decision_id}/publish")
def publish_decision(decision_id: int, request: Request, payload: PublishIn | None = None,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Step 8: register the outgoing letter and update the soldiers' records."""
    payload = payload or PublishIn()
    d = _act(db, user, decision_id, "publish")
    _recheck(db, d)
    if payload.decision_date:
        d.decision_date = payload.decision_date
    if payload.outgoing_document_id:
        if not db.get(DocumentOutgoing, payload.outgoing_document_id):
            raise HTTPException(400, "ឯកសារចេញមិនត្រឹមត្រូវ")
        d.outgoing_document_id = payload.outgoing_document_id
    if not d.outgoing_document_id:
        year = d.decision_date.year
        seq, number = allocate_outgoing_number(db, year)
        doc_type = db.scalar(select(DocumentType.id).where(DocumentType.name_kh == "សេចក្ដីសម្រេច"))
        doc = DocumentOutgoing(outgoing_no=number, seq=seq, year=year, doc_date=d.decision_date,
                               subject=f"សេចក្ដីសម្រេចស្ដីពី{DECISION_KINDS[d.kind]} ចំនួន {len(d.items)} រូប",
                               document_type_id=doc_type, status="sent", created_by=user.id)
        db.add(doc)
        db.flush()
        d.outgoing_document_id = doc.id
    d.decision_no = payload.decision_no or d.decision_no or db.get(DocumentOutgoing, d.outgoing_document_id).outgoing_no
    eff = d.effective_date
    for it in d.items:
        s = db.get(Soldier, it.soldier_id)
        # snapshot the state at publishing time (it may have changed since the draft was made)
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
    _move(db, d, user, "publish", "published", payload.comment)
    d.published_by, d.published_at = user.id, datetime.now()
    return _done(db, user, d, "publish", request)


@router.post("/{decision_id}/cancel")
def cancel_decision(decision_id: int, request: Request, payload: WorkflowStepIn | None = None,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Revert a published decision (only if nothing newer has changed the soldiers since)."""
    d = _act(db, user, decision_id, "cancel")
    for it in d.items:
        s = db.get(Soldier, it.soldier_id)
        own = db.scalar(select(func.min(SoldierHistory.id)).where(
            SoldierHistory.soldier_id == s.id, SoldierHistory.decision_id == d.id))
        newer = own and db.scalar(select(SoldierHistory.id).where(
            SoldierHistory.soldier_id == s.id, SoldierHistory.id > own,
            or_(SoldierHistory.decision_id.is_(None), SoldierHistory.decision_id != d.id)).limit(1))
        if newer:
            raise HTTPException(409, f"{s.name_kh}: មានការផ្លាស់ប្ដូរថ្មីជាងនេះ មិនអាចត្រឡប់វិញបានទេ")
        if is_inactive(db, s):
            raise HTTPException(409, f"{s.name_kh}: បានចូលនិវត្តន៍ ឬចេញពីជួររួចហើយ មិនអាចត្រឡប់វិញបានទេ")
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
    _move(db, d, user, "cancel", "cancelled", payload.comment if payload else None)
    return _done(db, user, d, "cancel", request)
