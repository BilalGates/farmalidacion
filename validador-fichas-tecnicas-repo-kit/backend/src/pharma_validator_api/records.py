from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from pharma_validator_api.config import Settings, get_settings
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import (
    BlockInstance,
    ExternalIdentifier,
    FieldMaintenanceRevision,
    FieldValue,
    ReviewQueueEntry,
    SecondReviewAssignment,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)
from pharma_validator_api.prefill_policy import field_prefill_policy, plan_field_presentation
from pharma_validator_api.review import (
    BULK_CHUNK,
    CurrentDecision,
    chunked,
    current_decisions_for,
    decision_history,
    effective_state,
    evaluate_field_conflict,
    evaluate_field_conflict_from,
    provenance_for,
    record_decision_in_transaction,
)
from pharma_validator_api.review_queue import DEFAULT_LEASE
from pharma_validator_api.reviewer_identity import (
    ROLE_LABELS,
    ReviewerDirectory,
    ReviewerIdentityError,
)
from pharma_validator_api.reviewer_store import directory_from_database
from pharma_validator_api.risk_rules import assess
from pharma_validator_api.second_review_store import open_second_review
from pharma_validator_api.validation_states import (
    ValidationDecision,
    ValidationState,
    ValidationStateError,
)

router = APIRouter(prefix="/records", tags=["registros"])


def _open_required_second_reviews(session: Session, *, target_record_id: str, actor_id: str) -> int:
    """Abre la segunda lectura de todos los campos ya decididos de un L04."""
    values = list(
        session.scalars(
            select(FieldValue)
            .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
            .where(BlockInstance.target_record_id == target_record_id)
        ).all()
    )
    decisions = current_decisions_for(session, [item.id for item in values])
    atc_values = [item for item in values if item.field_name.strip().upper() == "ATC"]

    def effective_literal(item: FieldValue) -> str | None:
        decision = decisions.get(item.id)
        return (decision.final_value if decision else None) or item.literal_value

    atc = next((value for item in atc_values if (value := effective_literal(item))), None)
    if assess(atc).requires_double_review is not True:
        return 0
    existing = set(
        session.scalars(
            select(SecondReviewAssignment.field_value_id).where(
                SecondReviewAssignment.target_record_id == target_record_id
            )
        ).all()
    )
    opened = 0
    for item in values:
        if item.id not in decisions or item.id in existing:
            continue
        open_second_review(session, field_value_id=item.id, actor_id=actor_id)
        opened += 1
    session.execute(
        update(ReviewQueueEntry)
        .where(ReviewQueueEntry.target_record_id == target_record_id)
        .values(requires_second_review=True, updated_at=datetime.now(UTC))
    )
    return opened


class ExternalIdentifierRead(BaseModel):
    source_system: str
    source_identifier: str
    source_version: str


class ProvenanceRead(BaseModel):
    source_fragment_id: str
    document_version_id: str
    locator_type: str
    locator: str
    literal_text: str | None
    provenance_role: str


class DecisionRead(BaseModel):
    sequence: int
    state: str
    final_value: str | None
    comment: str | None
    reviewer_id: str
    reviewer_assurance: str
    decided_at: str


class FieldMaintenanceRead(BaseModel):
    sequence: int
    before_value: str | None
    after_value: str | None
    actor_id: str
    actor_assurance: str
    reason: str
    recorded_at: str


class FieldValueRead(BaseModel):
    id: str
    field_name: str
    source_column_index: int | None = None
    literal_value: str | None
    maintained_value: str | None = None
    maintenance_sequence: int = 0
    maintenance_history: list[FieldMaintenanceRead] = Field(default_factory=list)
    observed_type: str
    logical_state: str
    provenance: list[ProvenanceRead]
    validation_state: str
    #: Estado de conflicto según ADR-0007. Sin matriz de prioridad cargada, un
    #: conflicto real permanece sin resolver y exige acción humana.
    conflict_status: str
    has_conflict: bool
    history: list[DecisionRead]
    #: Política de pre-relleno aplicada al campo (especificación 9, DEV-512).
    #: Mientras `enable_llm_prefill` siga apagada por D-015, todos los campos
    #: se sirven como `solo_evidencia`: se muestra la fuente y no se sugiere
    #: ningún valor. Es el comportamiento conservador, no una limitación
    #: temporal que la pantalla pueda saltarse.
    prefill_policy: str
    prefill_presentation: str
    #: Valor propuesto. `None` en toda política protegida, por construcción.
    proposed_value: str | None
    prefill_options: list[str]
    #: Aviso que acompaña al campo cuando la decisión es criterio clínico.
    prefill_warning: str | None


class BlockInstanceRead(BaseModel):
    id: str
    block_type: str
    ordinal: int
    values: list[FieldValueRead]


class TargetRecordRead(BaseModel):
    id: str
    entity_type: str
    external_identifiers: list[ExternalIdentifierRead]
    blocks: list[BlockInstanceRead]


class RecordSummaryRead(BaseModel):
    """Fila del listado. No colapsa ocurrencias: informa cuántas hay."""

    id: str
    entity_type: str
    display_name: str | None
    active_ingredient: str | None
    primary_identifier: str | None
    block_count: int
    field_count: int
    pending_count: int
    resolved_count: int
    conflict_count: int
    review_state: str
    last_reviewed_at: str | None


class RecordListRead(BaseModel):
    items: list[RecordSummaryRead]
    total: int


class ReviewerRead(BaseModel):
    identifier: str
    display_name: str
    assurance: str
    role: str
    role_label: str
    #: Si puede declarar `no_consta` y `no_aplica`. Se envía calculado para que
    #: la pantalla no reimplemente la regla y pueda discrepar de ella.
    may_sign_pharmacist_states: bool


class DecisionWrite(BaseModel):
    """Petición de decisión. Las reglas las aplica `validation_states`."""

    state: ValidationState
    reviewer_id: str
    # El rol NO se acepta del cliente: sale del directorio al resolver al
    # revisor. Aceptarlo permitía a cualquiera declararse farmacéutico y firmar
    # `no_consta` o `no_aplica`, que es justo lo que la regla debía impedir.
    final_value: str | None = None
    comment: str | None = None
    seconds_spent: int | None = None
    applicable_sources: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    reviewed_sources: list[str] = Field(default_factory=list)
    field_required: bool = False


class FieldMaintenanceWrite(BaseModel):
    expected_sequence: int = Field(ge=0)
    value: str | None = None
    actor_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=2000)


def get_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    with factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


def get_reviewer_directory(request: Request, session: SessionDependency) -> ReviewerDirectory:
    """Directorio de revisores, de la base de datos.

    La configuración `APP_REVIEWERS` queda como respaldo para una base todavía
    sin revisores: un despliegue existente no puede quedarse sin poder firmar
    porque la tabla esté vacía. En cuanto hay uno dado de alta, manda la base.
    """
    from_database = directory_from_database(session)
    if from_database.reviewers:
        return from_database
    settings = cast(Settings, getattr(request.app.state, "settings", None) or get_settings())
    return ReviewerDirectory.from_configuration(settings.reviewers)


DirectoryDependency = Annotated[ReviewerDirectory, Depends(get_reviewer_directory)]

#: Nombres de campo que identifican un registro en el listado. Provienen del
#: catálogo real; no se inventa semántica ni se deduce de otros campos.
DISPLAY_NAME_FIELDS = ("ME_DESCRIPCION", "DESCRIPCION", "NOMBRE")
ACTIVE_INGREDIENT_FIELDS = ("PA_DESCRIPCION", "PRINCIPIO_ACTIVO")


def _provenance(session: Session, field_value_id: str) -> list[ProvenanceRead]:
    rows = session.scalars(
        select(ValueProvenance)
        .where(ValueProvenance.field_value_id == field_value_id)
        .order_by(ValueProvenance.id)
    ).all()
    result = []
    for row in rows:
        fragment = session.get(SourceFragment, row.source_fragment_id)
        if fragment is None:
            raise RuntimeError(f"Procedencia sin fragmento: {row.id}")
        result.append(
            ProvenanceRead(
                source_fragment_id=fragment.id,
                document_version_id=fragment.document_version_id,
                locator_type=fragment.locator_type,
                locator=fragment.locator,
                literal_text=fragment.literal_text,
                provenance_role=row.provenance_role,
            )
        )
    return result


def _first_value(session: Session, record_id: str, names: tuple[str, ...]) -> str | None:
    """Primer valor literal de los campos indicados, en el orden declarado.

    Devuelve `None` si ninguno existe. No se compone un nombre a partir de otros
    campos: un identificador inventado sería indistinguible de uno importado.
    """
    for name in names:
        value = session.scalars(
            select(FieldValue)
            .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
            .where(BlockInstance.target_record_id == record_id)
            .where(FieldValue.field_name == name)
            .where(FieldValue.literal_value.is_not(None))
            .order_by(BlockInstance.ordinal, FieldValue.id)
            .limit(1)
        ).first()
        if value is not None:
            return value.literal_value
    return None


def _field_group_key(value: FieldValue) -> tuple[str, str, int | None]:
    """Separa cabeceras duplicadas, pero conserva evidencia del mismo campo fuente."""
    return (value.block_instance_id, value.field_name, value.source_column_index)


def _group_by_field(
    session: Session, values: Sequence[FieldValue]
) -> dict[tuple[str, str, int | None], tuple[FieldValue, ...]]:
    """Agrupa valores por ocurrencia de bloque y nombre de campo.

    Agrupar por nombre de campo a secas fusionaría ocurrencias distintas del
    mismo bloque repetible, que es exactamente lo que la regla de ocurrencias
    explícitas prohíbe.
    """
    grouped: dict[tuple[str, str, int | None], list[FieldValue]] = {}
    for value in values:
        grouped.setdefault(_field_group_key(value), []).append(value)
    return {key: tuple(items) for key, items in grouped.items()}


def _summarize_many(session: Session, records: Sequence[TargetRecord]) -> list[RecordSummaryRead]:
    """Resume una página entera de registros con un número fijo de consultas.

    Resumir de uno en uno costaba una consulta por campo para la decisión
    vigente y otras tantas por procedencia y fragmento. Con los maestros reales
    una página de 50 registros ronda los 2.500 campos, así que pintarla exigía
    del orden de miles de consultas y el listado no llegaba a responder.

    Aquí todo lo que depende de la página se carga en bloque y el resumen se
    calcula en memoria. Las reglas no cambian: son las mismas de `review`, sólo
    que alimentadas desde diccionarios ya cargados.
    """
    if not records:
        return []
    record_ids = [record.id for record in records]

    blocks_by_record: dict[str, list[BlockInstance]] = {rid: [] for rid in record_ids}
    blocks_by_id: dict[str, BlockInstance] = {}
    for chunk in chunked(record_ids, BULK_CHUNK):
        for block in session.scalars(
            select(BlockInstance).where(BlockInstance.target_record_id.in_(chunk))
        ).all():
            blocks_by_record[block.target_record_id].append(block)
            blocks_by_id[block.id] = block

    values_by_record: dict[str, list[FieldValue]] = {rid: [] for rid in record_ids}
    for chunk in chunked(record_ids, BULK_CHUNK):
        rows = session.execute(
            select(FieldValue, BlockInstance.target_record_id)
            .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
            .where(BlockInstance.target_record_id.in_(chunk))
            .order_by(FieldValue.id)
        ).all()
        for value, target_record_id in rows:
            values_by_record[target_record_id].append(value)

    value_ids = [value.id for values in values_by_record.values() for value in values]
    decisions = current_decisions_for(session, value_ids)
    provenance = provenance_for(session, value_ids)
    identifiers = _primary_identifiers(session, record_ids)

    return [
        _summarize_loaded(
            record,
            blocks_by_record[record.id],
            values_by_record[record.id],
            blocks_by_id,
            decisions,
            provenance,
            identifiers.get(record.id),
        )
        for record in records
    ]


def _primary_identifiers(session: Session, record_ids: Sequence[str]) -> dict[str, str]:
    """Identificador externo principal de cada registro, en bloque.

    El principal es el primero por sistema y valor, igual que en el resumen de
    uno en uno; ordenar aquí y quedarse con el primero visto da el mismo.
    """
    primeros: dict[str, str] = {}
    for chunk in chunked(record_ids, BULK_CHUNK):
        for row in session.scalars(
            select(ExternalIdentifier)
            .where(ExternalIdentifier.target_record_id.in_(chunk))
            .order_by(
                ExternalIdentifier.source_system,
                ExternalIdentifier.source_identifier,
            )
        ).all():
            primeros.setdefault(row.target_record_id, row.source_identifier)
    return primeros


def _first_loaded_value(values: Sequence[FieldValue], names: tuple[str, ...]) -> str | None:
    """Primer valor literal de los campos indicados, sobre valores ya cargados.

    Mismo criterio que `_first_value`: se respeta el orden declarado de `names`,
    y sólo cuenta el que tiene literal. No se compone un nombre a partir de
    otros campos.
    """
    for name in names:
        for value in values:
            if value.field_name == name and value.literal_value is not None:
                return value.literal_value
    return None


def _summarize_loaded(
    record: TargetRecord,
    blocks: Sequence[BlockInstance],
    values: Sequence[FieldValue],
    blocks_by_id: dict[str, BlockInstance],
    decisions: dict[str, CurrentDecision],
    provenance: dict[str, tuple[tuple[ValueProvenance, SourceFragment], ...]],
    primary_identifier: str | None,
) -> RecordSummaryRead:
    """Calcula el resumen de un registro sin tocar la base de datos."""
    pending = resolved = conflicts = 0
    last_reviewed = None
    for value in values:
        decision = decisions.get(value.id)
        if decision is None or decision.state in ("pendiente", "revision_pendiente"):
            pending += 1
        else:
            resolved += 1
        if decision is not None and (last_reviewed is None or decision.decided_at > last_reviewed):
            last_reviewed = decision.decided_at
    # La discrepancia se cuenta por campo dentro de la ocurrencia, no por fila:
    # dos fuentes que discrepan producen dos filas y el conflicto vive entre ellas.
    grouped: dict[tuple[str, str, int | None], list[FieldValue]] = {}
    for value in values:
        grouped.setdefault(_field_group_key(value), []).append(value)
    for (block_id, field_name, _column), group in grouped.items():
        block = blocks_by_id.get(block_id)
        block_type = block.block_type if block is not None else "desconocido"
        evaluation = evaluate_field_conflict_from(
            provenance, tuple(group), 1, record.entity_type, block_type, field_name
        )
        if evaluation.has_conflict:
            conflicts += 1
    if conflicts:
        review_state = "requiere_revision"
    elif pending and resolved:
        review_state = "en_revision"
    elif pending:
        review_state = "pendiente"
    else:
        review_state = "validado"
    # `_first_loaded_value` recorre los valores del registro en el mismo orden
    # que traía la consulta, que es `FieldValue.id`. `_first_value` ordenaba por
    # `(BlockInstance.ordinal, FieldValue.id)`, así que se ordena igual aquí.
    ordered = sorted(
        values,
        key=lambda value: (
            blocks_by_id[value.block_instance_id].ordinal
            if value.block_instance_id in blocks_by_id
            else 0,
            value.id,
        ),
    )
    return RecordSummaryRead(
        id=record.id,
        entity_type=record.entity_type,
        display_name=_first_loaded_value(ordered, DISPLAY_NAME_FIELDS),
        active_ingredient=_first_loaded_value(ordered, ACTIVE_INGREDIENT_FIELDS),
        primary_identifier=primary_identifier,
        block_count=len(blocks),
        field_count=len(values),
        pending_count=pending,
        resolved_count=resolved,
        conflict_count=conflicts,
        review_state=review_state,
        last_reviewed_at=last_reviewed.isoformat() if last_reviewed else None,
    )


def _summarize(session: Session, record: TargetRecord) -> RecordSummaryRead:
    """Resumen de un solo registro. Envoltorio de `_summarize_many`."""
    return _summarize_many(session, [record])[0]


# Tamaño del tramo al filtrar por `estado`. Ni tan pequeño que multiplique las
# consultas, ni tan grande que resuma cientos de registros para descartarlos.
_ESTADO_SCAN_CHUNK = 100


def _search_predicate(needle: str) -> ColumnElement[bool]:
    """Preselección en SQL de los registros que `q` puede llegar a casar.

    Cubre los mismos orígenes que `_matches`: el identificador del registro, los
    identificadores externos y los campos de nombre y principio activo.

    La comparación se hace sobre `lower()` en ambos lados y **no** con `LIKE` a
    secas: `LIKE` sólo ignora mayúsculas para ASCII, de modo que buscar
    `MAGNÉSICO` no encontraba `magnésico` y la preselección descartaba filas que
    `_matches` sí aceptaba. Con acentos, que abundan en los nombres de principio
    activo, eso vaciaba la búsqueda.

    Es deliberadamente amplia: `_matches` sigue siendo quien decide, y esto sólo
    descarta lo que con certeza no coincide. Los acentos no se normalizan, aquí
    ni allí: `magnesico` no encuentra `magnésico`, igual que antes.
    """
    pattern = f"%{needle.lower()}%"
    named_fields = DISPLAY_NAME_FIELDS + ACTIVE_INGREDIENT_FIELDS
    return or_(
        func.lower(TargetRecord.id).like(pattern),
        TargetRecord.id.in_(
            select(ExternalIdentifier.target_record_id).where(
                func.lower(ExternalIdentifier.source_identifier).like(pattern)
            )
        ),
        TargetRecord.id.in_(
            select(BlockInstance.target_record_id)
            .join(FieldValue, FieldValue.block_instance_id == BlockInstance.id)
            .where(FieldValue.field_name.in_(named_fields))
            .where(func.lower(FieldValue.literal_value).like(pattern))
        ),
    )


def _matches(item: RecordSummaryRead, needle: str) -> bool:
    """Coincidencia literal, sin normalizar acentos (misma regla que antes)."""
    folded = needle.casefold()
    return (
        folded in (item.display_name or "").casefold()
        or folded in (item.active_ingredient or "").casefold()
        or folded in (item.primary_identifier or "").casefold()
        or folded in item.id.casefold()
    )


@router.get("", response_model=RecordListRead)
def list_records(
    session: SessionDependency,
    q: str | None = None,
    estado: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> RecordListRead:
    """Listado paginado de registros con su estado de revisión agregado.

    La búsqueda es literal y sin acentuación normalizada: normalizar cambiaría
    lo que el usuario escribió por lo que la herramienta supone que quiso decir.

    El resumen de un registro recorre sus ocurrencias, valores, decisiones y
    conflictos, así que cuesta proporcionalmente a su tamaño. Con los maestros
    reales importados (7.189 registros) resumirlos todos para devolver una
    página tardaba horas: por eso sólo se resume la página pedida. `estado` es
    la excepción y está documentada abajo.
    """
    query = select(TargetRecord).order_by(TargetRecord.id)
    if q is not None:
        # `q` se compara contra valores que sí son columnas, así que el descarte
        # ocurre en la base de datos. Sin esto habría que resumir cada registro
        # sólo para averiguar que no coincide: con los maestros reales, buscar
        # un principio activo concreto costaba minutos.
        query = query.where(_search_predicate(q))
    if estado is None:
        # `estado` es el único filtro que exige resumir. Sin él, el recuento y el
        # recorte ocurren en la base de datos y sólo se resume la página.
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        records = session.scalars(query.offset(offset).limit(limit)).all()
        summaries = _summarize_many(session, records)
        if q is not None:
            # La preselección es deliberadamente amplia; `_matches` decide.
            summaries = [item for item in summaries if _matches(item, q)]
        return RecordListRead(items=summaries, total=total)

    # `estado` se deriva del resumen, no es una columna, así que filtrar por él
    # exige resumir. Se recorre por tramos y se para en cuanto la página está
    # completa, en lugar de resumir el maestro entero.
    matched: list[RecordSummaryRead] = []
    scanned = 0
    needed = offset + limit
    while True:
        batch = session.scalars(query.offset(scanned).limit(_ESTADO_SCAN_CHUNK)).all()
        if not batch:
            break
        scanned += len(batch)
        for summary in _summarize_many(session, batch):
            if estado is not None and summary.review_state != estado:
                continue
            if q is not None and not _matches(summary, q):
                continue
            matched.append(summary)
        if len(matched) >= needed:
            break
    # `total` cuenta las coincidencias halladas hasta donde se ha recorrido, que
    # con un filtro activo puede ser menos que el maestro completo: afirmar un
    # total exacto exigiría resumirlo entero, que es lo que se evita.
    return RecordListRead(items=matched[offset : offset + limit], total=len(matched))


@router.get("/reviewers", response_model=list[ReviewerRead])
def list_reviewers(directory: DirectoryDependency) -> list[ReviewerRead]:
    """Lista configurable de revisores (10.1). Vacía si no se ha configurado."""
    return [
        ReviewerRead(
            identifier=item.identifier,
            display_name=item.display_name,
            assurance=item.assurance,
            role=item.role,
            role_label=ROLE_LABELS[item.role],
            may_sign_pharmacist_states=item.may_sign_pharmacist_states,
        )
        for item in directory.reviewers
    ]


@router.get("/{record_id}", response_model=TargetRecordRead)
def read_record(record_id: str, session: SessionDependency) -> TargetRecordRead:
    record = session.get(TargetRecord, record_id)
    if record is None:
        raise ApplicationError("Registro no encontrado.", status_code=404)
    identifiers = session.scalars(
        select(ExternalIdentifier)
        .where(ExternalIdentifier.target_record_id == record_id)
        .order_by(
            ExternalIdentifier.source_system,
            ExternalIdentifier.source_identifier,
            ExternalIdentifier.source_version,
        )
    ).all()
    blocks = session.scalars(
        select(BlockInstance)
        .where(BlockInstance.target_record_id == record_id)
        .order_by(BlockInstance.ordinal, BlockInstance.id)
    ).all()
    block_payloads = []
    for block in blocks:
        values = session.scalars(
            select(FieldValue)
            .where(FieldValue.block_instance_id == block.id)
            .order_by(FieldValue.field_name, FieldValue.id)
        ).all()
        grouped = _group_by_field(session, values)
        block_payloads.append(
            BlockInstanceRead(
                id=block.id,
                block_type=block.block_type,
                ordinal=block.ordinal,
                values=[
                    _read_field_value(
                        session,
                        value,
                        record,
                        block,
                        grouped[_field_group_key(value)],
                    )
                    for value in values
                ],
            )
        )
    return TargetRecordRead(
        id=record.id,
        entity_type=record.entity_type,
        external_identifiers=[
            ExternalIdentifierRead(
                source_system=item.source_system,
                source_identifier=item.source_identifier,
                source_version=item.source_version,
            )
            for item in identifiers
        ],
        blocks=block_payloads,
    )


@router.post(
    "/values/{field_value_id}/maintenance", response_model=FieldMaintenanceRead, status_code=201
)
def maintain_field_value(
    field_value_id: str,
    payload: FieldMaintenanceWrite,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> FieldMaintenanceRead:
    """Corrige el valor de trabajo sin alterar el literal ni emitir una decisión clínica."""
    value = session.get(FieldValue, field_value_id)
    if value is None:
        raise ApplicationError("Campo no encontrado.", status_code=404)
    current = session.scalar(
        select(FieldMaintenanceRevision)
        .where(FieldMaintenanceRevision.field_value_id == field_value_id)
        .order_by(FieldMaintenanceRevision.sequence.desc())
        .limit(1)
    )
    current_sequence = current.sequence if current else 0
    if payload.expected_sequence != current_sequence:
        raise ApplicationError(
            "El campo cambió desde que lo abrió. Recargue antes de guardar.",
            status_code=409,
        )
    reason = payload.reason.strip()
    if not reason:
        raise ApplicationError("Indique el motivo del cambio.", status_code=400)
    if payload.value == (current.after_value if current else value.literal_value):
        raise ApplicationError("El valor nuevo es igual al valor vigente.", status_code=400)
    try:
        actor = directory.resolve(payload.actor_id)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error
    revision = FieldMaintenanceRevision(
        field_value_id=field_value_id,
        sequence=current_sequence + 1,
        before_value=current.after_value if current else value.literal_value,
        after_value=payload.value,
        actor_id=actor.identifier,
        actor_assurance=actor.assurance,
        reason=reason,
        recorded_at=datetime.now(UTC),
    )
    session.add(revision)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApplicationError(
            "El campo se modificó en paralelo. Recargue antes de guardar.",
            status_code=409,
        ) from error
    return FieldMaintenanceRead(
        sequence=revision.sequence,
        before_value=revision.before_value,
        after_value=revision.after_value,
        actor_id=revision.actor_id,
        actor_assurance=revision.actor_assurance,
        reason=revision.reason,
        recorded_at=revision.recorded_at.isoformat(),
    )


def _read_field_value(
    session: Session,
    value: FieldValue,
    record: TargetRecord,
    block: BlockInstance,
    siblings: tuple[FieldValue, ...],
) -> FieldValueRead:
    evaluation = evaluate_field_conflict(
        session, siblings, 1, record.entity_type, block.block_type, value.field_name
    )
    plan = plan_field_presentation(
        value.field_name,
        field_prefill_policy(session, value.field_name),
    )
    maintenance_history = session.scalars(
        select(FieldMaintenanceRevision)
        .where(FieldMaintenanceRevision.field_value_id == value.id)
        .order_by(FieldMaintenanceRevision.sequence)
    ).all()
    latest_maintenance = maintenance_history[-1] if maintenance_history else None
    return FieldValueRead(
        id=value.id,
        field_name=value.field_name,
        source_column_index=value.source_column_index,
        literal_value=value.literal_value,
        maintained_value=(
            latest_maintenance.after_value if latest_maintenance else value.literal_value
        ),
        maintenance_sequence=latest_maintenance.sequence if latest_maintenance else 0,
        maintenance_history=[
            FieldMaintenanceRead(
                sequence=item.sequence,
                before_value=item.before_value,
                after_value=item.after_value,
                actor_id=item.actor_id,
                actor_assurance=item.actor_assurance,
                reason=item.reason,
                recorded_at=item.recorded_at.isoformat(),
            )
            for item in maintenance_history
        ],
        observed_type=value.observed_type,
        logical_state=value.logical_state,
        provenance=_provenance(session, value.id),
        validation_state=effective_state(session, value.id),
        conflict_status=evaluation.status,
        has_conflict=evaluation.has_conflict,
        prefill_policy=plan.policy,
        prefill_presentation=plan.presentation,
        proposed_value=plan.prefilled_value,
        prefill_options=list(plan.options),
        prefill_warning=plan.warning,
        history=[
            DecisionRead(
                sequence=item.sequence,
                state=item.state,
                final_value=item.final_value,
                comment=item.comment,
                reviewer_id=item.reviewer_id,
                reviewer_assurance=item.reviewer_assurance,
                decided_at=item.decided_at.isoformat(),
            )
            for item in decision_history(session, value.id)
        ],
    )


@router.post("/values/{field_value_id}/decisions", response_model=DecisionRead, status_code=201)
def save_decision(
    request: Request,
    field_value_id: str,
    payload: DecisionWrite,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> DecisionRead:
    """Guarda una decisión de revisión como evento append-only.

    Ninguna regla se evalúa en este endpoint: se construye la decisión y se
    delega en `review.record_decision`, que atraviesa `reviewer_identity` y
    `validation_states`. Un error de esas barreras se traduce a 400 con su
    mensaje en español, sin reinterpretarlo.
    """
    value = session.get(FieldValue, field_value_id)
    if value is None:
        raise ApplicationError("Campo no encontrado.", status_code=404)
    block = session.get(BlockInstance, value.block_instance_id)
    assert block is not None
    queued = session.scalar(
        select(ReviewQueueEntry).where(ReviewQueueEntry.target_record_id == block.target_record_id)
    )
    settings = cast(Settings, getattr(request.app.state, "settings", None) or get_settings())
    if queued is not None and settings.enable_review_queue:
        # El UPDATE mantiene el bloqueo hasta el commit de la decisión, evitando
        # que otra asignación se interponga entre comprobación y escritura.
        acquired = session.execute(
            update(ReviewQueueEntry)
            .where(
                ReviewQueueEntry.id == queued.id,
                ReviewQueueEntry.version == queued.version,
                ReviewQueueEntry.assignee_id == payload.reviewer_id,
                ReviewQueueEntry.state.in_(["asignado", "en_revision"]),
                ReviewQueueEntry.assigned_at > datetime.now(UTC) - DEFAULT_LEASE,
            )
            .values(
                version=ReviewQueueEntry.version + 1,
                assigned_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            .returning(ReviewQueueEntry.id)
            .execution_options(synchronize_session=False)
        ).scalar_one_or_none()
        if acquired is None:
            raise ApplicationError(
                "La asignación no está vigente para este revisor. Recargue la cola.",
                status_code=409,
            )
    # El rol es el que consta en la lista de revisores, no el que diga quien
    # llama: `resolve` falla si el identificador no pertenece a la lista.
    try:
        signer = directory.resolve(payload.reviewer_id)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error
    try:
        decision = ValidationDecision(
            field_name=value.field_name,
            state=payload.state,
            final_value=payload.final_value,
            reviewer_id=payload.reviewer_id,
            reviewer_role=signer.role,
            applicable_sources=tuple(payload.applicable_sources),
            required_sources=tuple(payload.required_sources),
            reviewed_sources=tuple(payload.reviewed_sources),
            field_required=payload.field_required,
            comment=payload.comment,
            seconds_spent=payload.seconds_spent,
        )
        record = record_decision_in_transaction(
            session,
            field_value_id=field_value_id,
            decision=decision,
            directory=directory,
        )
        if settings.enable_second_review:
            _open_required_second_reviews(
                session,
                target_record_id=block.target_record_id,
                actor_id=signer.identifier,
            )
        session.commit()
    except (ValidationStateError, ReviewerIdentityError, ValueError) as error:
        raise ApplicationError(str(error), status_code=400) from error
    return DecisionRead(
        sequence=record.sequence,
        state=record.state,
        final_value=record.final_value,
        comment=record.comment,
        reviewer_id=record.reviewer_id,
        reviewer_assurance=record.reviewer_assurance,
        decided_at=record.decided_at.isoformat(),
    )
