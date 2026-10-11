from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import AuditMixin, Base, SoftDeleteMixin, TimestampMixin


class DocumentIncoming(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents_incoming"
    __table_args__ = (UniqueConstraint("incoming_no", "year", name="uq_doc_in_no_year"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    incoming_no: Mapped[str] = mapped_column(String(100))  # លេខឯកសារចូល
    year: Mapped[int] = mapped_column(SmallInteger, index=True)
    subject: Mapped[str] = mapped_column(Text)  # ខ្លឹមសារឯកសារ
    doc_date: Mapped[date] = mapped_column(Date, index=True)
    received_date: Mapped[date | None] = mapped_column(Date)
    document_type_id: Mapped[int | None] = mapped_column(ForeignKey("document_types.id"), index=True)
    from_unit: Mapped[str | None] = mapped_column(String(255))  # មកពីអង្គភាព
    status: Mapped[str] = mapped_column(String(30), default="received")
    remarks: Mapped[str | None] = mapped_column(Text)

    document_type = relationship("DocumentType", lazy="joined")


class DocumentOutgoing(AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents_outgoing"
    __table_args__ = (UniqueConstraint("outgoing_no", "year", name="uq_doc_out_no_year"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    outgoing_no: Mapped[str] = mapped_column(String(100))  # លេខ
    seq: Mapped[int | None] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(SmallInteger, index=True)
    subject: Mapped[str] = mapped_column(Text)
    doc_date: Mapped[date] = mapped_column(Date, index=True)
    document_type_id: Mapped[int | None] = mapped_column(ForeignKey("document_types.id"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))  # អង្គភាព
    recipient_name: Mapped[str | None] = mapped_column(String(255))  # អ្នកទទួល
    recipient_phone: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="sent")
    remarks: Mapped[str | None] = mapped_column(Text)

    document_type = relationship("DocumentType", lazy="joined")
    unit = relationship("Unit", lazy="joined")


class DocumentFile(TimestampMixin, Base):
    __tablename__ = "document_files"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(30), index=True)  # doc_in / doc_out / decision / training / ...
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    file_path: Mapped[str] = mapped_column(String(255))
    file_name: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
