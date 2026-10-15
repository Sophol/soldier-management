from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text, func
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
    # the request (សំណើ) that started this decision
    incoming_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents_incoming.id", ondelete="SET NULL"))
    # workflow status: draft -> review -> ... -> leadership -> approved -> published (see core/permissions.py);
    # soldier records change only when published. Also rejected / cancelled (a published decision reverted)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime)  # for "waiting too long" alerts
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))  # top leadership
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["DecisionItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    steps: Mapped[list["DecisionStep"]] = relationship(cascade="all, delete-orphan", order_by="DecisionStep.id")


class DecisionStep(Base):
    """Approval log: who moved the decision from which step to which, when, and their opinion."""

    __tablename__ = "decision_steps"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(20))  # submit / approve / return / reject / publish / cancel
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", lazy="joined")


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
