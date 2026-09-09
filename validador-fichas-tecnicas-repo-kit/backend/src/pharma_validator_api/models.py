from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
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
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("source_document_version.id"), index=True
    )
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


class MaintenanceChangeEvent(Base):
    """Novedad CIMA observada, inmutable e idempotente (DEV-703)."""

    __tablename__ = "maintenance_change_event"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nregistro: Mapped[str] = mapped_column(String(80), index=True)
    occurred_at_epoch: Mapped[int] = mapped_column(Integer)
    change_type: Mapped[int] = mapped_column(Integer)
    areas_json: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[str] = mapped_column(Text)
    old_version_id: Mapped[str | None] = mapped_column(ForeignKey("source_document_version.id"))
    new_version_id: Mapped[str | None] = mapped_column(ForeignKey("source_document_version.id"))
    diff_json: Mapped[str | None] = mapped_column(Text)
    affected_field_count: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MaintenanceRun(Base):
    """Intento operativo diario; su estado permite recuperar fallos visibles."""

    __tablename__ = "maintenance_run"
    __table_args__ = (
        UniqueConstraint("requested_date", "attempt", name="uq_maintenance_run_attempt"),
        Index("ix_maintenance_run_started", "started_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    requested_date: Mapped[str] = mapped_column(String(10), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImmutableHistoryError(RuntimeError):
    pass


@event.listens_for(SourceDocumentVersion, "before_update")
@event.listens_for(SourceDocumentVersion, "before_delete")
@event.listens_for(SourceDocumentArtifact, "before_update")
@event.listens_for(SourceDocumentArtifact, "before_delete")
@event.listens_for(MaintenanceChangeEvent, "before_update")
@event.listens_for(MaintenanceChangeEvent, "before_delete")
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
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"), index=True)
    source_system: Mapped[str] = mapped_column(String(100))
    source_identifier: Mapped[str] = mapped_column(Text)
    source_version: Mapped[str] = mapped_column(Text)


class DocumentRecordLink(Base):
    __tablename__ = "document_record_link"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("source_document_version.id"))
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"), index=True)
    link_type: Mapped[str] = mapped_column(String(80))


class TargetRecordLink(Base):
    __tablename__ = "target_record_link"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"), index=True)
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"), index=True)
    link_type: Mapped[str] = mapped_column(String(80))
    source_fragment_id: Mapped[str | None] = mapped_column(ForeignKey("source_fragment.id"))


class BlockInstance(Base):
    __tablename__ = "block_instance"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"), index=True)
    block_type: Mapped[str] = mapped_column(String(120))
    ordinal: Mapped[int] = mapped_column(Integer)
    source_fragment_id: Mapped[str | None] = mapped_column(ForeignKey("source_fragment.id"))
    # DEV-011: una ocurrencia puede quedar fuera de alcance sin borrarla. Los
    # valores se conservan intactos; marcar es reversible y borrar no lo es.
    not_applicable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Motivo de la última operación de bloque que afectó a esta ocurrencia.
    # El historial completo vive en `block_edit_record`; esto es su resumen.
    edit_comment: Mapped[str | None] = mapped_column(Text)


class FieldValue(Base):
    __tablename__ = "field_value"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    block_instance_id: Mapped[str] = mapped_column(ForeignKey("block_instance.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(160), index=True)
    literal_value: Mapped[str | None] = mapped_column(Text)
    observed_type: Mapped[str] = mapped_column(String(80))
    logical_state: Mapped[str] = mapped_column(String(80))


class ValueProvenance(Base):
    __tablename__ = "value_provenance"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    field_value_id: Mapped[str] = mapped_column(ForeignKey("field_value.id"), index=True)
    source_fragment_id: Mapped[str] = mapped_column(ForeignKey("source_fragment.id"), index=True)
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


class ReviewerRecord(Base):
    """Revisor que puede firmar validaciones (10.1, D-018).

    Los revisores vivían en `APP_REVIEWERS`, una variable de entorno: dar de
    alta a alguien exigía editar el despliegue y reiniciar. Aquí son datos, de
    modo que la lista se gestiona desde la aplicación.

    `active` no se borra nunca: una firma histórica debe seguir diciendo quién
    la puso, y eliminar la fila dejaría decisiones apuntando a un revisor
    inexistente. Desactivar retira del selector sin tocar el pasado.

    `role` decide qué puede firmar cada uno, no es una etiqueta: sólo el
    farmacéutico declara `no_consta` y `no_aplica` (ver `validation_states`).
    """

    __tablename__ = "reviewer"
    __table_args__ = (
        UniqueConstraint("identifier", name="uq_reviewer_identifier"),
        Index("ix_reviewer_active", "active"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    identifier: Mapped[str] = mapped_column(String(80))
    display_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewQueueEntry(Base):
    """Trabajo de revisión de un registro (DEV-502).

    A diferencia de `ValidationDecisionRecord`, esta tabla sí se actualiza: es
    estado de trabajo, no historial de decisiones. La integridad frente a dos
    revisores simultáneos la da `version`, que se compara al escribir; el rastro
    de quién hizo qué vive en el historial de decisiones y en la auditoría.
    """

    __tablename__ = "review_queue_entry"
    __table_args__ = (
        UniqueConstraint("target_record_id", name="uq_review_queue_target_record"),
        Index("ix_review_queue_state_priority", "state", "priority"),
        Index("ix_review_queue_assignee", "assignee_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"))
    state: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer, default=1)
    assignee_id: Mapped[str | None] = mapped_column(String(80))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    review_set: Mapped[str] = mapped_column(String(20), default="corpus", server_default="corpus")
    requires_second_review: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewSession(Base):
    """Sesión de revisión de un registro por un revisor (DEV-508/DEV-509).

    Existe para medir el ahorro de tiempo del sistema, que es el objetivo del
    piloto. **No es un instrumento de control de personas**: agrega tiempo por
    ficha y campo, no productividad individual comparada.
    """

    __tablename__ = "review_session"
    __table_args__ = (
        Index("ix_review_session_record", "target_record_id"),
        Index("ix_review_session_reviewer", "reviewer_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"))
    reviewer_id: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Agregados calculados por `time_measurement`, nunca por la interfaz: el
    # descuento de inactividad debe aplicarse en un único sitio.
    counted_seconds: Mapped[int] = mapped_column(Integer, default=0)
    discarded_seconds: Mapped[int] = mapped_column(Integer, default=0)
    measured_field_count: Mapped[int] = mapped_column(Integer, default=0)
    capped_field_count: Mapped[int] = mapped_column(Integer, default=0)
    # Marca de origen: una medición sintética nunca debe presentarse como
    # evidencia de ahorro farmacéutico real.
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class FieldFocusInterval(Base):
    """Tramo de foco observado en un campo (DEV-508).

    Se guarda el dato crudo además del agregado: si el umbral de inactividad
    cambiara, recalcular exige los intervalos originales. Un agregado no puede
    deshacerse.
    """

    __tablename__ = "field_focus_interval"
    __table_args__ = (Index("ix_field_focus_session", "review_session_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_session_id: Mapped[str] = mapped_column(ForeignKey("review_session.id"))
    field_name: Mapped[str] = mapped_column(String(160))
    started_at: Mapped[float] = mapped_column(Float)
    ended_at: Mapped[float] = mapped_column(Float)


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
        UniqueConstraint("field_value_id", "sequence", name="uq_validation_decision_sequence"),
        # La decisión vigente es la de mayor `sequence` para un campo: el índice
        # compuesto la resuelve sin recorrer el historial completo.
        Index(
            "ix_validation_decision_field_value_sequence",
            "field_value_id",
            "sequence",
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


class BlockEditRecord(Base):
    """Operación de edición de un bloque repetible, append-only (DEV-507).

    Las reglas de qué operación es admisible NO viven aquí: las aplica
    `pharma_validator_api.block_editing`, que es puro, antes de persistir. Esta
    tabla guarda lo que ese módulo ya describió: la operación, las ocurrencias
    afectadas y el motivo declarado por el revisor.

    Es append-only por la misma razón que las decisiones de validación: una
    ocurrencia eliminada o fusionada deja de existir en el modelo canónico, y
    sin este rastro no habría forma de saber qué había antes ni quién lo
    cambió. `before_state` conserva la ocurrencia serializada tal como estaba,
    de modo que fusionar o eliminar no destruya el dato de origen.
    """

    __tablename__ = "block_edit_record"
    __table_args__ = (
        UniqueConstraint("target_record_id", "sequence", name="uq_block_edit_sequence"),
        Index("ix_block_edit_record_sequence", "target_record_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    block_type: Mapped[str] = mapped_column(String(120))
    operation: Mapped[str] = mapped_column(String(40))
    #: Ocurrencias afectadas, en JSON. Una fusión afecta a dos.
    affected_ids: Mapped[str] = mapped_column(Text)
    #: Estado previo de las ocurrencias afectadas, serializado en JSON.
    #: Sin él, eliminar o fusionar perdería el dato de origen sin rastro.
    before_state: Mapped[str] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[str] = mapped_column(String(80))
    reviewer_assurance: Mapped[str] = mapped_column(String(20))
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@event.listens_for(BlockEditRecord, "before_update")
@event.listens_for(BlockEditRecord, "before_delete")
def _reject_block_edit_mutation(*_: object) -> None:
    raise ImmutableHistoryError(
        "El historial de edición de bloques es append-only: registre otra operación."
    )


class AuditEvent(Base):
    """Registro append-only de operaciones relevantes (DEV-609).

    Es un **único** diario transversal, no un segundo sistema paralelo a los
    historiales que ya existen. `validation_decision_record` y
    `block_edit_record` siguen siendo la verdad de sus propios dominios; esta
    tabla los referencia y añade lo que ninguno cubre: segunda revisión,
    conciliación, exportación y exclusión, con el mismo actor y el mismo orden.

    `before_state` y `after_state` guardan el estado serializado a ambos lados
    de la operación. Sin el anterior, un cambio de estado no se puede auditar
    salvo reconstruyéndolo, y reconstruirlo supone confiar en que nada más lo
    tocó.
    """

    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_entity", "entity_type", "entity_id"),
        Index("ix_audit_event_recorded", "recorded_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    #: Qué se tocó: target_record, field_value, block_instance, export_run...
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(60))
    actor_id: Mapped[str] = mapped_column(String(80))
    #: La firma identifica a quien dijo ser, no a quien era (D-018).
    actor_assurance: Mapped[str] = mapped_column(String(20))
    before_state: Mapped[str | None] = mapped_column(Text)
    after_state: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    #: Contexto mínimo en JSON. Nunca datos de paciente.
    context: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def _reject_audit_mutation(*_: object) -> None:
    raise ImmutableHistoryError("La auditoría es append-only: registre otro evento.")


class SecondReviewAssignment(Base):
    """Segunda revisión de un campo ya decidido (DEV-607).

    La ceguera de la segunda revisión no se consigue ocultando en pantalla: se
    consigue no sirviendo el dato. Esta fila declara qué campo está pendiente de
    segunda revisión y quién la tiene asignada; el endpoint que la atiende
    decide, a partir de `revealed`, si puede devolver la primera decisión.

    `first_decision_sequence` ancla la comparación a la decisión concreta que se
    revisó. Sin ella, una tercera decisión posterior haría que el acuerdo o
    desacuerdo se calculase contra algo que el segundo revisor nunca vio.
    """

    __tablename__ = "second_review_assignment"
    __table_args__ = (
        UniqueConstraint("field_value_id", name="uq_second_review_field"),
        Index("ix_second_review_state", "state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    field_value_id: Mapped[str] = mapped_column(ForeignKey("field_value.id"), index=True)
    target_record_id: Mapped[str] = mapped_column(ForeignKey("target_record.id"), index=True)
    #: pendiente | en_revision | acuerdo | desacuerdo | conciliado
    state: Mapped[str] = mapped_column(String(40))
    first_reviewer_id: Mapped[str] = mapped_column(String(80))
    first_decision_sequence: Mapped[int] = mapped_column(Integer)
    second_reviewer_id: Mapped[str | None] = mapped_column(String(80))
    second_decision_sequence: Mapped[int | None] = mapped_column(Integer)
    #: La primera decisión deja de estar oculta sólo tras emitir la segunda.
    revealed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReconciliationRecord(Base):
    """Resolución de una discrepancia entre dos revisores (DEV-608).

    Append-only y **nunca sobrescribe** las decisiones originales: la decisión
    conciliada se persiste como una decisión más en
    `validation_decision_record`, y esta fila explica por qué se tomó y quién la
    tomó. Pisar las dos decisiones enfrentadas destruiría la evidencia de que
    hubo desacuerdo.
    """

    __tablename__ = "reconciliation_record"
    __table_args__ = (UniqueConstraint("assignment_id", name="uq_reconciliation_assignment"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("second_review_assignment.id"), index=True
    )
    field_value_id: Mapped[str] = mapped_column(ForeignKey("field_value.id"), index=True)
    reconciler_id: Mapped[str] = mapped_column(String(80))
    reconciler_assurance: Mapped[str] = mapped_column(String(20))
    #: Secuencia de la decisión conciliada en el historial del campo.
    resulting_sequence: Mapped[int] = mapped_column(Integer)
    #: Conciliar exige justificación: es una decisión clínica, no un desempate.
    justification: Mapped[str] = mapped_column(Text)
    reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@event.listens_for(ReconciliationRecord, "before_update")
@event.listens_for(ReconciliationRecord, "before_delete")
def _reject_reconciliation_mutation(*_: object) -> None:
    raise ImmutableHistoryError("Una conciliación no se reescribe: registre otra decisión.")


class ExportRun(Base):
    """Ejecución archivada de una exportación (DEV-604/605).

    Guarda el metadato, no el fichero: un export de decenas de miles de fichas
    no cabe razonablemente en una fila. `content_hash` permite comprobar que el
    artefacto en disco es el que se declaró.

    La separación entre `content_hash` y `created_at` es lo que hace verificable
    la reproducibilidad: el contenido lógico no depende del reloj, así que dos
    ejecuciones de los mismos datos con el mismo perfil comparten hash aunque
    difieran en fecha.
    """

    __tablename__ = "export_run"
    __table_args__ = (Index("ix_export_run_created", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_name: Mapped[str] = mapped_column(String(120))
    profile_version: Mapped[str] = mapped_column(String(40))
    export_format: Mapped[str] = mapped_column(String(10))
    #: completado | fallido | bloqueado_por_contrato
    status: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str] = mapped_column(String(80))
    row_count: Mapped[int] = mapped_column(Integer)
    excluded_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    #: Ruta del artefacto en disco, si se escribió.
    artifact_path: Mapped[str | None] = mapped_column(Text)
    #: Configuración usada, serializada, para poder repetir la ejecución.
    profile_snapshot: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExportExclusion(Base):
    """Ficha o campo que no pudo exportarse, con su motivo (DEV-604).

    Existe para que un registro problemático no desaparezca en silencio. Un
    export que entrega menos filas de las esperadas sin decir cuáles ni por qué
    es indistinguible de uno correcto.
    """

    __tablename__ = "export_exclusion"
    __table_args__ = (Index("ix_export_exclusion_run", "export_run_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    export_run_id: Mapped[str] = mapped_column(ForeignKey("export_run.id"), index=True)
    target_record_id: Mapped[str] = mapped_column(String(36))
    field_name: Mapped[str | None] = mapped_column(String(160))
    #: bloqueante | advertencia | no_aplicable
    severity: Mapped[str] = mapped_column(String(20))
    rule: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str] = mapped_column(Text)
    #: Estado del campo en el momento de excluirlo.
    observed_state: Mapped[str | None] = mapped_column(String(40))
