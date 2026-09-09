"""API de la cola de revisión (DEV-502).

Un conflicto de concurrencia se devuelve como 409, no como 500: que otro
revisor llegara antes es un resultado previsible del flujo, y la interfaz debe
poder ofrecer recargar en lugar de presentar un fallo del sistema.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from pharma_validator_api.config import Settings, get_settings
from pharma_validator_api.maturity import CAPABILITIES, clinical_blockers
from pharma_validator_api.models import TargetRecord
from pharma_validator_api.records import SessionDependency
from pharma_validator_api.review_queue import (
    QueueConflictError,
    QueueItem,
    QueueState,
    ReviewQueueError,
    ReviewSet,
)
from pharma_validator_api.review_queue_store import (
    assign,
    assign_batch,
    claim_next,
    enqueue,
    list_queue,
    read,
    transition,
)

router = APIRouter(prefix='/queue', tags=['cola'])


class QueueItemRead(BaseModel):
    target_record_id: str
    state: str
    version: int
    assignee_id: str | None = None
    priority: int = 0
    review_set: ReviewSet
    requires_second_review: bool


class AssignRequest(BaseModel):
    reviewer_id: str = Field(min_length=1)


class TransitionRequest(BaseModel):
    reviewer_id: str = Field(min_length=1)
    state: QueueState
    # La versión que vio quien decide. Sin ella no puede detectarse que la
    # pantalla estaba desactualizada al pulsar.
    expected_version: int | None = None


class EnqueueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_record_id: str = Field(min_length=1)
    priority: int = 0
    review_set: ReviewSet = "corpus"
    requires_second_review: bool = False


class BatchAssignmentItem(BaseModel):
    target_record_id: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class BatchAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer_id: str = Field(min_length=1)
    items: list[BatchAssignmentItem] = Field(min_length=1, max_length=100)


def _read(item: QueueItem) -> QueueItemRead:
    return QueueItemRead(
        target_record_id=item.target_record_id,
        state=item.state,
        version=item.version,
        assignee_id=item.assignee_id,
        priority=item.priority,
        review_set=item.review_set,
        requires_second_review=item.requires_second_review,
    )


def get_active_settings(request: Request) -> Settings:
    return cast(Settings, getattr(request.app.state, 'settings', None) or get_settings())


SettingsDependency = Annotated[Settings, Depends(get_active_settings)]


def _require_enabled(settings: Settings) -> None:
    if not settings.enable_review_queue:
        raise HTTPException(status_code=404, detail='La cola de revisión está desactivada.')


def _guard(error: ReviewQueueError) -> HTTPException:
    status = 409 if isinstance(error, QueueConflictError) else 400
    return HTTPException(status_code=status, detail=str(error))


@router.get('', response_model=list[QueueItemRead])
def get_queue(
    session: SessionDependency,
    settings: SettingsDependency,
    state: QueueState | None = None,
    assignee_id: Annotated[str | None, Query()] = None,
    entity_type: Annotated[str | None, Query()] = None,
    block_type: Annotated[str | None, Query()] = None,
    review_set: Annotated[ReviewSet | None, Query()] = None,
    requires_second_review: Annotated[bool | None, Query()] = None,
) -> list[QueueItemRead]:
    _require_enabled(settings)
    return [
        _read(i)
        for i in list_queue(
            session,
            state=state,
            assignee_id=assignee_id,
            entity_type=entity_type,
            block_type=block_type,
            review_set=review_set,
            requires_second_review=requires_second_review,
        )
    ]


@router.post('', response_model=QueueItemRead, status_code=201)
def post_enqueue(
    payload: EnqueueRequest, session: SessionDependency, settings: SettingsDependency
) -> QueueItemRead:
    _require_enabled(settings)
    if session.get(TargetRecord, payload.target_record_id) is None:
        raise HTTPException(status_code=404, detail='Registro no encontrado.')
    return _read(
        enqueue(
            session,
            payload.target_record_id,
            priority=payload.priority,
            review_set=payload.review_set,
            requires_second_review=payload.requires_second_review,
        )
    )


@router.post('/assign-batch', response_model=list[QueueItemRead])
def post_assign_batch(
    payload: BatchAssignRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> list[QueueItemRead]:
    _require_enabled(settings)
    identifiers = [item.target_record_id for item in payload.items]
    if len(identifiers) != len(set(identifiers)):
        raise HTTPException(status_code=400, detail="Un lote no puede repetir registros.")
    try:
        assigned = assign_batch(
            session,
            tuple((item.target_record_id, item.expected_version) for item in payload.items),
            payload.reviewer_id,
        )
    except ReviewQueueError as error:
        raise _guard(error) from error
    return [_read(item) for item in assigned]


@router.post('/next', response_model=QueueItemRead | None)
def post_claim_next(
    payload: AssignRequest, session: SessionDependency, settings: SettingsDependency
) -> QueueItemRead | None:
    _require_enabled(settings)
    claimed = claim_next(session, payload.reviewer_id)
    return None if claimed is None else _read(claimed)


@router.get('/{target_record_id}', response_model=QueueItemRead)
def get_item(
    target_record_id: str, session: SessionDependency, settings: SettingsDependency
) -> QueueItemRead:
    _require_enabled(settings)
    item = read(session, target_record_id)
    if item is None:
        raise HTTPException(status_code=404, detail='El registro no está en la cola.')
    return _read(item)


@router.post('/{target_record_id}/assign', response_model=QueueItemRead)
def post_assign(
    target_record_id: str,
    payload: AssignRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> QueueItemRead:
    _require_enabled(settings)
    try:
        return _read(assign(session, target_record_id, payload.reviewer_id))
    except ReviewQueueError as error:
        raise _guard(error) from error


@router.post('/{target_record_id}/transition', response_model=QueueItemRead)
def post_transition(
    target_record_id: str,
    payload: TransitionRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> QueueItemRead:
    _require_enabled(settings)
    try:
        return _read(
            transition(
                session,
                target_record_id,
                payload.state,
                payload.reviewer_id,
                expected_version=payload.expected_version,
            )
        )
    except ReviewQueueError as error:
        raise _guard(error) from error


class CapabilityRead(BaseModel):
    name: str
    level: str
    clinical_blockers: list[str]
    note: str


class MaturityRead(BaseModel):
    """Lo que el despliegue afirma de sí mismo, sin adornos."""

    clinically_validated: bool
    clinical_blockers: list[str]
    capabilities: list[CapabilityRead]
    flags: dict[str, bool]


maturity_router = APIRouter(prefix='/maturity', tags=['sistema'])


@maturity_router.get('', response_model=MaturityRead)
def get_maturity(settings: SettingsDependency) -> MaturityRead:
    return MaturityRead(
        clinically_validated=settings.clinically_validated,
        clinical_blockers=list(clinical_blockers()),
        capabilities=[
            CapabilityRead(
                name=c.name,
                level=c.level,
                clinical_blockers=list(c.clinical_blockers),
                note=c.note,
            )
            for c in CAPABILITIES
        ],
        flags={
            'enable_llm_prefill': settings.enable_llm_prefill,
            'enable_second_review': settings.enable_second_review,
            'enable_export': settings.enable_export,
            'enable_cima_link': settings.enable_cima_link,
            'enable_auto_revalidation': settings.enable_auto_revalidation,
            'enable_review_queue': settings.enable_review_queue,
        },
    )
