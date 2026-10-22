"""Military service conscription (យុវជនបំពេញកាតព្វកិច្ចយោធា): the person, registrations, medical exams
and service periods, in separate tables linked by conscript_id (answer.txt)."""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import AuditMixin, Base, SoftDeleteMixin

REGISTRATION_STATUSES = {
    "registered": "ចុះឈ្មោះ", "called": "ត្រូវបានហៅ", "served": "បានបម្រើ",
    "exempted": "ទទួលការលើកលែង", "deferred": "ពន្យារ",
}
EXEMPTION_REASONS = {"study": "សិក្សា", "health": "សុខភាព", "family": "គ្រួសារ", "other": "ផ្សេងៗ"}
MEDICAL_RESULTS = {"pass": "ជាប់", "fail": "ធ្លាក់", "deferred": "ពន្យារ"}


class Conscript(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "conscripts"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conscript_no: Mapped[str] = mapped_column(String(50), unique=True)  # លេខសម្គាល់យោធា / លេខសម្គាល់ខ្លួន
    name_kh: Mapped[str] = mapped_column(String(255), index=True)
    name_latin: Mapped[str | None] = mapped_column(String(255), index=True)
    gender: Mapped[str] = mapped_column(String(1))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    birth_village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"))
    birth_place_text: Mapped[str | None] = mapped_column(String(500))
    nationality: Mapped[str | None] = mapped_column(String(50), default="ខ្មែរ")
    national_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    father_name: Mapped[str | None] = mapped_column(String(255))
    mother_name: Mapped[str | None] = mapped_column(String(255))
    current_village_id: Mapped[int | None] = mapped_column(ForeignKey("villages.id"))
    current_address_text: Mapped[str | None] = mapped_column(String(500))  # ផ្ទះលេខ ផ្លូវ
    phone: Mapped[str | None] = mapped_column(String(50))
    photo_path: Mapped[str | None] = mapped_column(String(255))
    marital_status_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    spouse_name: Mapped[str | None] = mapped_column(String(255))
    children_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    education_level_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    specialty_id: Mapped[int | None] = mapped_column(ForeignKey("specialties.id"))
    blood_type_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    spouse_job_id: Mapped[int | None] = mapped_column(ForeignKey("lookups.id"))
    profession: Mapped[str | None] = mapped_column(String(255))  # ជំនាញ/វិជ្ជាជីវៈ
    languages: Mapped[str | None] = mapped_column(String(255))
    driving_license: Mapped[str | None] = mapped_column(String(100))  # ប័ណ្ណបើកបរ (ប្រភេទ)
    notes: Mapped[str | None] = mapped_column(Text)


class ConscriptRegistration(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "conscript_registrations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conscript_id: Mapped[int] = mapped_column(ForeignKey("conscripts.id", ondelete="CASCADE"), index=True)
    register_no: Mapped[str | None] = mapped_column(String(50))  # លេខសម្គាល់បញ្ជីកាតព្វកិច្ច
    registration_year: Mapped[int] = mapped_column(SmallInteger, index=True)
    duty_year: Mapped[int | None] = mapped_column(SmallInteger)
    province_id: Mapped[int | None] = mapped_column(ForeignKey("provinces.id"), index=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    status: Mapped[str] = mapped_column(String(20), default="registered", index=True)
    reason: Mapped[str | None] = mapped_column(String(20))  # exemption / deferral reason
    reason_note: Mapped[str | None] = mapped_column(String(500))

    conscript = relationship("Conscript", lazy="joined")


class ConscriptMedical(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "conscript_medicals"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conscript_id: Mapped[int] = mapped_column(ForeignKey("conscripts.id", ondelete="CASCADE"), index=True)
    exam_date: Mapped[date] = mapped_column(Date)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 1))
    result: Mapped[str] = mapped_column(String(20))
    examiner: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    conscript = relationship("Conscript", lazy="joined")


class ConscriptService(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "conscript_services"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conscript_id: Mapped[int] = mapped_column(ForeignKey("conscripts.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    unit_text: Mapped[str | None] = mapped_column(String(255))  # កងពល/កងវរសេនាធំ outside the unit tree
    rank_id: Mapped[int | None] = mapped_column(ForeignKey("ranks.id"))
    role: Mapped[str | None] = mapped_column(String(255))  # តួនាទី
    trainings: Mapped[str | None] = mapped_column(Text)
    awards_discipline: Mapped[str | None] = mapped_column(Text)
    order_no: Mapped[str | None] = mapped_column(String(100))  # លេខបញ្ជា/សេចក្ដីសម្រេច

    conscript = relationship("Conscript", lazy="joined")
    unit = relationship("Unit", lazy="joined")
    rank = relationship("Rank", lazy="joined")
