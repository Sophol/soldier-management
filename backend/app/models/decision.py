from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import AuditMixin, Base, SoftDeleteMixin, TimestampMixin

DECISION_KINDS = {"appoint": "តែងតាំងមុខតំណែង", "transfer": "ផ្លាស់ប្ដូរ", "promote": "ដំឡើងឋានន្តរស័ក្តិ"}


class Decision(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    decision_no: Mapped[str] = mapped_column(String(100))
    decision_date: Mapped[date] = mapped_column(Date)
    effective_date: Mapped[date] = mapped_column(Date)
    issued_by: Mapped[str | None] = mapped_column(String(255))
    outgoing_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents_outgoing.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft / approved / cancelled
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["DecisionItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class DecisionItem(TimestampMixin, Base):
    __tablename__ = "decision_items"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    soldier_id: Mapped[int] = mapped_column(ForeignKey("soldiers.id"), index=True)
    old_rank_id: Mapped[int | None] = mapped_column(ForeignKey("ranks.id"))
    new_rank_id: Mapped[int | None] = mapped_column(ForeignKey("ranks.id"))
    old_position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"))
    new_position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"))
    old_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    new_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    # dates before approval, so a cancelled decision restores them exactly
    old_rank_date: Mapped[date | None] = mapped_column(Date)
    old_position_date: Mapped[date | None] = mapped_column(Date)
    old_unit_date: Mapped[date | None] = mapped_column(Date)
    old_from_unit_text: Mapped[str | None] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(String(500))

    soldier = relationship("Soldier", lazy="joined")
