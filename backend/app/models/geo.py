from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Province(TimestampMixin, Base):
    __tablename__ = "provinces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name_kh: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), default="ខេត្ត")  # រាជធានី / ខេត្ត
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    districts: Mapped[list["District"]] = relationship(back_populates="province")


class District(TimestampMixin, Base):
    __tablename__ = "districts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), index=True)
    name_kh: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), default="ស្រុក")  # ស្រុក / ក្រុង / ខណ្ឌ
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    province: Mapped[Province] = relationship(back_populates="districts")


class Commune(TimestampMixin, Base):
    __tablename__ = "communes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    name_kh: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), default="ឃុំ")  # ឃុំ / សង្កាត់
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    district: Mapped[District] = relationship()


class Village(TimestampMixin, Base):
    __tablename__ = "villages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    commune_id: Mapped[int] = mapped_column(ForeignKey("communes.id"), index=True)
    name_kh: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    commune: Mapped[Commune] = relationship()


class Country(TimestampMixin, Base):
    __tablename__ = "countries"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name_kh: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
