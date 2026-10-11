from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

# Unit levels: 1 ស្ថាប័នកងឯកភាព, 2 អង្គភាព, 3 អង្គភាពរង, 4 អង្គភាពចំណុះផ្ទាល់
UNIT_LEVELS = {1: "ស្ថាប័នកងឯកភាព", 2: "អង្គភាព", 3: "អង្គភាពរង", 4: "អង្គភាពចំណុះផ្ទាល់"}


class Unit(TimestampMixin, Base):
    __tablename__ = "units"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    level: Mapped[int] = mapped_column(SmallInteger, default=1)
    code: Mapped[str | None] = mapped_column(String(50))
    name_kh: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    # materialised path like "/1/5/12/" for fast subtree queries
    path: Mapped[str] = mapped_column(String(500), default="/", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    parent: Mapped["Unit | None"] = relationship(remote_side="Unit.id")


class RankClass(TimestampMixin, Base):
    __tablename__ = "rank_classes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_kh: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Rank(TimestampMixin, Base):
    __tablename__ = "ranks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rank_class_id: Mapped[int] = mapped_column(ForeignKey("rank_classes.id"), index=True)
    name_kh: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    short_kh: Mapped[str | None] = mapped_column(String(50))
    # higher value = higher rank; used to validate promotions
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    min_years_to_next: Mapped[int | None] = mapped_column(SmallInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    rank_class: Mapped[RankClass] = relationship()


class Position(TimestampMixin, Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_kh: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Specialty(TimestampMixin, Base):
    __tablename__ = "specialties"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_kh: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DocumentType(TimestampMixin, Base):
    __tablename__ = "document_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_kh: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    direction: Mapped[str] = mapped_column(String(10), default="both")  # in / out / both
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# Generic small lookup lists, grouped by category
LOOKUP_CATEGORIES = {
    "soldier_status": "ស្ថានភាពយោធិន",
    "education_level": "កម្រិតវប្បធម៌",
    "language": "ភាសាបរទេស",
    "blood_type": "ប្រភេទឈាម",
    "marital_status": "ស្ថានភាពគ្រួសារ",
    "occupation": "មុខរបរ",
    "award_type": "ប្រភេទសរសើរ/គ្រឿងឥស្សរិយយស",
    "discipline_type": "ប្រភេទទណ្ឌកម្ម",
    "separation_reason": "មូលហេតុចេញពីជួរ",
}


class Lookup(TimestampMixin, Base):
    __tablename__ = "lookups"
    __table_args__ = (UniqueConstraint("category", "code", name="uq_lookup_category_code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    code: Mapped[str | None] = mapped_column(String(50))
    name_kh: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
