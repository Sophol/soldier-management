"""Organisation structure and master data: units, ranks, positions, specialties,
document types, lookups, geography, countries."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, object_session

from app.api.crud import crud_router
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import (
    Commune,
    Country,
    District,
    DocumentType,
    Lookup,
    Position,
    Province,
    Rank,
    RankClass,
    Soldier,
    Specialty,
    Unit,
    UnitPosition,
    User,
    Village,
)
from app.models.org import LOOKUP_CATEGORIES, POSITION_LEVELS, UNIT_LEVELS
from app.schemas import (
    CommuneIn,
    CountryIn,
    DistrictIn,
    DocumentTypeIn,
    LookupIn,
    PositionIn,
    ProvinceIn,
    RankClassIn,
    RankIn,
    SpecialtyIn,
    UnitIn,
    UnitPositionIn,
    VillageIn,
)
from app.services.common import to_dict
from app.services.staffing import filled_by_rank, filled_by_unit_position

router = APIRouter()
extra = APIRouter()  # custom routes that must be registered before the generic /{id} routes


# ---------------- units (tree) ----------------

def _unit_before_save(db: Session, user: User, obj: Unit, data: dict, is_new: bool) -> None:
    parent_id = data.get("parent_id")
    obj._old_path = None if is_new else obj.path
    if parent_id:
        parent = db.get(Unit, parent_id)
        if not parent:
            raise HTTPException(400, "អង្គភាពមេមិនត្រឹមត្រូវ")
        if not is_new and (parent.id == obj.id or parent.path.startswith(obj.path)):
            raise HTTPException(400, "មិនអាចដាក់អង្គភាពនៅក្រោមខ្លួនឯង ឬអង្គភាពរងរបស់ខ្លួនបានទេ")
        if parent.level >= 4:
            raise HTTPException(400, "អង្គភាពចំណុះផ្ទាល់ មិនអាចមានអង្គភាពរងទៀតបានទេ")
        data["level"] = parent.level + 1
    else:
        data["level"] = 1
    if not is_new and data["level"] != obj.level:
        # the whole subtree moves with the unit: its deepest descendant must stay within level 4
        deepest = db.scalar(select(func.max(Unit.level)).where(Unit.path.like(f"{obj.path}%"))) or obj.level
        if deepest + data["level"] - obj.level > 4:
            raise HTTPException(400, "អង្គភាពរងរបស់អង្គភាពនេះ នឹងលើសពីកម្រិតទី៤ (អង្គភាពចំណុះផ្ទាល់)")


def _unit_after_save(db: Session, user: User, obj: Unit, is_new: bool) -> None:
    parent = db.get(Unit, obj.parent_id) if obj.parent_id else None
    new_path = f"{parent.path if parent else '/'}{obj.id}/"
    old_path = getattr(obj, "_old_path", None)
    obj.path = new_path
    if old_path and old_path != new_path:
        # move the whole subtree
        db.execute(
            update(Unit)
            .where(Unit.path.like(f"{old_path}%"), Unit.id != obj.id)
            .values(path=func.concat(new_path, func.substr(Unit.path, len(old_path) + 1)),
                    level=Unit.level + (new_path.count("/") - old_path.count("/")))
        )
    db.flush()


def unit_out(u: Unit) -> dict:
    return {**to_dict(u), "level_name": UNIT_LEVELS.get(u.level), "parent_name": u.parent.name_kh if u.parent else None}


@extra.get("/units/tree", tags=["units"])
def unit_tree(active_only: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Unit).order_by(Unit.level, Unit.sort_order, Unit.name_kh)
    if active_only:
        stmt = stmt.where(Unit.active.is_(True))
    if user.unit_scope_id and not user.role.is_super:
        scope = db.get(Unit, user.unit_scope_id)
        stmt = stmt.where(Unit.path.like(f"{scope.path}%"))
    units = db.scalars(stmt).all()
    counts = dict(db.execute(
        select(Soldier.current_unit_id, func.count()).where(Soldier.deleted_at.is_(None))
        .group_by(Soldier.current_unit_id)
    ).all())
    nodes = {u.id: {**to_dict(u), "level_name": UNIT_LEVELS.get(u.level),
                    "soldier_count": counts.get(u.id, 0), "children": []} for u in units}
    roots = []
    for u in units:
        node = nodes[u.id]
        if u.parent_id in nodes:
            nodes[u.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


@extra.get("/meta/unit-levels", tags=["units"])
def unit_levels(_: User = Depends(get_current_user)):
    return [{"value": k, "label": v} for k, v in UNIT_LEVELS.items()]


@extra.get("/meta/lookup-categories", tags=["lookups"])
def lookup_categories(_: User = Depends(get_current_user)):
    return [{"value": k, "label": v} for k, v in LOOKUP_CATEGORIES.items()]


@extra.get("/lookups/all", tags=["lookups"])
def all_lookups(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Every dropdown list in one call (used by the frontend lookup store)."""
    out: dict[str, list] = {c: [] for c in LOOKUP_CATEGORIES}
    for lk in db.scalars(select(Lookup).where(Lookup.active.is_(True)).order_by(Lookup.category, Lookup.sort_order)):
        out.setdefault(lk.category, []).append({"id": lk.id, "code": lk.code, "name_kh": lk.name_kh, "name_en": lk.name_en})
    ranks = db.scalars(select(Rank).where(Rank.active.is_(True)).order_by(Rank.sort_order.desc())).all()
    out["ranks"] = [{**to_dict(r), "rank_class_name": r.rank_class.name_kh} for r in ranks]
    out["rank_classes"] = [to_dict(r) for r in db.scalars(select(RankClass).order_by(RankClass.sort_order))]
    out["positions"] = [to_dict(p) for p in db.scalars(
        select(Position).where(Position.active.is_(True)).order_by(Position.sort_order, Position.name_kh))]
    out["specialties"] = [to_dict(s) for s in db.scalars(
        select(Specialty).where(Specialty.active.is_(True)).order_by(Specialty.name_kh))]
    out["document_types"] = [to_dict(d) for d in db.scalars(
        select(DocumentType).where(DocumentType.active.is_(True)).order_by(DocumentType.id))]
    out["countries"] = [{"id": c.id, "name_kh": c.name_kh, "name_en": c.name_en} for c in db.scalars(
        select(Country).where(Country.active.is_(True)).order_by(Country.name_en))]
    return out


# ---------------- geography helpers ----------------

@extra.get("/geo/village-path/{village_id}", tags=["geography"])
def village_path(village_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    v = db.get(Village, village_id)
    if not v:
        raise HTTPException(404, "រកមិនឃើញភូមិ")
    c = v.commune
    d = c.district
    p = d.province
    return {
        "province_id": p.id, "district_id": d.id, "commune_id": c.id, "village_id": v.id,
        "text": f"ភូមិ{v.name_kh} {c.type}{c.name_kh} {d.type}{d.name_kh} {p.type}{p.name_kh}",
    }


def _rank_out(r: Rank) -> dict:
    filled = filled_by_rank(object_session(r)).get(r.id, 0)
    return {**to_dict(r), "rank_class_name": r.rank_class.name_kh if r.rank_class else None, "filled": filled,
            "vacant": None if r.quota is None else r.quota - filled}


# ---------------- staffing table (ក្របខណ្ឌមុខតំណែងតាមអង្គភាព) ----------------

def _unit_position_out(up: UnitPosition) -> dict:
    db = object_session(up)
    filled = filled_by_unit_position(db, up.unit_id).get(up.position_id, 0)
    ranks = {r.id: r.name_kh for r in db.scalars(select(Rank).where(Rank.id.in_(
        [i for i in (up.min_rank_id, up.max_rank_id) if i])))}
    return {**to_dict(up), "unit_name": up.unit.name_kh, "position_name": up.position.name_kh,
            "min_rank_name": ranks.get(up.min_rank_id), "max_rank_name": ranks.get(up.max_rank_id),
            "salary_effective": float(up.salary if up.salary is not None else (up.position.salary or 0)) or None,
            "filled": filled, "vacant": up.quota - filled}


def _unit_position_check(db, user, obj, data, is_new):
    if not db.get(Unit, data["unit_id"]) or not db.get(Position, data["position_id"]):
        raise HTTPException(400, "អង្គភាព ឬមុខតំណែងមិនត្រឹមត្រូវ")
    low = db.get(Rank, data["min_rank_id"]) if data.get("min_rank_id") else None
    high = db.get(Rank, data["max_rank_id"]) if data.get("max_rank_id") else None
    if low and high and low.sort_order > high.sort_order:
        raise HTTPException(400, "ឋានន្តរស័ក្តិទាបបំផុត ត្រូវតែទាបជាងឬស្មើឋានន្តរស័ក្តិខ្ពស់បំផុត")


# lookup codes the application logic depends on (statuses set by retirement/separation, form logic)
SYSTEM_LOOKUP_CODES = {
    "soldier_status": {"active", "studying", "suspended", "retired", "category2", "separated"},
    "marital_status": {"single"},
}


def _is_system_lookup(obj: Lookup) -> bool:
    return obj.code in SYSTEM_LOOKUP_CODES.get(obj.category, ())


# ---------------- positions (មុខតំណែង › មុខតំណែងរង › មុខតំណែងចំណុះផ្ទាល់) ----------------

def _position_before_save(db, user, obj, data, is_new):
    parent = db.get(Position, data["parent_id"]) if data.get("parent_id") else None
    if data.get("parent_id") and not parent:
        raise HTTPException(400, "មុខតំណែងមេមិនត្រឹមត្រូវ")
    p = parent
    while p is not None:  # no cycles: the parent may not be this position or one below it
        if not is_new and p.id == obj.id:
            raise HTTPException(400, "មិនអាចដាក់មុខតំណែងនៅក្រោមខ្លួនឯង ឬមុខតំណែងរងរបស់ខ្លួនបានទេ")
        p = db.get(Position, p.parent_id) if p.parent_id else None
    data["level"] = parent.level + 1 if parent else 1
    if data["level"] > 3:
        raise HTTPException(400, "មុខតំណែងចំណុះផ្ទាល់ មិនអាចមានមុខតំណែងរងទៀតបានទេ")
    if not is_new and data["level"] != obj.level and db.scalar(select(Position.id).where(Position.parent_id == obj.id).limit(1)):
        raise HTTPException(400, "មុខតំណែងនេះមានមុខតំណែងរង — សូមផ្លាស់ទីមុខតំណែងរងជាមុនសិន")


def _position_out(p: Position) -> dict:
    db = object_session(p)
    parent = db.get(Position, p.parent_id) if p.parent_id else None
    return {**to_dict(p), "level_name": POSITION_LEVELS.get(p.level), "parent_name": parent.name_kh if parent else None}


@extra.get("/positions/tree", tags=["positions"])
def position_tree(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(Position).order_by(Position.level, Position.sort_order, Position.name_kh)).all()
    nodes = {p.id: {**to_dict(p), "level_name": POSITION_LEVELS.get(p.level), "children": []} for p in rows}
    roots = []
    for p in rows:
        (nodes[p.parent_id]["children"] if p.parent_id in nodes else roots).append(nodes[p.id])
    return roots


# ---------------- specialties: military / civil field > section (ផ្នែក) > specialty ----------------

def _specialty_before_save(db, user, obj, data, is_new):
    if data.get("section_id"):
        section = db.get(Lookup, data["section_id"])
        if not section or section.category != "specialty_section":
            raise HTTPException(400, "ផ្នែកមិនត្រឹមត្រូវ")


def _specialty_out(sp: Specialty) -> dict:
    section = object_session(sp).get(Lookup, sp.section_id) if sp.section_id else None
    return {**to_dict(sp), "section_name": section.name_kh if section else None}


def _lookup_check(db, user, obj, data, is_new):
    if data["category"] not in LOOKUP_CATEGORIES:
        raise HTTPException(400, "ប្រភេទបញ្ជីមិនត្រឹមត្រូវ")
    if not is_new and _is_system_lookup(obj) and (data["category"], data["code"]) != (obj.category, obj.code):
        raise HTTPException(400, f"កូដ '{obj.code}' ប្រើដោយប្រព័ន្ធ មិនអាចប្ដូរបានទេ (អាចប្ដូរតែឈ្មោះ)")


def _lookup_delete_check(db, user, obj):
    if _is_system_lookup(obj):
        raise HTTPException(400, f"កូដ '{obj.code}' ប្រើដោយប្រព័ន្ធ មិនអាចលុបបានទេ (អាចបិទមិនឱ្យប្រើបាន)")


router.include_router(extra)
router.include_router(crud_router(
    prefix="/units", model=Unit, module="org_units", schema=UnitIn, public_read=True,
    search_fields=(Unit.name_kh, Unit.name_en, Unit.code), filter_fields={"parent_id": Unit.parent_id, "level": Unit.level},
    order_by=(Unit.level, Unit.sort_order, Unit.name_kh), serialize=unit_out,
    before_save=_unit_before_save, after_save=_unit_after_save, tags=["units"],
))
router.include_router(crud_router(
    prefix="/rank-classes", model=RankClass, module="ranks", schema=RankClassIn, public_read=True,
    order_by=(RankClass.sort_order,), tags=["ranks"],
))
router.include_router(crud_router(
    prefix="/ranks", model=Rank, module="ranks", schema=RankIn, public_read=True,
    search_fields=(Rank.name_kh, Rank.name_en),
    filter_fields={"rank_class_id": Rank.rank_class_id, "branch": Rank.branch},
    order_by=(Rank.sort_order.desc(),), serialize=_rank_out, tags=["ranks"],
))
router.include_router(crud_router(
    prefix="/positions", model=Position, module="positions", schema=PositionIn, public_read=True,
    search_fields=(Position.name_kh, Position.name_en),
    filter_fields={"parent_id": Position.parent_id, "level": Position.level},
    order_by=(Position.level, Position.sort_order, Position.name_kh), serialize=_position_out,
    before_save=_position_before_save,
))
router.include_router(crud_router(
    prefix="/specialties", model=Specialty, module="specialties", schema=SpecialtyIn, public_read=True,
    search_fields=(Specialty.name_kh, Specialty.name_en),
    filter_fields={"category": Specialty.category, "section_id": Specialty.section_id},
    order_by=(Specialty.category, Specialty.name_kh), serialize=_specialty_out, before_save=_specialty_before_save,
))
router.include_router(crud_router(
    prefix="/unit-positions", model=UnitPosition, module="positions", schema=UnitPositionIn,
    filter_fields={"unit_id": UnitPosition.unit_id, "position_id": UnitPosition.position_id},
    order_by=(UnitPosition.unit_id, UnitPosition.id), serialize=_unit_position_out,
    before_save=_unit_position_check, tags=["positions"],
))
router.include_router(crud_router(
    prefix="/document-types", model=DocumentType, module="doc_types", schema=DocumentTypeIn, public_read=True,
    search_fields=(DocumentType.name_kh, DocumentType.name_en), order_by=(DocumentType.id,),
))
router.include_router(crud_router(
    prefix="/lookups", model=Lookup, module="lookups", schema=LookupIn, public_read=True,
    search_fields=(Lookup.name_kh, Lookup.name_en), filter_fields={"category": Lookup.category},
    order_by=(Lookup.category, Lookup.sort_order), before_save=_lookup_check, before_delete=_lookup_delete_check,
))
router.include_router(crud_router(
    prefix="/countries", model=Country, module="lookups", schema=CountryIn, public_read=True,
    search_fields=(Country.name_kh, Country.name_en), order_by=(Country.name_en,),
))
router.include_router(crud_router(
    prefix="/geo/provinces", model=Province, module="geography", schema=ProvinceIn, public_read=True,
    search_fields=(Province.name_kh, Province.name_en), order_by=(Province.id,), tags=["geography"],
))
router.include_router(crud_router(
    prefix="/geo/districts", model=District, module="geography", schema=DistrictIn, public_read=True,
    search_fields=(District.name_kh, District.name_en), filter_fields={"province_id": District.province_id},
    order_by=(District.id,), tags=["geography"],
))
router.include_router(crud_router(
    prefix="/geo/communes", model=Commune, module="geography", schema=CommuneIn, public_read=True,
    search_fields=(Commune.name_kh, Commune.name_en), filter_fields={"district_id": Commune.district_id},
    order_by=(Commune.id,), tags=["geography"],
))
router.include_router(crud_router(
    prefix="/geo/villages", model=Village, module="geography", schema=VillageIn, public_read=True,
    search_fields=(Village.name_kh, Village.name_en), filter_fields={"commune_id": Village.commune_id},
    order_by=(Village.id,), tags=["geography"],
))
