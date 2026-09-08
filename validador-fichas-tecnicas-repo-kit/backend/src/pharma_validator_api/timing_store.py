"""Persistencia de la medición de tiempos de revisión (DEV-508/DEV-509).

El cálculo vive en `time_measurement` y aquí no se repite: la interfaz envía
tramos de foco observados y este módulo los guarda y agrega llamando al módulo
puro. Si el umbral de inactividad cambiara, se recalcula desde los intervalos
crudos, que por eso se conservan.

Propósito declarado: medir el ahorro de tiempo del sistema. No es un
instrumento de evaluación de personas, y las consultas que expone agregan por
ficha y campo, no comparan revisores entre sí.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.models import FieldFocusInterval, ReviewSession
from pharma_validator_api.time_measurement import (
    FocusInterval,
    SessionMeasurement,
    measure_session,
)


class TimingStoreError(RuntimeError):
    """Medición incoherente con lo ya registrado."""


def start_session(session: Session, *, target_record_id: str, reviewer_id: str,
                  started_at: datetime | None = None,
                  is_synthetic: bool = False) -> ReviewSession:
    """Abre una sesión de medición.

    `is_synthetic` marca de origen las sesiones de piloto técnico o pruebas, de
    modo que jamás puedan sumarse a una cifra presentada como ahorro real.
    """
    if not reviewer_id:
        raise TimingStoreError("Una sesión de medición exige revisor identificado.")
    row = ReviewSession(
        target_record_id=target_record_id,
        reviewer_id=reviewer_id,
        started_at=started_at or datetime.now(UTC),
        is_synthetic=is_synthetic,
    )
    session.add(row)
    session.commit()
    return row


def record_focus(session: Session, review_session_id: str, field_name: str,
                 started_at: float, ended_at: float) -> FieldFocusInterval:
    """Guarda un tramo de foco. Se valida antes de tocar la base."""
    # Construir el intervalo puro valida el orden temporal sin duplicar la regla.
    FocusInterval(started_at=started_at, ended_at=ended_at)
    if not field_name:
        raise TimingStoreError("Un tramo de foco exige campo.")
    if session.get(ReviewSession, review_session_id) is None:
        raise TimingStoreError(f"La sesión {review_session_id} no existe.")
    row = FieldFocusInterval(
        review_session_id=review_session_id,
        field_name=field_name,
        started_at=started_at,
        ended_at=ended_at,
    )
    session.add(row)
    session.commit()
    return row


def _observations(
    session: Session, review_session_id: str
) -> tuple[tuple[str, tuple[FocusInterval, ...]], ...]:
    rows = session.scalars(
        select(FieldFocusInterval).where(
            FieldFocusInterval.review_session_id == review_session_id
        )
    ).all()
    grouped: dict[str, list[FocusInterval]] = {}
    for row in rows:
        grouped.setdefault(row.field_name, []).append(
            FocusInterval(started_at=row.started_at, ended_at=row.ended_at)
        )
    return tuple((name, tuple(intervals)) for name, intervals in grouped.items())


def measure(session: Session, review_session_id: str) -> SessionMeasurement:
    """Agrega la sesión aplicando el descuento de inactividad del módulo puro."""
    return measure_session(_observations(session, review_session_id))


def close_session(session: Session, review_session_id: str,
                  ended_at: datetime | None = None) -> ReviewSession:
    """Cierra la sesión y congela sus agregados.

    Los agregados se guardan calculados, no acumulados a mano por la interfaz:
    el descuento de inactividad debe aplicarse en un único sitio.
    """
    row = session.get(ReviewSession, review_session_id)
    if row is None:
        raise TimingStoreError(f"La sesión {review_session_id} no existe.")
    measurement = measure(session, review_session_id)
    row.ended_at = ended_at or datetime.now(UTC)
    row.counted_seconds = measurement.counted_seconds
    row.discarded_seconds = measurement.discarded_seconds
    row.measured_field_count = measurement.measured_field_count
    row.capped_field_count = measurement.capped_field_count
    session.commit()
    return row


def seconds_per_field(session: Session, *, include_synthetic: bool = False) -> float | None:
    """Métrica rectora de 10.2 sobre sesiones cerradas.

    Las sesiones sintéticas quedan fuera por defecto: mezclarlas con revisión
    real produciría una cifra que parece un resultado y no lo es.
    """
    statement = select(ReviewSession).where(ReviewSession.ended_at.is_not(None))
    if not include_synthetic:
        statement = statement.where(ReviewSession.is_synthetic.is_(False))
    rows = session.scalars(statement).all()
    fields = sum(r.measured_field_count for r in rows)
    if not fields:
        return None
    return sum(r.counted_seconds for r in rows) / fields
