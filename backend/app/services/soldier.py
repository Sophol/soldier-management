from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lookup, Soldier, SoldierHistory, StrengthMovement


def diff_ym(start: date | None, end: date | None = None) -> tuple[int, int] | None:
    """Whole years and months between two dates."""
    if not start:
        return None
    end = end or date.today()
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    months = max(months, 0)
    return months // 12, months % 12


def ym_text(ym: tuple[int, int] | None) -> str | None:
    if ym is None:
        return None
    y, m = ym
    return f"{y} ឆ្នាំ {m} ខែ"


def years_ago(years: int) -> date:
    """Today, `years` years ago (29 February falls back to the 28th)."""
    t = date.today()
    try:
        return t.replace(year=t.year - years)
    except ValueError:
        return t.replace(year=t.year - years, day=28)


def age(dob: date | None) -> int | None:
    ym = diff_ym(dob)
    return ym[0] if ym else None


def unit_chain(unit) -> list:
    """[institution, ..., unit]: the unit and all of its parents, top first."""
    chain = []
    while unit is not None:
        chain.append(unit)
        unit = unit.parent
    return chain[::-1]


def soldier_summary(s: Soldier) -> dict:
    """Fields shown in lists (with computed values)."""
    service = diff_ym(s.enlistment_date)
    in_rank = diff_ym(s.rank_date)
    in_position = diff_ym(s.position_date)
    chain = unit_chain(s.unit)
    return {
        "id": s.id,
        "military_id": s.military_id,
        "name_kh": s.name_kh,
        "name_latin": s.name_latin,
        "gender": s.gender,
        "date_of_birth": s.date_of_birth.isoformat() if s.date_of_birth else None,
        "age": age(s.date_of_birth),
        "phone": s.phone,
        "photo_path": s.photo_path,
        "rank_id": s.current_rank_id,
        "rank_name": s.rank.name_kh if s.rank else None,
        "rank_sort": s.rank.sort_order if s.rank else None,
        "position_id": s.current_position_id,
        "position_name": s.position.name_kh if s.position else None,
        "unit_id": s.current_unit_id,
        "unit_name": s.unit.name_kh if s.unit else None,
        "institution_id": chain[0].id if chain else None,
        "institution_name": chain[0].name_kh if chain else None,
        "unit_path": " › ".join(u.name_kh for u in chain) or None,
        "status_id": s.status_id,
        "status_name": s.status.name_kh if s.status else None,
        "status_code": s.status.code if s.status else None,
        "enlistment_date": s.enlistment_date.isoformat() if s.enlistment_date else None,
        "service_length": ym_text(service),
        "service_years": service[0] if service else None,
        "rank_date": s.rank_date.isoformat() if s.rank_date else None,
        "time_in_rank": ym_text(in_rank),
        "time_in_rank_years": in_rank[0] if in_rank else None,
        "position_date": s.position_date.isoformat() if s.position_date else None,
        "time_in_position": ym_text(in_position),
        "specialty_name": s.specialty.name_kh if s.specialty else None,
    }


def status_id_by_code(db: Session, code: str) -> int | None:
    return db.scalar(select(Lookup.id).where(Lookup.category == "soldier_status", Lookup.code == code))


def years_to_next_rank(s: Soldier) -> int | None:
    """Minimum years in the current rank before promotion, for the soldier's service track
    (combat operations use the rank's combat value when it is set)."""
    if not s.rank:
        return None
    if s.service_track == "combat" and s.rank.min_years_combat is not None:
        return s.rank.min_years_combat
    return s.rank.min_years_to_next


# statuses of soldiers who have left the strength (retirement, category 2, separation)
INACTIVE_STATUS_CODES = ("retired", "category2", "separated")


def is_inactive(db: Session, s: Soldier) -> bool:
    """True when the soldier has left the strength (read by id: the cached relationship may be stale)."""
    code = db.scalar(select(Lookup.code).where(Lookup.id == s.status_id)) if s.status_id else None
    return code in INACTIVE_STATUS_CODES


def add_history(db: Session, soldier: Soldier, kind: str, effective_date: date | None, *,
                old_rank=None, new_rank=None, old_position=None, new_position=None,
                old_unit=None, new_unit=None, decision_id=None, note=None) -> None:
    db.add(SoldierHistory(
        soldier_id=soldier.id, kind=kind, effective_date=effective_date,
        old_rank_id=old_rank, new_rank_id=new_rank, old_position_id=old_position, new_position_id=new_position,
        old_unit_id=old_unit, new_unit_id=new_unit, decision_id=decision_id, note=note,
    ))


def add_movement(db: Session, soldier_id: int, unit_id: int | None, direction: str, reason: str,
                 movement_date: date, source_table: str | None = None, source_id: int | None = None,
                 note: str | None = None) -> None:
    db.add(StrengthMovement(
        soldier_id=soldier_id, unit_id=unit_id, direction=direction, reason=reason,
        movement_date=movement_date, source_table=source_table, source_id=source_id, note=note,
    ))
