"""API de consulta read-only sobre lo que Farmalidación ya tiene almacenado.

Este módulo no calcula nada clínico ni decide nada: agrega lo que hay en la
base de datos para que la interfaz pueda responder a «qué datos tenemos, de
dónde vienen y cuánto se ha cargado».

Regla que atraviesa todo el módulo: una métrica que no puede calcularse con
garantías no se estima, se declara `None` y la interfaz la omite. Un número
inventado en un panel de estado es peor que un hueco, porque nadie lo audita.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session, sessionmaker

from pharma_validator_api.data_origin import (
    DataOrigin,
    apply_origin_filter,
    origin_for_record,
    origins_for_records,
)
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import (
    BlockInstance,
    CatalogFieldDefinition,
    DocumentRecordLink,
    FieldValue,
    ImportBatch,
    ImportDiagnostic,
    ImportedSourceSheet,
    QuarantinedSourceRow,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
    ValidationDecisionRecord,
    ValueProvenance,
)

router = APIRouter(prefix="/insights", tags=["consulta"])


def get_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    with factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]

#: Campos que sirven como nombre visible, en orden de preferencia. Son nombres
#: reales del catálogo de maestros; no se compone un nombre a partir de otros.
DISPLAY_NAME_FIELDS = (
    "ME_DESCRIPCION",
    "PA_DESCRIPCION",
    "ES_DESCRIPCION",
    "DESCRIPCION",
    "NOMBRE",
)
#: Campos que actúan como identificador externo del maestro.
IDENTIFIER_FIELDS = (
    "ME_IDEXTERNO",
    "PA_IDEXTERNO",
    "ES_IDEXTERNO",
    "MED_IDEXTERNO",
    "IDEXTERNO",
)


class MetricRead(BaseModel):
    """Una cifra del panel, con la etiqueta que la explica."""

    key: str
    label: str
    value: int


class PipelineStageRead(BaseModel):
    key: str
    label: str
    #: `disponible`, `parcial`, `pendiente`. Derivado de datos, nunca fijado.
    status: str
    detail: str


class DashboardRead(BaseModel):
    metrics: list[MetricRead]
    pipeline: list[PipelineStageRead]
    last_import_at: str | None
    #: `true` cuando no hay ningún dato real cargado todavía. La interfaz lo usa
    #: para explicar el vacío en lugar de mostrar una pantalla en blanco.
    empty: bool


class SourceRead(BaseModel):
    key: str
    name: str
    source_type: str
    status: str
    versions: int
    latest_version: str | None
    latest_content_hash: str | None
    last_updated_at: str | None
    batches: int
    records: int
    diagnostics: int
    quarantined_rows: int


class SourceSheetRead(BaseModel):
    sheet_name: str
    sheet_ordinal: int
    data_row_count: int
    material_value_count: int


class SourceDetailRead(SourceRead):
    sheets: list[SourceSheetRead]
    batch_ids: list[str]


class ImportRead(BaseModel):
    id: str
    source_system: str
    source_locator: str
    source_version: str | None
    content_hash: str
    importer_name: str
    importer_version: str
    status: str
    created_at: str
    completed_at: str | None
    processed_rows: int | None
    retained_records: int
    quarantined_rows: int
    diagnostics: int
    errors: int


class IncidentRead(BaseModel):
    severity: str
    code: str
    message: str
    source_locator: str | None
    occurrence_count: int


class ImportDetailRead(ImportRead):
    sheets: list[SourceSheetRead]
    incidents: list[IncidentRead]


class ImportListRead(BaseModel):
    items: list[ImportRead]
    total: int


class SourceListRead(BaseModel):
    items: list[SourceRead]
    total: int


class RecordRowRead(BaseModel):
    id: str
    entity_type: str
    origin: str
    display_name: str | None
    identifier: str | None
    source_system: str | None
    block_count: int
    field_count: int


class RecordPageRead(BaseModel):
    items: list[RecordRowRead]
    total: int
    limit: int
    offset: int


class ValueProvenanceRead(BaseModel):
    source_system: str | None
    document_name: str | None
    source_locator: str | None
    source_version: str | None
    content_hash: str | None
    locator: str
    locator_type: str
    provenance_role: str
    import_batch_id: str | None


class RecordValueRead(BaseModel):
    id: str
    field_name: str
    literal_value: str | None
    observed_type: str
    logical_state: str
    provenance: list[ValueProvenanceRead]


class RecordBlockRead(BaseModel):
    id: str
    block_type: str
    ordinal: int
    values: list[RecordValueRead]


class RecordSourceAvailabilityRead(BaseModel):
    key: str
    label: str
    status: str
    detail: str


class RecordDetailRead(BaseModel):
    id: str
    entity_type: str
    origin: str
    display_name: str | None
    identifier: str | None
    blocks: list[RecordBlockRead]
    sources: list[RecordSourceAvailabilityRead]


def _count(session: Session, statement: Select[tuple[str]]) -> int:
    return int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)


def _scalar_count(session: Session, model: type, *conditions: ColumnElement[bool]) -> int:
    statement = select(func.count()).select_from(model)
    for condition in conditions:
        statement = statement.where(condition)
    return int(session.scalar(statement) or 0)


@router.get("/dashboard", response_model=DashboardRead)
def read_dashboard(session: SessionDependency) -> DashboardRead:
    """Cifras reales del sistema.

    Todas proceden de un `count` sobre el modelo físico. Ninguna se estima ni se
    fija: si una tabla está vacía la cifra es 0 y el panel lo dice.
    """
    real_records = _count(
        session, apply_origin_filter(select(TargetRecord.id), DataOrigin.REAL)
    )
    demo_records = _count(
        session, apply_origin_filter(select(TargetRecord.id), DataOrigin.DEMO)
    )
    medications = _count(
        session,
        apply_origin_filter(
            select(TargetRecord.id).where(TargetRecord.entity_type == "medication"),
            DataOrigin.REAL,
        ),
    )
    active_ingredients = _count(
        session,
        apply_origin_filter(
            select(TargetRecord.id).where(TargetRecord.entity_type == "active_ingredient"),
            DataOrigin.REAL,
        ),
    )
    specialties = _count(
        session,
        apply_origin_filter(
            select(TargetRecord.id).where(TargetRecord.entity_type == "specialty"),
            DataOrigin.REAL,
        ),
    )
    documents = _scalar_count(session, SourceDocument)
    document_versions = _scalar_count(session, SourceDocumentVersion)
    batches = _scalar_count(session, ImportBatch)
    catalog_fields = _scalar_count(session, CatalogFieldDefinition)
    field_values = _scalar_count(session, FieldValue)
    quarantined = _scalar_count(session, QuarantinedSourceRow)
    diagnostics = _scalar_count(session, ImportDiagnostic)
    decisions = _scalar_count(session, ValidationDecisionRecord)
    reviewed_values = int(
        session.scalar(
            select(func.count(func.distinct(ValidationDecisionRecord.field_value_id)))
        )
        or 0
    )

    metrics = [
        MetricRead(key="real_records", label="Registros reales", value=real_records),
        MetricRead(key="medications", label="Medicamentos", value=medications),
        MetricRead(
            key="active_ingredients", label="Principios activos", value=active_ingredients
        ),
        MetricRead(key="specialties", label="Especialidades", value=specialties),
        MetricRead(key="catalog_fields", label="Campos de catálogo", value=catalog_fields),
        MetricRead(key="field_values", label="Valores almacenados", value=field_values),
        MetricRead(key="documents", label="Documentos de origen", value=documents),
        MetricRead(
            key="document_versions", label="Versiones documentales", value=document_versions
        ),
        MetricRead(key="batches", label="Importaciones", value=batches),
        MetricRead(key="reviewed_values", label="Valores revisados", value=reviewed_values),
        MetricRead(key="decisions", label="Decisiones registradas", value=decisions),
        MetricRead(key="quarantined", label="Filas en cuarentena", value=quarantined),
        MetricRead(key="diagnostics", label="Incidencias de importación", value=diagnostics),
        MetricRead(key="demo_records", label="Registros DEMO", value=demo_records),
    ]

    last_import = session.scalar(
        select(ImportBatch.created_at).order_by(ImportBatch.created_at.desc()).limit(1)
    )

    #: Los estados se derivan de la presencia real de datos. «Extracción» y
    #: «Exportación» no tienen todavía tabla propia: se declaran pendientes en
    #: lugar de fingir un estado que nadie podría comprobar.
    def stage(key: str, label: str, present: int, detail_present: str) -> PipelineStageRead:
        return PipelineStageRead(
            key=key,
            label=label,
            status="disponible" if present else "pendiente",
            detail=detail_present if present else "Sin datos cargados todavía.",
        )

    pipeline = [
        stage(
            "maestros",
            "Maestros Excel",
            real_records,
            f"{real_records} registros importados desde los maestros.",
        ),
        stage(
            "catalogo",
            "Catálogo de campos",
            catalog_fields,
            f"{catalog_fields} definiciones de campo importadas.",
        ),
        PipelineStageRead(
            key="cima",
            label="CIMA",
            status="pendiente",
            detail=(
                "No hay documentos CIMA asociados a registros en la base de datos."
                if not _scalar_count(session, SourceDocument, SourceDocument.source_type == "cima")
                else "Documentos CIMA presentes."
            ),
        ),
        stage(
            "validacion",
            "Validación",
            decisions,
            f"{decisions} decisiones de revisión firmadas.",
        ),
        PipelineStageRead(
            key="extraccion",
            label="Extracción de fichas técnicas",
            status="pendiente",
            detail="La extracción asistida no forma parte de esta vertical.",
        ),
        PipelineStageRead(
            key="exportacion",
            label="Exportación",
            status="pendiente",
            detail="Sin destino de exportación configurado.",
        ),
    ]

    return DashboardRead(
        metrics=metrics,
        pipeline=pipeline,
        last_import_at=last_import.isoformat() if last_import else None,
        empty=real_records == 0 and catalog_fields == 0 and batches == 0,
    )


SourceRow = tuple[SourceDocument, int, int, datetime | None, str | None, str | None]


def _source_rows(session: Session) -> list[SourceRow]:
    rows = list(
        session.execute(
            select(
                SourceDocument,
                func.count(func.distinct(SourceDocumentVersion.id)),
                func.count(func.distinct(DocumentRecordLink.target_record_id)),
                func.max(SourceDocumentVersion.acquired_at),
                func.max(SourceDocumentVersion.source_version),
                func.max(SourceDocumentVersion.content_hash),
            )
            .outerjoin(
                SourceDocumentVersion,
                SourceDocumentVersion.document_id == SourceDocument.id,
            )
            .outerjoin(
                DocumentRecordLink,
                DocumentRecordLink.document_version_id == SourceDocumentVersion.id,
            )
            .group_by(SourceDocument.id)
            .order_by(SourceDocument.source_type, SourceDocument.name)
        ).all()
    )
    return [row._tuple() for row in rows]


def _batches_for_document(session: Session, document_id: str) -> list[ImportBatch]:
    return list(
        session.scalars(
            select(ImportBatch)
            .join(
                SourceDocumentVersion,
                ImportBatch.source_document_version_id == SourceDocumentVersion.id,
            )
            .where(SourceDocumentVersion.document_id == document_id)
            .order_by(ImportBatch.created_at.desc())
        ).all()
    )


def _source_payload(session: Session, row: SourceRow) -> SourceRead:
    document, versions, records, acquired, version_label, content_hash = row
    batches = _batches_for_document(session, document.id)
    batch_ids = [batch.id for batch in batches]
    diagnostics = (
        _scalar_count(session, ImportDiagnostic, ImportDiagnostic.import_batch_id.in_(batch_ids))
        if batch_ids
        else 0
    )
    quarantined = (
        _scalar_count(
            session, QuarantinedSourceRow, QuarantinedSourceRow.import_batch_id.in_(batch_ids)
        )
        if batch_ids
        else 0
    )
    if any(batch.status == "failed" for batch in batches):
        status = "con_errores"
    elif records or versions:
        status = "disponible"
    else:
        status = "sin_datos"
    return SourceRead(
        key=document.id,
        name=document.name,
        source_type=document.source_type,
        status=status,
        versions=int(versions or 0),
        latest_version=version_label,
        latest_content_hash=content_hash,
        last_updated_at=acquired.isoformat() if acquired else None,
        batches=len(batch_ids),
        records=int(records or 0),
        diagnostics=diagnostics,
        quarantined_rows=quarantined,
    )


@router.get("/sources", response_model=SourceListRead)
def list_sources(session: SessionDependency) -> SourceListRead:
    """Fuentes realmente conocidas por el sistema, con su estado de carga."""
    items = [_source_payload(session, row) for row in _source_rows(session)]
    return SourceListRead(items=items, total=len(items))


@router.get("/sources/{source_id}", response_model=SourceDetailRead)
def read_source(source_id: str, session: SessionDependency) -> SourceDetailRead:
    rows = [row for row in _source_rows(session) if row[0].id == source_id]
    if not rows:
        raise ApplicationError("Fuente no encontrada.", status_code=404)
    base = _source_payload(session, rows[0])
    batches = _batches_for_document(session, source_id)
    batch_ids = [batch.id for batch in batches]
    sheets = (
        list(
            session.scalars(
                select(ImportedSourceSheet)
                .where(ImportedSourceSheet.import_batch_id.in_(batch_ids))
                .order_by(ImportedSourceSheet.sheet_ordinal)
            ).all()
        )
        if batch_ids
        else []
    )
    return SourceDetailRead(
        **base.model_dump(),
        batch_ids=batch_ids,
        sheets=[
            SourceSheetRead(
                sheet_name=sheet.sheet_name,
                sheet_ordinal=sheet.sheet_ordinal,
                data_row_count=sheet.data_row_count,
                material_value_count=sheet.material_value_count,
            )
            for sheet in sheets
        ],
    )


def _import_payload(session: Session, batch: ImportBatch) -> ImportRead:
    processed = session.scalar(
        select(func.sum(ImportedSourceSheet.data_row_count)).where(
            ImportedSourceSheet.import_batch_id == batch.id
        )
    )
    retained = (
        _scalar_count(
            session,
            DocumentRecordLink,
            DocumentRecordLink.document_version_id == batch.source_document_version_id,
        )
        if batch.source_document_version_id
        else _scalar_count(
            session, CatalogFieldDefinition, CatalogFieldDefinition.import_batch_id == batch.id
        )
    )
    return ImportRead(
        id=batch.id,
        source_system=batch.source_system,
        source_locator=batch.source_locator,
        source_version=batch.source_version,
        content_hash=batch.content_hash,
        importer_name=batch.importer_name,
        importer_version=batch.importer_version,
        status=batch.status,
        created_at=batch.created_at.isoformat(),
        completed_at=batch.completed_at.isoformat() if batch.completed_at else None,
        processed_rows=int(processed) if processed is not None else None,
        retained_records=retained,
        quarantined_rows=_scalar_count(
            session, QuarantinedSourceRow, QuarantinedSourceRow.import_batch_id == batch.id
        ),
        diagnostics=_scalar_count(
            session, ImportDiagnostic, ImportDiagnostic.import_batch_id == batch.id
        ),
        errors=_scalar_count(
            session,
            ImportDiagnostic,
            ImportDiagnostic.import_batch_id == batch.id,
            ImportDiagnostic.severity == "error",
        ),
    )


@router.get("/imports", response_model=ImportListRead)
def list_imports(session: SessionDependency) -> ImportListRead:
    """Lotes de importación ya ejecutados, del más reciente al más antiguo."""
    batches = list(
        session.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc())).all()
    )
    items = [_import_payload(session, batch) for batch in batches]
    return ImportListRead(items=items, total=len(items))


@router.get("/imports/{batch_id}", response_model=ImportDetailRead)
def read_import(batch_id: str, session: SessionDependency) -> ImportDetailRead:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise ApplicationError("Importación no encontrada.", status_code=404)
    base = _import_payload(session, batch)
    sheets = session.scalars(
        select(ImportedSourceSheet)
        .where(ImportedSourceSheet.import_batch_id == batch_id)
        .order_by(ImportedSourceSheet.sheet_ordinal)
    ).all()
    diagnostics = session.scalars(
        select(ImportDiagnostic)
        .where(ImportDiagnostic.import_batch_id == batch_id)
        .order_by(ImportDiagnostic.severity, ImportDiagnostic.code)
        .limit(200)
    ).all()
    return ImportDetailRead(
        **base.model_dump(),
        sheets=[
            SourceSheetRead(
                sheet_name=sheet.sheet_name,
                sheet_ordinal=sheet.sheet_ordinal,
                data_row_count=sheet.data_row_count,
                material_value_count=sheet.material_value_count,
            )
            for sheet in sheets
        ],
        incidents=[
            IncidentRead(
                severity=item.severity,
                code=item.code,
                message=item.message,
                source_locator=item.source_locator,
                occurrence_count=item.occurrence_count,
            )
            for item in diagnostics
        ],
    )


def _identity_by_record(
    session: Session, record_ids: list[str]
) -> tuple[dict[str, str], dict[str, str], dict[str, int], dict[str, int]]:
    """Nombre, identificador y recuentos de una página, en un único recorrido.

    Sin índice sobre `field_value.block_instance_id` cada consulta de valores
    recorre la tabla entera (más de dos millones de filas con los maestros
    reales cargados), así que el coste real no está en cuántas filas se piden
    sino en cuántas veces se recorre. Aquí se recorre una sola vez y se reparte
    el resultado en memoria, en lugar de una consulta por dato mostrado.

    La necesidad del índice queda documentada en `docs/REAL_DATA_UI_HANDOFF.md`:
    esta vertical no crea migraciones.
    """
    if not record_ids:
        return {}, {}, {}, {}
    block_owner: dict[str, str] = {
        block_id: owner
        for block_id, owner in session.execute(
            select(BlockInstance.id, BlockInstance.target_record_id).where(
                BlockInstance.target_record_id.in_(record_ids)
            )
        ).all()
    }
    blocks_per_record: dict[str, int] = {}
    for owner in block_owner.values():
        blocks_per_record[owner] = blocks_per_record.get(owner, 0) + 1
    if not block_owner:
        return {}, {}, {}, {}

    wanted = set(DISPLAY_NAME_FIELDS) | set(IDENTIFIER_FIELDS)
    name_rank = {name: index for index, name in enumerate(DISPLAY_NAME_FIELDS)}
    id_rank = {name: index for index, name in enumerate(IDENTIFIER_FIELDS)}
    names: dict[str, tuple[int, str]] = {}
    identifiers: dict[str, tuple[int, str]] = {}
    values_per_record: dict[str, int] = {}

    rows = session.execute(
        select(
            FieldValue.block_instance_id,
            FieldValue.field_name,
            FieldValue.literal_value,
        ).where(FieldValue.block_instance_id.in_(list(block_owner)))
    ).all()
    for block_id, field_name, literal in rows:
        owner_or_none = block_owner.get(block_id)
        if owner_or_none is None:
            continue
        owner = owner_or_none
        values_per_record[owner] = values_per_record.get(owner, 0) + 1
        if field_name not in wanted or not literal:
            continue
        if field_name in name_rank:
            current = names.get(owner)
            if current is None or name_rank[field_name] < current[0]:
                names[owner] = (name_rank[field_name], literal)
        if field_name in id_rank:
            current = identifiers.get(owner)
            if current is None or id_rank[field_name] < current[0]:
                identifiers[owner] = (id_rank[field_name], literal)

    return (
        {key: value for key, (_, value) in names.items()},
        {key: value for key, (_, value) in identifiers.items()},
        blocks_per_record,
        values_per_record,
    )


@router.get("/records", response_model=RecordPageRead)
def list_records(
    session: SessionDependency,
    origin: DataOrigin = DataOrigin.REAL,
    q: str | None = None,
    entity_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RecordPageRead:
    """Listado paginado de registros, separado por origen REAL o DEMO.

    El origen es un parámetro obligatorio con valor por defecto REAL: no existe
    una consulta que mezcle ambos conjuntos, porque mezclarlos es precisamente
    lo que esta vertical debe impedir.
    """
    statement = apply_origin_filter(select(TargetRecord.id), origin)
    if entity_type:
        statement = statement.where(TargetRecord.entity_type == entity_type)

    if q:
        needle = f"%{q.strip()}%"
        matching = (
            select(BlockInstance.target_record_id)
            .join(FieldValue, FieldValue.block_instance_id == BlockInstance.id)
            .where(FieldValue.field_name.in_(DISPLAY_NAME_FIELDS + IDENTIFIER_FIELDS))
            .where(FieldValue.literal_value.ilike(needle))
        )
        statement = statement.where(TargetRecord.id.in_(matching))

    total = _count(session, statement)
    page_ids = list(
        session.scalars(statement.order_by(TargetRecord.id).limit(limit).offset(offset)).all()
    )
    if not page_ids:
        return RecordPageRead(items=[], total=total, limit=limit, offset=offset)

    records = {
        record.id: record
        for record in session.scalars(
            select(TargetRecord).where(TargetRecord.id.in_(page_ids))
        ).all()
    }
    names, identifiers, counts, value_counts = _identity_by_record(session, page_ids)
    origins = origins_for_records(session, page_ids)
    systems: dict[str, str] = {
        record: system
        for record, system in session.execute(
            select(DocumentRecordLink.target_record_id, func.min(SourceDocument.source_type))
            .join(
                SourceDocumentVersion,
                DocumentRecordLink.document_version_id == SourceDocumentVersion.id,
            )
            .join(SourceDocument, SourceDocumentVersion.document_id == SourceDocument.id)
            .where(DocumentRecordLink.target_record_id.in_(page_ids))
            .group_by(DocumentRecordLink.target_record_id)
        ).all()
    }

    items = [
        RecordRowRead(
            id=record_id,
            entity_type=records[record_id].entity_type,
            origin=origins[record_id].value,
            display_name=names.get(record_id),
            identifier=identifiers.get(record_id),
            source_system=systems.get(record_id),
            block_count=int(counts.get(record_id, 0)),
            field_count=int(value_counts.get(record_id, 0)),
        )
        for record_id in page_ids
    ]
    return RecordPageRead(items=items, total=total, limit=limit, offset=offset)


@router.get("/records/{record_id}", response_model=RecordDetailRead)
def read_record(record_id: str, session: SessionDependency) -> RecordDetailRead:
    """Ficha completa con la procedencia de cada valor."""
    record = session.get(TargetRecord, record_id)
    if record is None:
        raise ApplicationError("Registro no encontrado.", status_code=404)

    blocks = list(
        session.scalars(
            select(BlockInstance)
            .where(BlockInstance.target_record_id == record_id)
            .order_by(BlockInstance.block_type, BlockInstance.ordinal)
        ).all()
    )
    block_ids = [block.id for block in blocks]
    values = (
        list(
            session.scalars(
                select(FieldValue)
                .where(FieldValue.block_instance_id.in_(block_ids))
                .order_by(FieldValue.block_instance_id, FieldValue.field_name)
            ).all()
        )
        if block_ids
        else []
    )

    # Procedencia de todos los valores de la ficha en una sola consulta, en
    # lugar de una por campo.
    provenance_rows = (
        session.execute(
            select(
                ValueProvenance.field_value_id,
                ValueProvenance.provenance_role,
                SourceFragment.locator,
                SourceFragment.locator_type,
                SourceDocument.name,
                SourceDocument.source_type,
                SourceDocumentVersion.source_locator,
                SourceDocumentVersion.source_version,
                SourceDocumentVersion.content_hash,
                ImportBatch.id,
            )
            .join(SourceFragment, ValueProvenance.source_fragment_id == SourceFragment.id)
            .join(
                SourceDocumentVersion,
                SourceFragment.document_version_id == SourceDocumentVersion.id,
            )
            .join(SourceDocument, SourceDocumentVersion.document_id == SourceDocument.id)
            .outerjoin(
                ImportBatch,
                ImportBatch.source_document_version_id == SourceDocumentVersion.id,
            )
            .where(ValueProvenance.field_value_id.in_([value.id for value in values]))
        ).all()
        if values
        else []
    )
    provenance: dict[str, list[ValueProvenanceRead]] = {}
    for row in provenance_rows:
        provenance.setdefault(row[0], []).append(
            ValueProvenanceRead(
                provenance_role=row[1],
                locator=row[2],
                locator_type=row[3],
                document_name=row[4],
                source_system=row[5],
                source_locator=row[6],
                source_version=row[7],
                content_hash=row[8],
                import_batch_id=row[9],
            )
        )

    by_block: dict[str, list[RecordValueRead]] = {}
    for value in values:
        by_block.setdefault(value.block_instance_id, []).append(
            RecordValueRead(
                id=value.id,
                field_name=value.field_name,
                literal_value=value.literal_value,
                observed_type=value.observed_type,
                logical_state=value.logical_state,
                provenance=provenance.get(value.id, []),
            )
        )

    present_types = {
        row
        for row in session.scalars(
            select(SourceDocument.source_type)
            .join(
                SourceDocumentVersion,
                SourceDocumentVersion.document_id == SourceDocument.id,
            )
            .join(
                DocumentRecordLink,
                DocumentRecordLink.document_version_id == SourceDocumentVersion.id,
            )
            .where(DocumentRecordLink.target_record_id == record_id)
        ).all()
    }

    #: Sólo se declara «disponible» lo que está enlazado a este registro. La
    #: vinculación Maestro↔CIMA no existe todavía en el modelo, de modo que se
    #: anuncia como pendiente en vez de insinuar una asociación no verificada.
    sources = [
        RecordSourceAvailabilityRead(
            key="maestro",
            label="Maestro",
            status="disponible" if "master_excel" in present_types else "no_disponible",
            detail=(
                "Registro importado desde los maestros Excel."
                if "master_excel" in present_types
                else "Sin origen de maestro enlazado."
            ),
        ),
        RecordSourceAvailabilityRead(
            key="cima",
            label="CIMA",
            status="disponible" if "cima" in present_types else "pendiente",
            detail=(
                "Documento CIMA enlazado a este registro."
                if "cima" in present_types
                else "Vinculación con CIMA pendiente: el modelo no almacena todavía "
                "una correspondencia verificada entre el maestro y el nregistro de CIMA."
            ),
        ),
        RecordSourceAvailabilityRead(
            key="ficha_tecnica",
            label="Ficha técnica",
            status="disponible" if "ficha_tecnica" in present_types else "no_disponible",
            detail=(
                "Ficha técnica enlazada."
                if "ficha_tecnica" in present_types
                else "Sin ficha técnica asociada a este registro."
            ),
        ),
        RecordSourceAvailabilityRead(
            key="extraccion",
            label="Extracción",
            status="no_disponible",
            detail="La extracción asistida no forma parte de esta vertical.",
        ),
    ]

    names, identifiers, _, _ = _identity_by_record(session, [record_id])

    return RecordDetailRead(
        id=record.id,
        entity_type=record.entity_type,
        origin=origin_for_record(session, record_id).value,
        display_name=names.get(record_id),
        identifier=identifiers.get(record_id),
        blocks=[
            RecordBlockRead(
                id=block.id,
                block_type=block.block_type,
                ordinal=block.ordinal,
                values=by_block.get(block.id, []),
            )
            for block in blocks
        ],
        sources=sources,
    )
