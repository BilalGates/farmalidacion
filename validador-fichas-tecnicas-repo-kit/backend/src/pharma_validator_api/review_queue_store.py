"""Persistencia de la cola de revisión (DEV-502).

Las reglas viven en `review_queue`; aquí sólo se leen y escriben filas. La
comprobación de versión se hace en la propia sentencia `UPDATE`, no en Python:
comprobar antes y escribir después deja una ventana en la que otro revisor
puede colarse, y esa ventana es exactamente la colisión que hay que evitar.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session

from pharma_validator_api.models import BlockInstance, ReviewQueueEntry, TargetRecord
from pharma_validator_api.review_queue import (
    DEFAULT_LEASE,
    QueueConflictError,
    QueueItem,
    QueueState,
    ReviewSet,
    assert_version_matches,
    plan_assignment,
    plan_transition,
    queue_order,
)


def _aware(moment: datetime | None) -> datetime | None:
    """SQLite devuelve `datetime` sin zona; compararlo con uno consciente falla.

    Se reinterpreta como UTC, que es como se escribió, en lugar de dejar que la
    caducidad de una asignación reviente al leerla de disco.
    """
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=UTC)


def _to_item(row: ReviewQueueEntry) -> QueueItem:
    return QueueItem(
        target_record_id=row.target_record_id,
        state=row.state,  # type: ignore[arg-type]
        version=row.version,
        assignee_id=row.assignee_id,
        assigned_at=_aware(row.assigned_at),
        priority=row.priority,
        created_at=_aware(row.created_at),
        review_set=row.review_set,  # type: ignore[arg-type]
        requires_second_review=row.requires_second_review,
    )


def enqueue(session: Session, target_record_id: str, *, priority: int = 0,
            review_set: ReviewSet = "corpus", requires_second_review: bool = False,
            now: datetime | None = None) -> QueueItem:
    """Encola un registro. Reencolar uno ya presente no lo duplica ni lo reinicia."""
    moment = now or datetime.now(UTC)
    existing = session.scalar(
        select(ReviewQueueEntry).where(ReviewQueueEntry.target_record_id == target_record_id)
    )
    if existing is not None:
        return _to_item(existing)
    row = ReviewQueueEntry(
        target_record_id=target_record_id,
        state="pendiente",
        version=1,
        priority=priority,
        review_set=review_set,
        requires_second_review=requires_second_review,
        created_at=moment,
        updated_at=moment,
    )
    session.add(row)
    session.commit()
    return _to_item(row)


def read(session: Session, target_record_id: str) -> QueueItem | None:
    row = session.scalar(
        select(ReviewQueueEntry).where(ReviewQueueEntry.target_record_id == target_record_id)
    )
    return None if row is None else _to_item(row)


def list_queue(session: Session, *, state: QueueState | None = None,
               assignee_id: str | None = None, entity_type: str | None = None,
               block_type: str | None = None, review_set: ReviewSet | None = None,
               requires_second_review: bool | None = None) -> tuple[QueueItem, ...]:
    statement = select(ReviewQueueEntry)
    if state is not None:
        statement = statement.where(ReviewQueueEntry.state == state)
    if assignee_id is not None:
        statement = statement.where(ReviewQueueEntry.assignee_id == assignee_id)
    if entity_type is not None:
        statement = statement.join(TargetRecord).where(TargetRecord.entity_type == entity_type)
    if block_type is not None:
        statement = statement.join(
            BlockInstance, BlockInstance.target_record_id == ReviewQueueEntry.target_record_id
        ).where(BlockInstance.block_type == block_type)
    if review_set is not None:
        statement = statement.where(ReviewQueueEntry.review_set == review_set)
    if requires_second_review is not None:
        statement = statement.where(
            ReviewQueueEntry.requires_second_review == requires_second_review
        )
    statement = statement.distinct()
    return queue_order(tuple(_to_item(r) for r in session.scalars(statement).all()))


def _persist(
    session: Session, planned: QueueItem, expected_version: int, *, commit: bool = True
) -> QueueItem:
    """Escribe sólo si la fila sigue en la versión leída.

    `rowcount == 0` significa que alguien escribió entre la lectura y esta
    sentencia: se informa como conflicto en lugar de pisar su trabajo.
    """
    result: CursorResult[object] = session.execute(  # type: ignore[assignment]
        update(ReviewQueueEntry)
        .where(
            ReviewQueueEntry.target_record_id == planned.target_record_id,
            ReviewQueueEntry.version == expected_version,
        )
        .values(
            state=planned.state,
            version=planned.version,
            assignee_id=planned.assignee_id,
            assigned_at=planned.assigned_at,
            priority=planned.priority,
            review_set=planned.review_set,
            requires_second_review=planned.requires_second_review,
            updated_at=datetime.now(UTC),
        )
    )
    if result.rowcount == 0:
        session.rollback()
        raise QueueConflictError(
            "Otro revisor modificó este trabajo mientras se editaba. Recargue antes de decidir."
        )
    if commit:
        session.commit()
    return planned


def _require(session: Session, target_record_id: str) -> QueueItem:
    item = read(session, target_record_id)
    if item is None:
        raise QueueConflictError(f"El registro {target_record_id} no está en la cola.")
    return item


def assign(session: Session, target_record_id: str, reviewer_id: str, *,
           now: datetime | None = None, lease: timedelta = DEFAULT_LEASE) -> QueueItem:
    moment = now or datetime.now(UTC)
    item = _require(session, target_record_id)
    return _persist(session, plan_assignment(item, reviewer_id, moment, lease), item.version)


def transition(session: Session, target_record_id: str, target: QueueState,
               reviewer_id: str, *, now: datetime | None = None,
               lease: timedelta = DEFAULT_LEASE,
               expected_version: int | None = None) -> QueueItem:
    """Avanza un trabajo.

    `expected_version` es la versión sobre la que decidió quien llama. Sin ella
    se usa la fila actual, que basta para una única sesión; una interfaz web
    debe pasarla, porque entre que pintó la pantalla y llegó la acción del
    revisor otro puede haber escrito.
    """
    moment = now or datetime.now(UTC)
    item = _require(session, target_record_id)
    if expected_version is not None:
        assert_version_matches(item, expected_version)
    planned = plan_transition(item, target, reviewer_id, moment, lease)
    return _persist(session, planned, item.version)


def assign_batch(
    session: Session,
    assignments: tuple[tuple[str, int], ...],
    reviewer_id: str,
    *,
    now: datetime | None = None,
    lease: timedelta = DEFAULT_LEASE,
) -> tuple[QueueItem, ...]:
    """Asigna un lote completo o ninguno, conservando el bloqueo optimista."""
    if not assignments:
        raise QueueConflictError("El lote de asignación no puede estar vacío.")
    moment = now or datetime.now(UTC)
    planned: list[QueueItem] = []
    try:
        for target_record_id, expected_version in assignments:
            item = _require(session, target_record_id)
            assert_version_matches(item, expected_version)
            candidate = plan_assignment(item, reviewer_id, moment, lease)
            planned.append(_persist(session, candidate, item.version, commit=False))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return tuple(planned)


def claim_next(session: Session, reviewer_id: str, *, now: datetime | None = None,
               lease: timedelta = DEFAULT_LEASE) -> QueueItem | None:
    """Toma el siguiente trabajo disponible en orden técnico.

    Si otro revisor gana la carrera por un trabajo, se intenta el siguiente en
    lugar de fallar: la cola debe seguir avanzando bajo concurrencia.
    """
    moment = now or datetime.now(UTC)
    for item in list_queue(session):
        if item.state == "pendiente" or (
            item.state in ("asignado", "en_revision") and item.lease_expired(moment, lease)
        ):
            try:
                return assign(session, item.target_record_id, reviewer_id, now=moment, lease=lease)
            except QueueConflictError:
                continue
    return None
