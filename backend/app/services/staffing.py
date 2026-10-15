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


def filled_by_rank(db: Session) -> dict[int, int]:
    stmt = serving(select(Soldier.current_rank_id, func.count(Soldier.id))).group_by(Soldier.current_rank_id)
    return dict(db.execute(stmt).all())


def staffing_warnings(db: Session, s: Soldier, *, unit_id, position_id, rank_id, rank_changes: bool,
                      label: str) -> list[str]:
    """Warnings (not errors) when a decision would exceed the staffing table or a rank quota,
    or put a soldier of the wrong rank in a position."""
    warnings = []
    rank = db.get(Rank, rank_id) if rank_id else None
    if unit_id and position_id:
        up = db.scalar(select(UnitPosition).where(UnitPosition.unit_id == unit_id, UnitPosition.position_id == position_id))
        if up is not None:
            filled = filled_count(db, Soldier.current_unit_id == unit_id, Soldier.current_position_id == position_id,
                                  Soldier.id != s.id)
            if filled >= up.quota:
                warnings.append(f"{label}: មុខតំណែង {up.position.name_kh} ក្នុង {up.unit.name_kh} "
                                f"ពេញក្របខណ្ឌហើយ ({filled}/{up.quota})")
            low = db.get(Rank, up.min_rank_id) if up.min_rank_id else None
            high = db.get(Rank, up.max_rank_id) if up.max_rank_id else None
            if rank and ((low and rank.sort_order < low.sort_order) or (high and rank.sort_order > high.sort_order)):
                span = f"{low.name_kh if low else '...'} – {high.name_kh if high else '...'}"
                warnings.append(f"{label}: ឋានន្តរស័ក្តិ {rank.name_kh} មិនស្របនឹងមុខតំណែងនេះ ({span})")
        elif position_id and db.scalar(select(UnitPosition.id).where(UnitPosition.unit_id == unit_id).limit(1)):
            warnings.append(f"{label}: មុខតំណែងនេះមិនមានក្នុងក្របខណ្ឌរបស់អង្គភាព")
    if rank_changes and rank and rank.quota is not None:
        filled = filled_count(db, Soldier.current_rank_id == rank.id, Soldier.id != s.id)
        if filled >= rank.quota:
            warnings.append(f"{label}: ឋានន្តរស័ក្តិ {rank.name_kh} ពេញចំនួនកំណត់ហើយ ({filled}/{rank.quota})")
    return warnings
