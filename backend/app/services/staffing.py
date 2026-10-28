"""Staffing table (ក្របខណ្ឌ) and rank quotas: how many soldiers a unit position / a rank may have."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Lookup, Rank, Soldier, UnitPosition
from app.services.soldier import INACTIVE_STATUS_CODES


def serving(stmt):
    """Restrict a soldier query to soldiers still in the strength (not deleted, not retired/separated)."""
    return stmt.outerjoin(Lookup, Lookup.id == Soldier.status_id).where(
        Soldier.deleted_at.is_(None), or_(Lookup.code.is_(None), Lookup.code.not_in(INACTIVE_STATUS_CODES)))


def filled_count(db: Session, *conds) -> int:
    return db.scalar(serving(select(func.count(Soldier.id))).where(*conds)) or 0


def filled_by_unit_position(db: Session, unit_id: int) -> dict[int, int]:
    """{position_id: serving soldiers} for one unit."""
    stmt = serving(select(Soldier.current_position_id, func.count(Soldier.id))).where(
        Soldier.current_unit_id == unit_id).group_by(Soldier.current_position_id)
    return dict(db.execute(stmt).all())


def filled_column():
    """Correlated SQL count of serving soldiers in a staffing-table row (UnitPosition), for filtering."""
    return serving(select(func.count(Soldier.id))).where(
        Soldier.current_unit_id == UnitPosition.unit_id, Soldier.current_position_id == UnitPosition.position_id,
    ).correlate(UnitPosition).scalar_subquery()


def filled_by_rank(db: Session) -> dict[int, int]:
    stmt = serving(select(Soldier.current_rank_id, func.count(Soldier.id))).group_by(Soldier.current_rank_id)
    return dict(db.execute(stmt).all())


def staffing_problems(db: Session, s: Soldier, *, unit_id, position_id, rank_id, slot_changes: bool,
                      rank_changes: bool, label: str, planned_slot: int = 0, planned_rank: int = 0) -> list[str]:
    """Reasons a decision would break the staffing table (ក្របខណ្ឌ) or a rank quota; decisions are refused while
    any remain (New.txt §4: appointments must be checked against the staffing table and the rank).
    slot_changes: the soldier moves into unit_id/position_id; rank_changes: the soldier gets rank_id.
    planned_*: other soldiers of the same decision already going into the same slot / rank."""
    problems = []
    rank = db.get(Rank, rank_id) if rank_id else None
    if slot_changes and unit_id and position_id:
        up = db.scalar(select(UnitPosition).where(UnitPosition.unit_id == unit_id, UnitPosition.position_id == position_id))
        if up is not None:
            filled = filled_count(db, Soldier.current_unit_id == unit_id, Soldier.current_position_id == position_id,
                                  Soldier.id != s.id) + planned_slot
            if filled >= up.quota:
                problems.append(f"{label}: មុខតំណែង {up.position.name_kh} ក្នុង {up.unit.name_kh} "
                                f"ពេញក្របខណ្ឌហើយ ({filled}/{up.quota})")
            low = db.get(Rank, up.min_rank_id) if up.min_rank_id else None
            high = db.get(Rank, up.max_rank_id) if up.max_rank_id else None
            if rank and ((low and rank.sort_order < low.sort_order) or (high and rank.sort_order > high.sort_order)):
                span = f"{low.name_kh if low else '...'} – {high.name_kh if high else '...'}"
                problems.append(f"{label}: ឋានន្តរស័ក្តិ {rank.name_kh} មិនស្របនឹងមុខតំណែងនេះ ({span})")
        elif db.scalar(select(UnitPosition.id).where(UnitPosition.unit_id == unit_id).limit(1)):
            # a unit that has a staffing table only takes the positions listed in it
            problems.append(f"{label}: មុខតំណែងនេះមិនមានក្នុងក្របខណ្ឌរបស់អង្គភាព")
    if rank_changes and rank and rank.quota is not None:
        filled = filled_count(db, Soldier.current_rank_id == rank.id, Soldier.id != s.id) + planned_rank
        if filled >= rank.quota:
            problems.append(f"{label}: ឋានន្តរស័ក្តិ {rank.name_kh} ពេញចំនួនកំណត់ហើយ ({filled}/{rank.quota})")
    return problems
