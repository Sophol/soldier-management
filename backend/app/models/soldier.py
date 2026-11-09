from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, Integer, SmallInteger, String, Text, event, update
from sqlalchemy.orm import Mapped, Session, attributes, mapped_column, relationship

from app.core.database import AuditMixin, Base, SoftDeleteMixin, TimestampMixin
from app.models.org import Rank


class Soldier(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "soldiers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    military_id: Mapped[str] = mapped_column(String(50), unique=True)  # អត្តលេខ
    name_kh: Mapped[str] = mapped_column(String(255), index=True)  # គោត្តនាមនិងនាម
    name_latin: Mapped[str | None] = mapped_column(String(255), index=True)
    gender: Mapped[str] = mapped_column(String(1))  # M / F
    date_of_birth: Mapped[date | None] = mapped_column(Date, index=True)
    national_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    national_id_expiry: Mapped[date | None] = mapped_column(Date, index=True)  # ថ្ងៃផុតកំណត់អត្តសញ្ញាណប័ណ្ណ
    nationality: Mapped[str | None] = mapped_column(String(50), default="ខ្មែរ")  # សញ្ជាតិ
    ethnicity: Mapped[str | None] = mapped_column(String(50))  # ជនជាតិ
    phone: Mapped[str | None] = mapped_column(String(50))
    photo_path: Mapped[str | None] = mapped_column(String(255))
    blood_type_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))

    birth_village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"))
    birth_place_text: Mapped[str | None] = mapped_column(String(500))
    current_village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"))
    current_address_text: Mapped[str | None] = mapped_column(String(500))
    # គោលនយោបាយ (New (2).txt §10): ជួលមូលដ្ឋាន, ទីបោះឆ្នោត, ស្ថានភាពលំនៅ, អ្នកក្នុងបន្ទុក
    base_village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"))
    voting_village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"))
    voting_place: Mapped[str | None] = mapped_column(String(255))  # polling station
    housing_status: Mapped[str | None] = mapped_column(String(10))  # own ផ្ទះផ្ទាល់ / rent ជួល / stay ស្នាក់
    dependents_count: Mapped[int] = mapped_column(SmallInteger, default=0)  # ចំនួនអ្នកក្នុងបន្ទុក

    # current service state (cache of the latest history row)
    current_rank_id: Mapped[int | None] = mapped_column(ForeignKey("ranks.id"), index=True)
    # copy of the current rank's sort_order (kept by _sync_rank_sort) so the default list order uses an index
    rank_sort: Mapped[int | None] = mapped_column(Integer)
    rank_date: Mapped[date | None] = mapped_column(Date)
    current_position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"), index=True)
    position_date: Mapped[date | None] = mapped_column(Date)
    current_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True)
    unit_transfer_date: Mapped[date | None] = mapped_column(Date)
    from_unit_text: Mapped[str | None] = mapped_column(String(255))  # មកពីស្ថាប័នកងឯកភាព
    enlistment_date: Mapped[date | None] = mapped_column(Date)
    service_track: Mapped[str] = mapped_column(String(10), default="admin")
    establishment_no: Mapped[str | None] = mapped_column(String(100), index=True)  # បញ្ចូលក្របខ័ណ្ឌលេខ  # admin រដ្ឋបាល / combat ប្រតិបត្តិការសឹក

    status_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"), index=True)
    education_level_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    specialty_id: Mapped[int | None] = mapped_column(ForeignKey("specialties.id"))
    combat_veteran: Mapped[bool] = mapped_column(Boolean, default=False)
    combat_note: Mapped[str | None] = mapped_column(String(500))

    marital_status_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    spouse_name: Mapped[str | None] = mapped_column(String(255))
    spouse_job_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    children_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    father_name: Mapped[str | None] = mapped_column(String(255))
    mother_name: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    rank = relationship("Rank", lazy="joined")
    position = relationship("Position", lazy="joined")
    unit = relationship("Unit", lazy="joined")
    status = relationship("Lookup", foreign_keys=[status_id], lazy="joined")
    specialty = relationship("Specialty", lazy="joined")

    educations: Mapped[list["SoldierEducation"]] = relationship(cascade="all, delete-orphan", order_by="SoldierEducation.start_date")
    languages: Mapped[list["SoldierLanguage"]] = relationship(cascade="all, delete-orphan")
    children: Mapped[list["SoldierChild"]] = relationship(cascade="all, delete-orphan")


# the soldier list's default order (highest rank first, then name) and its reverse, read straight from an index
Index("ix_soldiers_rank_sort_desc", Soldier.rank_sort.desc(), Soldier.name_kh)
Index("ix_soldiers_rank_sort_asc", Soldier.rank_sort, Soldier.name_kh)


@event.listens_for(Session, "before_flush")
def _sync_rank_sort(session: Session, _flush_context, _instances) -> None:
    """Keep Soldier.rank_sort equal to the sort_order of the soldier's current rank, whichever way either changes."""
    with session.no_autoflush:
        for obj in [*session.new, *session.dirty]:
            if isinstance(obj, Soldier) and (obj in session.new or attributes.get_history(obj, "current_rank_id").has_changes()):
                rank = session.get(Rank, obj.current_rank_id) if obj.current_rank_id else None
                obj.rank_sort = rank.sort_order if rank else None
            elif isinstance(obj, Rank) and obj not in session.new and attributes.get_history(obj, "sort_order").has_changes():
                session.execute(update(Soldier).where(Soldier.current_rank_id == obj.id).values(rank_sort=obj.sort_order)
                                .execution_options(synchronize_session=False))


class SoldierEducation(TimestampMixin, Base):
    __tablename__ = "soldier_educations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="general")  # general / specialty / other
    education_level_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    specialty_text: Mapped[str | None] = mapped_column(String(255))
    institution: Mapped[str | None] = mapped_column(String(255))
    country_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"))
    is_abroad: Mapped[bool] = mapped_column(Boolean, default=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    duration_text: Mapped[str | None] = mapped_column(String(100))


class SoldierLanguage(TimestampMixin, Base):
    __tablename__ = "soldier_languages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id", ondelete="CASCADE"), index=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("lookups.id"))
    level: Mapped[str | None] = mapped_column(String(50))


class SoldierChild(TimestampMixin, Base):
    __tablename__ = "soldier_children"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    gender: Mapped[str | None] = mapped_column(String(1))
    date_of_birth: Mapped[date | None] = mapped_column(Date)


class SoldierAttachment(TimestampMixin, Base):
    __tablename__ = "soldier_attachments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(255))
    file_name: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(255))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class SoldierHistory(TimestampMixin, Base):
    """Service history: one row per rank/position/unit change (written by decisions)."""

    __tablename__ = "soldier_histories"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # initial / appoint / transfer / promote
    effective_date: Mapped[date | None] = mapped_column(Date)
    old_rank_id: Mapped[int | None] = mapped_column(ForeignKey("ranks.id"))
    new_rank_id: Mapped[int | None] = mapped_column(ForeignKey("ranks.id"))
    old_position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"))
    new_position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"))
    old_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    new_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    note: Mapped[str | None] = mapped_column(String(500))
