from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    event,
)
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


class SourceDocumentArtifact(Base):
    __tablename__ = "source_document_artifact"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "artifact_role",
            "ordinal",
            name="uq_source_document_artifact_occurrence",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("source_document_version.id"))
    artifact_role: Mapped[str] = mapped_column(String(40))
    ordinal: Mapped[int] = mapped_column(Integer)
    locator: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str | None] = mapped_column(Text)
    response_headers: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    body: Mapped[bytes] = mapped_column(LargeBinary)
    fetched_at: Mapped[str] = mapped_column(Text)


class ImmutableHistoryError(RuntimeError):
    pass


@event.listens_for(SourceDocumentVersion, "before_update")
@event.listens_for(SourceDocumentVersion, "before_delete")
@event.listens_for(SourceDocumentArtifact, "before_update")
@event.listens_for(SourceDocumentArtifact, "before_delete")
def _reject_historical_mutation(*_: object) -> None:
    raise ImmutableHistoryError("Las versiones y artefactos documentales son inmutables.")


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


class ImportBatch(Base):
    __tablename__ = "import_batch"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "source_locator",
            "source_version",
            "content_hash",
            "importer_name",
            "importer_version",
            name="uq_import_batch_identity",
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(100))
    source_locator: Mapped[str] = mapped_column(Text)
    source_version: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    importer_name: Mapped[str] = mapped_column(String(120))
    importer_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_document_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_document_version.id")
    )


class ImportDiagnostic(Base):
    __tablename__ = "import_diagnostic"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "diagnostic_key", name="uq_import_diagnostic_key"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batch.id"))
    diagnostic_key: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(80))
    source_locator: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    details_literal: Mapped[str | None] = mapped_column(Text)
    occurrence_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuarantinedSourceRow(Base):
    __tablename__ = "quarantined_source_row"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "quarantine_key", name="uq_quarantined_source_row_key"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batch.id"))
    quarantine_key: Mapped[str] = mapped_column(String(64))
    source_locator: Mapped[str] = mapped_column(Text)
    reason_code: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CatalogFieldDefinition(Base):
    __tablename__ = "catalog_field_definition"
    __table_args__ = (
        UniqueConstraint(
            "import_batch_id", "source_row_number", name="uq_catalog_field_source_row"
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batch.id"))
    sheet_name: Mapped[str] = mapped_column(Text)
    source_row_number: Mapped[int] = mapped_column(Integer)
    sequence_literal: Mapped[str] = mapped_column(Text)
    entity_literal: Mapped[str] = mapped_column(Text)
    block_literal: Mapped[str] = mapped_column(Text)
    field_name_literal: Mapped[str] = mapped_column(Text)
    declared_type_literal: Mapped[str] = mapped_column(Text)
    effective_type: Mapped[str] = mapped_column(Text)
    override_decision: Mapped[str | None] = mapped_column(String(40))
    required_literal: Mapped[str | None] = mapped_column(Text)
    from_ft_literal: Mapped[str | None] = mapped_column(Text)
    ft_section_literal: Mapped[str | None] = mapped_column(Text)
    comment_literal: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[str] = mapped_column(Text)


class ImportedSourceSheet(Base):
    __tablename__ = "imported_source_sheet"
    __table_args__ = (
        UniqueConstraint(
            "import_batch_id", "sheet_ordinal", name="uq_imported_source_sheet_ordinal"
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batch.id"))
    sheet_name: Mapped[str] = mapped_column(Text)
    sheet_ordinal: Mapped[int] = mapped_column(Integer)
    header_row_number: Mapped[int] = mapped_column(Integer)
    header_payload: Mapped[str] = mapped_column(Text)
    data_row_count: Mapped[int] = mapped_column(Integer)
    material_value_count: Mapped[int] = mapped_column(Integer)


class SamplingRun(Base):
    __tablename__ = "sampling_run"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(20))
    seed: Mapped[int] = mapped_column(Integer)
    requested_size: Mapped[int] = mapped_column(Integer)
    eligible_count: Mapped[int] = mapped_column(Integer)
    excluded_count: Mapped[int] = mapped_column(Integer)
    source_snapshot_hash: Mapped[str] = mapped_column(String(64))
    algorithm_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SamplingItem(Base):
    __tablename__ = "sampling_item"
    __table_args__ = (
        UniqueConstraint("sampling_run_id", "ordinal", name="uq_sampling_item_ordinal"),
        UniqueConstraint("sampling_run_id", "nregistro", name="uq_sampling_item_nregistro"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sampling_run_id: Mapped[str] = mapped_column(ForeignKey("sampling_run.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    nregistro: Mapped[str] = mapped_column(Text)
    atc_stratum: Mapped[str | None] = mapped_column(String(20))
    source_response_hash: Mapped[str] = mapped_column(String(64))


class ValidationDecisionRecord(Base):
    """Evento de decisión de revisión, append-only (DEV-506 / ADR-0004).

    No hay UPDATE ni DELETE: revertir una decisión se registra como otro evento,
    porque sobrescribir borraría la autoría sin rastro. El estado vigente de un
    campo es el evento de mayor `sequence` para ese `field_value_id`.

    Las reglas de qué decisión es legítima NO viven aquí: las aplica
    `pharma_validator_api.validation_states` antes de persistir.
    """

    __tablename__ = "validation_decision_record"
    __table_args__ = (
        UniqueConstraint(
            "field_value_id", "sequence", name="uq_validation_decision_sequence"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    field_value_id: Mapped[str] = mapped_column(ForeignKey("field_value.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    field_name: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(40))
    final_value: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[str] = mapped_column(String(80))
    reviewer_role: Mapped[str] = mapped_column(String(40))
    # 10.1: la firma identifica quién dijo ser, no quién era (D-018).
    reviewer_assurance: Mapped[str] = mapped_column(String(20))
    seconds_spent: Mapped[int | None] = mapped_column(Integer)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@event.listens_for(ValidationDecisionRecord, "before_update")
@event.listens_for(ValidationDecisionRecord, "before_delete")
def _reject_decision_mutation(*_: object) -> None:
    raise ImmutableHistoryError(
        "Las decisiones de validación son append-only: registre otra decisión."
    )
