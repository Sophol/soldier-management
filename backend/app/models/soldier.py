from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import AuditMixin, Base, SoftDeleteMixin, TimestampMixin


class Soldier(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "soldiers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    military_id: Mapped[str] = mapped_column(String(50), unique=True)  # អត្តលេខ
    name_kh: Mapped[str] = mapped_column(String(255), index=True)  # គោត្តនាមនិងនាម
    name_latin: Mapped[str | None] = mapped_column(String(255), index=True)
    gender: Mapped[str] = mapped_column(String(1))  # M / F
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    national_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    photo_path: Mapped[str | None] = mapped_column(String(255))
    blood_type_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))

    birth_village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"))
    birth_place_text: Mapped[str | None] = mapped_column(String(500))
    current_village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"))
    current_address_text: Mapped[str | None] = mapped_column(String(500))

    # current service state (cache of the latest history row)
    current_rank_id: Mapped[int | None] = mapped_column(ForeignKey("ranks.id"), index=True)
    rank_date: Mapped[date | None] = mapped_column(Date)
    current_position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"), index=True)
    position_date: Mapped[date | None] = mapped_column(Date)
    current_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True)
    unit_transfer_date: Mapped[date | None] = mapped_column(Date)
    from_unit_text: Mapped[str | None] = mapped_column(String(255))  # មកពីស្ថាប័នកងឯកភាព
    enlistment_date: Mapped[date | None] = mapped_column(Date)

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
