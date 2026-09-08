"""API de medición de tiempos de revisión (DEV-508/509).

Las reglas viven en `time_measurement` (puro) y la persistencia en
`timing_store`. Aquí sólo se expone el contrato HTTP que la pantalla necesita
para declarar dónde estuvo el foco.

Qué NO hace esta API, y por qué:

- No mide desde el servidor. El tiempo de trabajo ocurre en el navegador del
  revisor, y deducirlo de la separación entre peticiones contaría como trabajo
  una pestaña abierta y olvidada.
- No acepta tramos sobre una sesión cerrada. Una medición cerrada tiene sus
  agregados congelados; admitir tramos después los invalidaría en silencio.
- No permite que el cliente declare `is_synthetic`. Lo decide el servidor a
  partir de la configuración: si el cliente pudiera marcarlo, una medición de
  ingeniería podría colarse en una cifra presentada como ahorro real, o al
  revés.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import ReviewSession, TargetRecord
from pharma_validator_api.records import DirectoryDependency, SessionDependency
from pharma_validator_api.reviewer_identity import ReviewerDirectory
from pharma_validator_api.timing_store import (
    TimingStoreError,
    close_session,
    measure,
    record_focus,
    start_session,
)

router = APIRouter(prefix='/timing', tags=['tiempos'])


class SessionStartWrite(BaseModel):
    target_record_id: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)


class SessionRead(BaseModel):
    id: str
    target_record_id: str
    reviewer_id: str
    started_at: str
    ended_at: str | None
    is_synthetic: bool


class FocusWrite(BaseModel):
    """Un tramo de foco ya terminado, en segundos epoch del cliente.

    Se envían tramos cerrados y no «he entrado en el campo»: si el navegador se
    cierra a mitad, el tramo abierto simplemente no llega, en lugar de quedar
    contando indefinidamente.
    """

    field_name: str = Field(min_length=1)
    started_at: float
    ended_at: float


class MeasurementRead(BaseModel):
    review_session_id: str
    counted_seconds: float
    discarded_seconds: float
    fields: dict[str, float]


def _require_reviewer(directory: ReviewerDirectory, reviewer_id: str) -> None:
    if not any(item.identifier == reviewer_id for item in directory.reviewers):
        raise ApplicationError('Revisor no reconocido.', status_code=400)


@router.post('/sessions', response_model=SessionRead, status_code=201)
def open_session(
    payload: SessionStartWrite,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> SessionRead:
    _require_reviewer(directory, payload.reviewer_id)
    if session.get(TargetRecord, payload.target_record_id) is None:
        raise ApplicationError('Registro no encontrado.', status_code=404)
    try:
        row = start_session(
            session,
            target_record_id=payload.target_record_id,
            reviewer_id=payload.reviewer_id,
        )
    except TimingStoreError as error:
        raise ApplicationError(str(error), status_code=400) from error
    return _read(row)


@router.post('/sessions/{session_id}/focus', status_code=204)
def add_focus(
    session_id: str, payload: FocusWrite, session: SessionDependency
) -> None:
    try:
        record_focus(
            session,
            session_id,
            payload.field_name,
            payload.started_at,
            payload.ended_at,
        )
    except TimingStoreError as error:
        raise ApplicationError(str(error), status_code=400) from error
    except ValueError as error:
        # El intervalo puro rechaza un orden temporal imposible.
        raise ApplicationError(str(error), status_code=400) from error


@router.get('/sessions/{session_id}', response_model=MeasurementRead)
def read_measurement(session_id: str, session: SessionDependency) -> MeasurementRead:
    if session.get(ReviewSession, session_id) is None:
        raise ApplicationError('Sesión de medición no encontrada.', status_code=404)
    result = measure(session, session_id)
    return MeasurementRead(
        review_session_id=session_id,
        counted_seconds=result.counted_seconds,
        discarded_seconds=result.discarded_seconds,
        fields={item.field_name: item.counted_seconds for item in result.timings},
    )


@router.post('/sessions/{session_id}/close', response_model=MeasurementRead)
def end_session(session_id: str, session: SessionDependency) -> MeasurementRead:
    if session.get(ReviewSession, session_id) is None:
        raise ApplicationError('Sesión de medición no encontrada.', status_code=404)
    try:
        close_session(session, session_id)
    except TimingStoreError as error:
        raise ApplicationError(str(error), status_code=400) from error
    return read_measurement(session_id, session)


def _read(row: ReviewSession) -> SessionRead:
    return SessionRead(
        id=row.id,
        target_record_id=row.target_record_id,
        reviewer_id=row.reviewer_id,
        started_at=row.started_at.isoformat(),
        ended_at=row.ended_at.isoformat() if row.ended_at else None,
        is_synthetic=bool(row.is_synthetic),
    )
