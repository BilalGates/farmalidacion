"""API de las acciones de novedades CIMA (ADR-0019, D-040).

Lectura de la bandeja «Por atender», el histórico y los avisos sin registro en
el catálogo; decisiones del farmacéutico y envío en lote a la cola de Revisión.
Toda consulta de acciones filtra por un único origen (REAL o DEMO).
"""

from __future__ import annotations

import json
import logging
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, FastAPI, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from pharma_validator_api.cima_client import CimaClient
from pharma_validator_api.config import Settings
from pharma_validator_api.data_origin import DataOrigin
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.maintenance_action_decisions import (
    ActionConflict,
    ActionError,
    ActionNotFound,
    decide,
    send_to_review,
)
from pharma_validator_api.maintenance_actions import (
    KINDS,
    backfill_actions,
    current_state,
    live_actions,
    pending_condition,
)
from pharma_validator_api.maintenance_lock import MaintenanceAlreadyRunning, maintenance_lock
from pharma_validator_api.models import (
    MaintenanceAction,
    MaintenanceActionDecision,
    MaintenanceChangeEvent,
    MaintenanceChangeEventTarget,
    MedicationCatalogIdentity,
    SourceDocumentArtifact,
    SourceDocumentVersion,
)
from pharma_validator_api.records import DirectoryDependency, SessionDependency
from pharma_validator_api.reviewer_identity import Reviewer, ReviewerIdentityError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["mantenimiento"])
catalog_router = APIRouter(prefix="/catalog", tags=["catálogo"])

ActionKind = Literal[
    "proponer_activo_n",
    "revisar_estado",
    "revisar_comercializacion",
    "revisar_archivo",
    "proponer_alta",
]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


class DecisionRead(BaseModel):
    sequence: int
    decision: str
    reason: str
    actor_id: str
    actor_assurance: str
    recorded_at: str
    applied_revision_id: str | None = None
    applied_field_revision_id: str | None = None


class ActionRead(BaseModel):
    id: str
    event_id: str
    kind: str
    area: str
    data_origin: str
    state: str
    sequence: int
    nregistro: str
    event_occurred_at_epoch: int
    event_change_type: int
    target_record_id: str | None
    identity_id: str | None
    identity_name: str | None
    national_code: str | None
    master_field_name: str | None
    master_value_literal: str | None
    cima_version_id: str | None
    cima_pointer: str | None
    cima_value_literal: str | None
    cima_fetched_at: str | None
    cima_source_url: str | None
    proposed_value: str | None
    rule_id: str | None
    proposal: dict[str, Any] | None
    diagnostic_code: str | None
    derivation_version: str
    last_decision: DecisionRead | None
    decisions: list[DecisionRead] | None = None


class ActionPage(BaseModel):
    items: list[ActionRead]
    total: int
    limit: int
    offset: int
    origin: str
    counts: dict[str, int]


class UnlinkedEventRead(BaseModel):
    id: str
    nregistro: str
    occurred_at_epoch: int
    change_type: int
    areas: list[str]
    recorded_at: str
    diagnostic_code: str


class UnlinkedPage(BaseModel):
    items: list[UnlinkedEventRead]
    page: int
    page_size: int
    total: int


class DecisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str = Field(min_length=1, max_length=80)
    decision: Literal["aceptada", "descartada", "reabierta"]
    reason: str = ""
    expected_sequence: int = Field(ge=0)


class SendToReviewWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str = Field(min_length=1, max_length=80)
    action_ids: list[str] = Field(min_length=1, max_length=200)


class SendToReviewRead(BaseModel):
    enqueued: list[str]
    already_queued: list[str]
    decided: list[str]
    rejected: list[dict[str, str]]


class BackfillWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int | None = Field(default=None, ge=1)


class BackfillStarted(BaseModel):
    status: str
    origin: str


def _origin(request: Request, origin: DataOrigin | None) -> DataOrigin:
    """Un único origen por consulta: el pedido o, si no, el del despliegue."""
    return origin or DataOrigin(request.app.state.settings.data_mode)


def _decision_read(row: MaintenanceActionDecision) -> DecisionRead:
    return DecisionRead(
        sequence=row.sequence,
        decision=row.decision,
        reason=row.reason,
        actor_id=row.actor_id,
        actor_assurance=row.actor_assurance,
        recorded_at=row.recorded_at.isoformat(),
        applied_revision_id=row.applied_revision_id,
        applied_field_revision_id=row.applied_field_revision_id,
    )


def _serialize(
    session: Session, rows: list[Any], *, with_decisions: bool = False
) -> list[ActionRead]:
    """`rows`: tuplas (acción, evento, nombre de la identidad)."""
    states = current_state(session, [row[0].id for row in rows])
    version_ids = {row[0].cima_version_id for row in rows if row[0].cima_version_id}
    sources: dict[str, tuple[str | None, str | None]] = {}
    if version_ids:
        for version_id, acquired_at, source_url in session.execute(
            select(
                SourceDocumentVersion.id,
                SourceDocumentVersion.acquired_at,
                SourceDocumentArtifact.source_url,
            )
            .join(
                SourceDocumentArtifact,
                SourceDocumentArtifact.document_version_id == SourceDocumentVersion.id,
            )
            .where(SourceDocumentVersion.id.in_(version_ids))
        ):
            sources[version_id] = (acquired_at.isoformat(), source_url)
    items = []
    for action, event, identity_name in rows:
        state = states[action.id]
        fetched_at, url = sources.get(action.cima_version_id or "", (None, None))
        decisions = None
        if with_decisions:
            decisions = [
                _decision_read(item)
                for item in session.scalars(
                    select(MaintenanceActionDecision)
                    .where(MaintenanceActionDecision.action_id == action.id)
                    .order_by(MaintenanceActionDecision.sequence)
                )
            ]
        items.append(
            ActionRead(
                id=action.id,
                event_id=action.event_id,
                kind=action.kind,
                area=action.area,
                data_origin=action.data_origin,
                state=state.state,
                sequence=state.sequence,
                nregistro=event.nregistro,
                event_occurred_at_epoch=event.occurred_at_epoch,
                event_change_type=event.change_type,
                target_record_id=action.target_record_id,
                identity_id=action.identity_id,
                identity_name=identity_name,
                national_code=action.national_code,
                master_field_name=action.master_field_name,
                master_value_literal=action.master_value_literal,
                cima_version_id=action.cima_version_id,
                cima_pointer=action.cima_pointer,
                cima_value_literal=action.cima_value_literal,
                cima_fetched_at=fetched_at,
                cima_source_url=url,
                proposed_value=action.proposed_value,
                rule_id=action.rule_id,
                proposal=json.loads(action.proposal_json) if action.proposal_json else None,
                diagnostic_code=action.diagnostic_code,
                derivation_version=action.derivation_version,
                last_decision=_decision_read(state.decision) if state.decision else None,
                decisions=decisions,
            )
        )
    return items


def _base_query(origin: DataOrigin) -> Any:
    return (
        select(MaintenanceAction, MaintenanceChangeEvent, MedicationCatalogIdentity.display_name)
        .join(MaintenanceChangeEvent, MaintenanceChangeEvent.id == MaintenanceAction.event_id)
        .outerjoin(
            MedicationCatalogIdentity,
            MedicationCatalogIdentity.id == MaintenanceAction.identity_id,
        )
        .where(MaintenanceAction.data_origin == origin.value, live_actions())
    )


def _page(
    session: Session, origin: DataOrigin, *, pending: bool, kind: str | None,
    limit: int, offset: int,
) -> ActionPage:
    if kind is not None and kind not in KINDS:
        raise ApplicationError("Tipo de acción desconocido.", status_code=400)
    condition = pending_condition() if pending else ~pending_condition()
    base = _base_query(origin).where(condition)
    counts = dict(
        session.execute(
            select(MaintenanceAction.kind, func.count())
            .where(
                MaintenanceAction.data_origin == origin.value, live_actions(), condition
            )
            .group_by(MaintenanceAction.kind)
        ).all()
    )
    filtered = base.where(MaintenanceAction.kind == kind) if kind else base
    total = sum(counts.values()) if kind is None else counts.get(kind, 0)
    rows = session.execute(
        filtered.order_by(
            MaintenanceAction.kind,
            MaintenanceChangeEvent.occurred_at_epoch.desc(),
            MaintenanceAction.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return ActionPage(
        items=_serialize(session, list(rows)),
        total=total,
        limit=limit,
        offset=offset,
        origin=origin.value,
        counts={name: int(value) for name, value in counts.items()},
    )


@router.get("/actions", response_model=ActionPage)
def pending_actions(
    request: Request,
    session: SessionDependency,
    kind: ActionKind | None = None,
    origin: DataOrigin | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> ActionPage:
    """Bandeja «Por atender»: sin decisión o reabiertas, con contadores por tipo."""
    return _page(
        session, _origin(request, origin), pending=True, kind=kind, limit=limit, offset=offset
    )


@router.get("/actions/history", response_model=ActionPage)
def decided_actions(
    request: Request,
    session: SessionDependency,
    kind: ActionKind | None = None,
    origin: DataOrigin | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> ActionPage:
    return _page(
        session, _origin(request, origin), pending=False, kind=kind, limit=limit, offset=offset
    )


@router.get("/actions/unlinked", response_model=UnlinkedPage)
def unlinked_events(
    session: SessionDependency, page: int = 1, limit: int = 50
) -> UnlinkedPage:
    """Avisos sin registro en el catálogo (D-040): se guardan todos, fuera de las cifras."""
    if not 1 <= page <= 10_000 or not 1 <= limit <= 100:
        raise ApplicationError("Página o tamaño de página inválidos.", status_code=400)
    linked = select(MaintenanceChangeEventTarget.event_id)
    condition = MaintenanceChangeEvent.id.not_in(linked)
    total = session.scalar(
        select(func.count()).select_from(MaintenanceChangeEvent).where(condition)
    ) or 0
    rows = session.scalars(
        select(MaintenanceChangeEvent)
        .where(condition)
        .order_by(MaintenanceChangeEvent.occurred_at_epoch.desc(), MaintenanceChangeEvent.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return UnlinkedPage(
        items=[
            UnlinkedEventRead(
                id=row.id,
                nregistro=row.nregistro,
                occurred_at_epoch=row.occurred_at_epoch,
                change_type=row.change_type,
                areas=json.loads(row.areas_json),
                recorded_at=row.recorded_at.isoformat(),
                diagnostic_code="sin_registro_en_catalogo",
            )
            for row in rows
        ],
        page=page,
        page_size=limit,
        total=total,
    )


def _require_deployment_origin(request: Request, session: Session, action_id: str) -> None:
    """REAL y DEMO no se mezclan: una acción de otro origen no existe para este despliegue."""
    origin = session.scalar(
        select(MaintenanceAction.data_origin).where(MaintenanceAction.id == action_id)
    )
    if origin is not None and origin != request.app.state.settings.data_mode:
        raise ApplicationError("Acción de novedad no encontrada.", status_code=404)


@router.get("/actions/{action_id}", response_model=ActionRead)
def action_detail(action_id: str, request: Request, session: SessionDependency) -> ActionRead:
    _require_deployment_origin(request, session, action_id)
    row = session.execute(
        select(MaintenanceAction, MaintenanceChangeEvent, MedicationCatalogIdentity.display_name)
        .join(MaintenanceChangeEvent, MaintenanceChangeEvent.id == MaintenanceAction.event_id)
        .outerjoin(
            MedicationCatalogIdentity,
            MedicationCatalogIdentity.id == MaintenanceAction.identity_id,
        )
        .where(MaintenanceAction.id == action_id)
    ).first()
    if row is None:
        raise ApplicationError("Acción de novedad no encontrada.", status_code=404)
    return _serialize(session, [tuple(row)], with_decisions=True)[0]


def _reviewer(directory: Any, actor_id: str) -> Reviewer:
    try:
        return directory.resolve(actor_id)  # type: ignore[no-any-return]
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error


def _status(error: ActionError) -> int:
    if isinstance(error, ActionNotFound):
        return 404
    return 409 if isinstance(error, ActionConflict) else 400


@router.post("/actions/send-to-review", response_model=SendToReviewRead)
def send_actions_to_review(
    payload: SendToReviewWrite, session: SessionDependency, directory: DirectoryDependency
) -> SendToReviewRead:
    reviewer = _reviewer(directory, payload.actor_id)
    result = send_to_review(session, action_ids=payload.action_ids, reviewer=reviewer)
    return SendToReviewRead(
        enqueued=result.enqueued,
        already_queued=result.already_queued,
        decided=result.decided,
        rejected=result.rejected,
    )


@router.post("/actions/{action_id}/decisions", response_model=DecisionRead, status_code=201)
def decide_action(
    action_id: str,
    payload: DecisionWrite,
    request: Request,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> DecisionRead:
    _require_deployment_origin(request, session, action_id)
    reviewer = _reviewer(directory, payload.actor_id)
    try:
        row = decide(
            session,
            action_id=action_id,
            decision=payload.decision,
            reason=payload.reason,
            expected_sequence=payload.expected_sequence,
            reviewer=reviewer,
        )
    except ActionError as error:
        raise ApplicationError(str(error), status_code=_status(error)) from error
    return _decision_read(row)


def build_cima_client(settings: Settings) -> CimaClient:
    return CimaClient(
        base_url=settings.cima_base_url,
        cache_dir=settings.cima_cache_dir,
        timeout_seconds=settings.cima_timeout_seconds,
        requests_per_second=settings.cima_requests_per_second,
        max_retries=settings.cima_max_retries,
        backoff_seconds=settings.cima_backoff_seconds,
        max_retry_delay_seconds=settings.cima_max_retry_delay_seconds,
    )


def maintenance_lock_for(settings: Settings) -> AbstractContextManager[None]:
    url = make_url(settings.database_url)
    path = url.database
    if url.get_backend_name() == "sqlite" and path not in (None, ":memory:"):
        return maintenance_lock(Path(str(path)))
    return nullcontext()


def _run_backfill(application: FastAPI, origin: DataOrigin, limit: int | None) -> None:
    settings: Settings = application.state.settings
    try:
        with (
            maintenance_lock_for(settings),
            build_cima_client(settings) as client,
            application.state.session_factory() as session,
        ):
            backfill_actions(session, client=client, origin=origin, limit=limit)
    except MaintenanceAlreadyRunning:
        logger.warning("Backfill de acciones omitido: ya hay una pasada CIMA activa.")
    except Exception:
        logger.exception("Backfill de acciones fallido; relanzarlo continúa donde se quedó.")


@router.post("/actions/backfill", response_model=BackfillStarted, status_code=202)
def start_backfill(
    request: Request, background: BackgroundTasks, payload: BackfillWrite | None = None
) -> BackfillStarted:
    """Deriva acciones de los avisos ya guardados. Reanudable; no repite filas."""
    settings: Settings = request.app.state.settings
    try:
        with maintenance_lock_for(settings):
            pass  # comprobación inmediata; la pasada real retoma el bloqueo
    except MaintenanceAlreadyRunning as error:
        raise ApplicationError(str(error), status_code=409) from error
    origin = DataOrigin(settings.data_mode)
    background.add_task(_run_backfill, request.app, origin, payload.limit if payload else None)
    return BackfillStarted(status="iniciado", origin=origin.value)


@catalog_router.get(
    "/identities/{identity_id}/maintenance-actions", response_model=list[ActionRead]
)
def identity_actions(
    identity_id: str,
    request: Request,
    session: SessionDependency,
    state: Literal["pendiente", "todas"] = "pendiente",
    origin: DataOrigin | None = None,
) -> list[ActionRead]:
    identity = session.get(MedicationCatalogIdentity, identity_id)
    if identity is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    belongs = [MaintenanceAction.identity_id == identity_id]
    if identity.target_record_id:
        belongs.append(MaintenanceAction.target_record_id == identity.target_record_id)
    query = _base_query(_origin(request, origin)).where(or_(*belongs))
    if state == "pendiente":
        query = query.where(pending_condition())
    rows = session.execute(
        query.order_by(MaintenanceChangeEvent.occurred_at_epoch.desc(), MaintenanceAction.id)
    ).all()
    return _serialize(session, list(rows))
