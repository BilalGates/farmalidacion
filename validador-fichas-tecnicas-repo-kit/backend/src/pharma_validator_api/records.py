from collections.abc import Iterator, Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from pharma_validator_api.config import Settings, get_settings
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import (
    BlockInstance,
    ExternalIdentifier,
    FieldValue,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)
from pharma_validator_api.review import (
    current_decision,
    decision_history,
    effective_state,
    evaluate_field_conflict,
    record_decision,
)
from pharma_validator_api.reviewer_identity import ReviewerDirectory, ReviewerIdentityError
from pharma_validator_api.validation_states import (
    ValidationDecision,
    ValidationState,
    ValidationStateError,
)

router = APIRouter(prefix='/records', tags=['registros'])


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


class FieldValueRead(BaseModel):
    id: str
    field_name: str
    literal_value: str | None
    observed_type: str
    logical_state: str
    provenance: list[ProvenanceRead]
    validation_state: str
    #: Estado de conflicto según ADR-0007. Sin matriz de prioridad cargada, un
    #: conflicto real permanece sin resolver y exige acción humana.
    conflict_status: str
    has_conflict: bool
    history: list[DecisionRead]


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


class DecisionWrite(BaseModel):
    """Petición de decisión. Las reglas las aplica `validation_states`."""

    state: ValidationState
    reviewer_id: str
    reviewer_role: str = 'farmaceutico'
    final_value: str | None = None
    comment: str | None = None
    seconds_spent: int | None = None
    applicable_sources: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    reviewed_sources: list[str] = Field(default_factory=list)
    field_required: bool = False


def get_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    with factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


def get_reviewer_directory(request: Request) -> ReviewerDirectory:
    settings = cast(Settings, getattr(request.app.state, 'settings', None) or get_settings())
    return ReviewerDirectory.from_configuration(settings.reviewers)


DirectoryDependency = Annotated[ReviewerDirectory, Depends(get_reviewer_directory)]

#: Nombres de campo que identifican un registro en el listado. Provienen del
#: catálogo real; no se inventa semántica ni se deduce de otros campos.
DISPLAY_NAME_FIELDS = ('ME_DESCRIPCION', 'DESCRIPCION', 'NOMBRE')
ACTIVE_INGREDIENT_FIELDS = ('PA_DESCRIPCION', 'PRINCIPIO_ACTIVO')


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
            raise RuntimeError(f'Procedencia sin fragmento: {row.id}')
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


def _group_by_field(
    session: Session, values: Sequence[FieldValue]
) -> dict[tuple[str, str], tuple[FieldValue, ...]]:
    """Agrupa valores por ocurrencia de bloque y nombre de campo.

    Agrupar por nombre de campo a secas fusionaría ocurrencias distintas del
    mismo bloque repetible, que es exactamente lo que la regla de ocurrencias
    explícitas prohíbe.
    """
    grouped: dict[tuple[str, str], list[FieldValue]] = {}
    for value in values:
        grouped.setdefault((value.block_instance_id, value.field_name), []).append(value)
    return {key: tuple(items) for key, items in grouped.items()}


def _summarize(session: Session, record: TargetRecord) -> RecordSummaryRead:
    blocks = session.scalars(
        select(BlockInstance).where(BlockInstance.target_record_id == record.id)
    ).all()
    values = session.scalars(
        select(FieldValue)
        .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
        .where(BlockInstance.target_record_id == record.id)
        .order_by(FieldValue.id)
    ).all()
    pending = resolved = conflicts = 0
    last_reviewed = None
    for value in values:
        decision = current_decision(session, value.id)
        if decision is None or decision.state in ('pendiente', 'revision_pendiente'):
            pending += 1
        else:
            resolved += 1
        if decision is not None and (last_reviewed is None or decision.decided_at > last_reviewed):
            last_reviewed = decision.decided_at
    # La discrepancia se cuenta por campo dentro de la ocurrencia, no por fila:
    # dos fuentes que discrepan producen dos filas y el conflicto vive entre ellas.
    for (block_id, field_name), group in _group_by_field(session, values).items():
        block = session.get(BlockInstance, block_id)
        block_type = block.block_type if block is not None else 'desconocido'
        evaluation = evaluate_field_conflict(
            session, group, 1, record.entity_type, block_type, field_name
        )
        if evaluation.has_conflict:
            conflicts += 1
    identifier = session.scalars(
        select(ExternalIdentifier)
        .where(ExternalIdentifier.target_record_id == record.id)
        .order_by(ExternalIdentifier.source_system, ExternalIdentifier.source_identifier)
        .limit(1)
    ).first()
    if conflicts:
        review_state = 'requiere_revision'
    elif pending and resolved:
        review_state = 'en_revision'
    elif pending:
        review_state = 'pendiente'
    else:
        review_state = 'validado'
    return RecordSummaryRead(
        id=record.id,
        entity_type=record.entity_type,
        display_name=_first_value(session, record.id, DISPLAY_NAME_FIELDS),
        active_ingredient=_first_value(session, record.id, ACTIVE_INGREDIENT_FIELDS),
        primary_identifier=identifier.source_identifier if identifier else None,
        block_count=len(blocks),
        field_count=len(values),
        pending_count=pending,
        resolved_count=resolved,
        conflict_count=conflicts,
        review_state=review_state,
        last_reviewed_at=last_reviewed.isoformat() if last_reviewed else None,
    )


# Tamaño del tramo al filtrar por `estado`. Ni tan pequeño que multiplique las
# consultas, ni tan grande que resuma cientos de registros para descartarlos.
_ESTADO_SCAN_CHUNK = 100


def _search_predicate(needle: str) -> ColumnElement[bool]:
    """Preselección en SQL de los registros que `q` puede llegar a casar.

    Cubre los mismos orígenes que `_matches`: el identificador del registro, los
    identificadores externos y los campos de nombre y principio activo. `LIKE`
    en SQLite es insensible a mayúsculas para ASCII, igual que el `casefold` que
    aplica después `_matches`, que sigue siendo quien decide: esto sólo descarta
    lo que con certeza no coincide.
    """
    pattern = f'%{needle}%'
    named_fields = DISPLAY_NAME_FIELDS + ACTIVE_INGREDIENT_FIELDS
    return or_(
        TargetRecord.id.like(pattern),
        TargetRecord.id.in_(
            select(ExternalIdentifier.target_record_id).where(
                ExternalIdentifier.source_identifier.like(pattern)
            )
        ),
        TargetRecord.id.in_(
            select(BlockInstance.target_record_id)
            .join(FieldValue, FieldValue.block_instance_id == BlockInstance.id)
            .where(FieldValue.field_name.in_(named_fields))
            .where(FieldValue.literal_value.like(pattern))
        ),
    )


def _matches(item: RecordSummaryRead, needle: str) -> bool:
    """Coincidencia literal, sin normalizar acentos (misma regla que antes)."""
    folded = needle.casefold()
    return (
        folded in (item.display_name or '').casefold()
        or folded in (item.active_ingredient or '').casefold()
        or folded in (item.primary_identifier or '').casefold()
        or folded in item.id.casefold()
    )


@router.get('', response_model=RecordListRead)
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
        summaries = [_summarize(session, record) for record in records]
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
        for record in batch:
            summary = _summarize(session, record)
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


@router.get('/reviewers', response_model=list[ReviewerRead])
def list_reviewers(directory: DirectoryDependency) -> list[ReviewerRead]:
    """Lista configurable de revisores (10.1). Vacía si no se ha configurado."""
    return [
        ReviewerRead(
            identifier=item.identifier,
            display_name=item.display_name,
            assurance=item.assurance,
        )
        for item in directory.reviewers
    ]


@router.get('/{record_id}', response_model=TargetRecordRead)
def read_record(record_id: str, session: SessionDependency) -> TargetRecordRead:
    record = session.get(TargetRecord, record_id)
    if record is None:
        raise ApplicationError('Registro no encontrado.', status_code=404)
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
                        grouped[(value.block_instance_id, value.field_name)],
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
    return FieldValueRead(
        id=value.id,
        field_name=value.field_name,
        literal_value=value.literal_value,
        observed_type=value.observed_type,
        logical_state=value.logical_state,
        provenance=_provenance(session, value.id),
        validation_state=effective_state(session, value.id),
        conflict_status=evaluation.status,
        has_conflict=evaluation.has_conflict,
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


@router.post('/values/{field_value_id}/decisions', response_model=DecisionRead, status_code=201)
def save_decision(
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
        raise ApplicationError('Campo no encontrado.', status_code=404)
    if payload.reviewer_role not in ('farmaceutico', 'otro'):
        raise ApplicationError('Rol de revisor no reconocido.', status_code=400)
    try:
        decision = ValidationDecision(
            field_name=value.field_name,
            state=payload.state,
            final_value=payload.final_value,
            reviewer_id=payload.reviewer_id,
            reviewer_role=payload.reviewer_role,  # type: ignore[arg-type]
            applicable_sources=tuple(payload.applicable_sources),
            required_sources=tuple(payload.required_sources),
            reviewed_sources=tuple(payload.reviewed_sources),
            field_required=payload.field_required,
            comment=payload.comment,
            seconds_spent=payload.seconds_spent,
        )
        record = record_decision(
            session,
            field_value_id=field_value_id,
            decision=decision,
            directory=directory,
        )
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
