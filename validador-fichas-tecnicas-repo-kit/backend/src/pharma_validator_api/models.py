from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class SourceDocument(Base):
    __tablename__ = "source_document"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(Text)


class SourceDocumentVersion(Base):
    __tablename__ = "source_document_version"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("source_document.id"))
    content_hash: Mapped[str] = mapped_column(String(64))
    source_version: Mapped[str | None] = mapped_column(Text)
    source_locator: Mapped[str] = mapped_column(Text)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceFragment(Base):
    __tablename__ = "source_fragment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("source_document_version.id"))
    locator_type: Mapped[str] = mapped_column(String(40))
    locator: Mapped[str] = mapped_column(Text)
    literal_text: Mapped[str | None] = mapped_column(Text)


class TargetRecord(Base):
    __tablename__ = "target_record"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(80))


class ExternalIdentifier(Base):
    __tablename__ = "external_identifier"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "source_identifier",
            "source_version",
            name="uq_external_identifier_reference",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"))
    source_system: Mapped[str] = mapped_column(String(100))
    source_identifier: Mapped[str] = mapped_column(Text)
    source_version: Mapped[str] = mapped_column(Text)


class DocumentRecordLink(Base):
    __tablename__ = "document_record_link"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("source_document_version.id"))
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"))
    link_type: Mapped[str] = mapped_column(String(80))


class TargetRecordLink(Base):
    __tablename__ = "target_record_link"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"))
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"))
    link_type: Mapped[str] = mapped_column(String(80))
    source_fragment_id: Mapped[str | None] = mapped_column(ForeignKey("source_fragment.id"))


class BlockInstance(Base):
    __tablename__ = "block_instance"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"))
    block_type: Mapped[str] = mapped_column(String(120))
    ordinal: Mapped[int] = mapped_column(Integer)
    source_fragment_id: Mapped[str | None] = mapped_column(ForeignKey("source_fragment.id"))


class FieldValue(Base):
    __tablename__ = "field_value"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    block_instance_id: Mapped[str] = mapped_column(ForeignKey("block_instance.id"))
    field_name: Mapped[str] = mapped_column(String(160))
    literal_value: Mapped[str | None] = mapped_column(Text)
    observed_type: Mapped[str] = mapped_column(String(80))
    logical_state: Mapped[str] = mapped_column(String(80))


class ValueProvenance(Base):
    __tablename__ = "value_provenance"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    field_value_id: Mapped[str] = mapped_column(ForeignKey("field_value.id"))
    source_fragment_id: Mapped[str] = mapped_column(ForeignKey("source_fragment.id"))
    provenance_role: Mapped[str] = mapped_column(String(80))
