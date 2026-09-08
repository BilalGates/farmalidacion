"""Persistencia de la cola: asignación, orden y colisiones reales (DEV-502).

`test_review_queue` cubre las reglas puras. Aquí lo que se protege es que dos
sesiones concurrentes sobre la misma fila no puedan pisarse: esa garantía la da
la base de datos, no Python, y por eso se prueba contra SQLite real.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pharma_validator_api.models import Base, TargetRecord
from pharma_validator_api.review_queue import DEFAULT_LEASE, QueueConflictError
from pharma_validator_api.review_queue_store import (
    assign,
    claim_next,
    enqueue,
    list_queue,
    read,
    transition,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'queue.db').as_posix()}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    with maker() as session:
        for index in range(3):
            session.add(TargetRecord(id=f"rec-{index}", entity_type="medicamento"))
        session.commit()
    return maker


def test_enqueue_is_idempotent(factory: sessionmaker[Session]) -> None:
    """Reencolar no debe duplicar el trabajo ni perder su estado."""
    with factory() as session:
        first = enqueue(session, "rec-0", now=NOW)
        assign(session, "rec-0", "rev-a", now=NOW)
        again = enqueue(session, "rec-0", now=NOW)
    assert first.target_record_id == again.target_record_id
    assert again.state == "asignado"
    with factory() as session:
        assert len(list_queue(session)) == 1


def test_a_decision_survives_a_new_session(factory: sessionmaker[Session]) -> None:
    """La cola es estado persistido, no memoria de proceso."""
    with factory() as session:
        enqueue(session, "rec-0", now=NOW)
        assign(session, "rec-0", "rev-a", now=NOW)
    with factory() as session:
        item = read(session, "rec-0")
    assert item is not None
    assert (item.state, item.assignee_id) == ("asignado", "rev-a")


def test_two_sessions_cannot_both_take_the_same_work(factory: sessionmaker[Session]) -> None:
    """La colisión que motiva el bloqueo optimista, con dos sesiones abiertas."""
    with factory() as session:
        enqueue(session, "rec-0", now=NOW)

    first, second = factory(), factory()
    try:
        assign(first, "rec-0", "rev-a", now=NOW)
        with pytest.raises(QueueConflictError):
            assign(second, "rec-0", "rev-b", now=NOW)
    finally:
        first.close()
        second.close()

    with factory() as session:
        item = read(session, "rec-0")
    assert item is not None
    assert item.assignee_id == "rev-a"


def test_a_client_deciding_on_an_outdated_version_is_rejected(
    factory: sessionmaker[Session],
) -> None:
    """El caso de una pantalla abierta: se decidió sobre un estado ya superado.

    Releer no basta para detectarlo, porque la relectura ya trae lo nuevo. Quien
    llama declara la versión que vio, y ésa es la que debe comprobarse.
    """
    with factory() as session:
        enqueue(session, "rec-0", now=NOW)
        assign(session, "rec-0", "rev-a", now=NOW)
        seen = read(session, "rec-0")
        assert seen is not None
        # Otro revisor avanza el trabajo después de que la pantalla se pintara.
        transition(session, "rec-0", "en_revision", "rev-a", now=NOW)

        with pytest.raises(QueueConflictError):
            transition(
                session,
                "rec-0",
                "completado",
                "rev-a",
                now=NOW,
                expected_version=seen.version,
            )

        current = read(session, "rec-0")
    assert current is not None
    assert current.state == "en_revision"


def test_claim_next_follows_technical_order(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        enqueue(session, "rec-0", priority=0, now=NOW)
        enqueue(session, "rec-1", priority=9, now=NOW)
        enqueue(session, "rec-2", priority=0, now=NOW)
        claimed = claim_next(session, "rev-a", now=NOW)
    assert claimed is not None
    assert claimed.target_record_id == "rec-1"


def test_claim_next_skips_work_held_by_others(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        enqueue(session, "rec-0", priority=5, now=NOW)
        enqueue(session, "rec-1", priority=1, now=NOW)
        assign(session, "rec-0", "rev-a", now=NOW)
        claimed = claim_next(session, "rev-b", now=NOW)
    assert claimed is not None
    assert claimed.target_record_id == "rec-1"


def test_claim_next_recovers_abandoned_work(factory: sessionmaker[Session]) -> None:
    """Un revisor que cierra el navegador no retiene la ficha para siempre."""
    with factory() as session:
        enqueue(session, "rec-0", now=NOW)
        assign(session, "rec-0", "rev-a", now=NOW)
        later = NOW + DEFAULT_LEASE + timedelta(minutes=1)
        claimed = claim_next(session, "rev-b", now=later)
    assert claimed is not None
    assert (claimed.target_record_id, claimed.assignee_id) == ("rec-0", "rev-b")


def test_claim_next_returns_none_when_nothing_is_available(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        assert claim_next(session, "rev-a", now=NOW) is None


def test_filters_narrow_the_queue(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        enqueue(session, "rec-0", now=NOW)
        enqueue(session, "rec-1", now=NOW)
        assign(session, "rec-0", "rev-a", now=NOW)
        assert len(list_queue(session, state="pendiente")) == 1
        assert len(list_queue(session, assignee_id="rev-a")) == 1
