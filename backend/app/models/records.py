"""Training, discipline, awards, retirement, separation and strength movement records."""

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import AuditMixin, Base, SoftDeleteMixin, TimestampMixin


class TrainingCourse(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "training_courses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    course_type: Mapped[str] = mapped_column(String(20), index=True)  # long / short
    level: Mapped[str] = mapped_column(String(20), default="basic")  # basic បណ្ដុះបណ្ដាល / refresher បំប៉ន
    sector: Mapped[str] = mapped_column(String(10), default="military")  # military យោធា / civil ស៊ីវិល
    specialty_id: Mapped[int | None] = mapped_column(ForeignKey("specialties.id"))
    institution: Mapped[str | None] = mapped_column(String(255))
    country_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    participants: Mapped[list["TrainingParticipant"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class TrainingParticipant(TimestampMixin, Base):
    __tablename__ = "training_participants"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("training_courses.id", ondelete="CASCADE"), index=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="studying")  # studying / completed / dropped
    result: Mapped[str | None] = mapped_column(String(100))  # លទ្ធផល/ថ្នាក់
    certificate_no: Mapped[str | None] = mapped_column(String(100))

    soldier = relationship("Soldier", lazy="joined")


class DisciplineRecord(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "discipline_records"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id"), index=True)
    discipline_type_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    level: Mapped[str | None] = mapped_column(String(100))  # កម្រិតទោស
    reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(255))  # អ្នកសម្រេច
    # status: cancelled (លុបចោល) when set; otherwise in force until end_date, then expired (ផុតកំណត់)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    decision_no: Mapped[str | None] = mapped_column(String(100))
    decision_date: Mapped[date | None] = mapped_column(Date)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    soldier = relationship("Soldier", lazy="joined")
    discipline_type = relationship("Lookup", lazy="joined")


class AwardRecord(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "award_records"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id"), index=True)
    award_type_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    level: Mapped[str | None] = mapped_column(String(100))  # កម្រិត/ថ្នាក់
    awarded_by: Mapped[str | None] = mapped_column(String(255))  # អ្នកផ្ដល់
    reason: Mapped[str | None] = mapped_column(Text)
    decision_no: Mapped[str | None] = mapped_column(String(100))
    decision_date: Mapped[date | None] = mapped_column(Date)

    soldier = relationship("Soldier", lazy="joined")
    award_type = relationship("Lookup", lazy="joined")


class RetirementRecord(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "retirement_records"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id"), index=True)
    # pension (គ្រប់អាយុ) / voluntary (ស្ម័គ្រចិត្ត) / disability (ពិការ) / death (ស្លាប់) / category2
    type: Mapped[str] = mapped_column(String(20))
    case_status: Mapped[str] = mapped_column(String(20), default="submitted")  # submitted / processing / done
    decision_no: Mapped[str | None] = mapped_column(String(100))
    decision_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date] = mapped_column(Date)
    pension_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    # soldier status/unit before this record, restored if the record is deleted
    previous_status_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    previous_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))

    soldier = relationship("Soldier", lazy="joined")


class SeparationRecord(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "separation_records"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id"), index=True)
    reason_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    decision_no: Mapped[str | None] = mapped_column(String(100))
    decision_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    # soldier status/unit before this record, restored if the record is deleted
    previous_status_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    previous_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))

    soldier = relationship("Soldier", lazy="joined")
    reason = relationship("Lookup", lazy="joined", foreign_keys=[reason_id])


class StrengthMovement(TimestampMixin, Base):
    """ការងារកើនថយ: every soldier entering (in) or leaving (out) a unit's strength."""

    __tablename__ = "strength_movements"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True)
    direction: Mapped[str] = mapped_column(String(3))  # in / out
    reason: Mapped[str] = mapped_column(String(50))  # recruit / transfer_in / transfer_out / retire / category2 / separate / reinstate
    movement_date: Mapped[date] = mapped_column(Date, index=True)
    source_table: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(String(500))

    soldier = relationship("Soldier", lazy="joined")
    unit = relationship("Unit", lazy="joined")


class MilitaryCard(AuditMixin, SoftDeleteMixin, Base):
    """អត្តសញ្ញាណប័ណ្ណយោធិន: one row per card issued (a replacement is a new row; the old one becomes replaced)."""

    __tablename__ = "military_cards"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id"), index=True)
    card_no: Mapped[str | None] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # issued / pending / lost / replaced
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    soldier = relationship("Soldier", lazy="joined")
