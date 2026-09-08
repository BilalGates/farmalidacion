"""Persistencia de la medicion de tiempos (DEV-508/DEV-509).

Lo que se protege aqui no es la aritmetica --eso ya lo cubre
`test_time_measurement`-- sino que la interfaz no pueda inventar un agregado ni
mezclar mediciones sinteticas con revision real.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from pharma_validator_api.models import Base, FieldFocusInterval, TargetRecord
from pharma_validator_api.time_measurement import TimeMeasurementError
from pharma_validator_api.timing_store import (
    TimingStoreError,
    close_session,
    measure,
    record_focus,
    seconds_per_field,
    start_session,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'timing.db').as_posix()}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    with maker() as session:
        session.add(TargetRecord(id="rec-0", entity_type="medicamento"))
        session.commit()
    return maker


def open_session(session: Session, **kwargs: object):
    return start_session(
        session, target_record_id="rec-0", reviewer_id="ana", started_at=NOW, **kwargs
    )


def test_aggregates_are_computed_not_supplied(factory: sessionmaker[Session]) -> None:
    """La interfaz envia tramos observados; el agregado lo calcula el servidor."""
    with factory() as session:
        opened = open_session(session)
        record_focus(session, opened.id, "CN", 0.0, 8.0)
        record_focus(session, opened.id, "DOSIS", 10.0, 15.0)
        closed = close_session(session, opened.id, ended_at=NOW)
    assert closed.counted_seconds == 13
    assert closed.measured_field_count == 2
    assert closed.discarded_seconds == 0


def test_inactivity_beyond_the_threshold_is_discarded_not_counted(
    factory: sessionmaker[Session],
) -> None:
    """Una pantalla olvidada abierta no puede convertirse en trabajo medido."""
    with factory() as session:
        opened = open_session(session)
        record_focus(session, opened.id, "CN", 0.0, 3600.0)
        closed = close_session(session, opened.id, ended_at=NOW)
    assert closed.counted_seconds == 60
    assert closed.discarded_seconds == 3540
    assert closed.capped_field_count == 1


def test_raw_intervals_survive_aggregation(factory: sessionmaker[Session]) -> None:
    """Sin el dato crudo, cambiar el umbral obligaria a tirar la medicion."""
    with factory() as session:
        opened = open_session(session)
        record_focus(session, opened.id, "CN", 0.0, 90.0)
        close_session(session, opened.id, ended_at=NOW)
        stored = session.scalar(select(func.count()).select_from(FieldFocusInterval))
    assert stored == 1


def test_overlapping_focus_is_rejected_rather_than_averaged(
    factory: sessionmaker[Session],
) -> None:
    """El foco no puede estar en dos sitios; no se inventa una duracion."""
    with factory() as session:
        opened = open_session(session)
        record_focus(session, opened.id, "CN", 0.0, 30.0)
        record_focus(session, opened.id, "CN", 10.0, 40.0)
        with pytest.raises(TimeMeasurementError):
            measure(session, opened.id)


def test_an_inverted_interval_is_refused(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        opened = open_session(session)
        with pytest.raises(ValueError):
            record_focus(session, opened.id, "CN", 30.0, 10.0)


def test_a_session_requires_a_reviewer(factory: sessionmaker[Session]) -> None:
    with factory() as session, pytest.raises(TimingStoreError):
        start_session(session, target_record_id="rec-0", reviewer_id="")


def test_focus_on_an_unknown_session_is_refused(factory: sessionmaker[Session]) -> None:
    with factory() as session, pytest.raises(TimingStoreError):
        record_focus(session, "no-existe", "CN", 0.0, 5.0)


def test_synthetic_sessions_are_excluded_from_the_headline_metric(
    factory: sessionmaker[Session],
) -> None:
    """Un piloto tecnico no puede presentarse como ahorro farmaceutico."""
    with factory() as session:
        fake = start_session(
            session,
            target_record_id="rec-0",
            reviewer_id="test_reviewer_a",
            started_at=NOW,
            is_synthetic=True,
        )
        record_focus(session, fake.id, "CN", 0.0, 40.0)
        close_session(session, fake.id, ended_at=NOW)

        assert seconds_per_field(session) is None
        assert seconds_per_field(session, include_synthetic=True) == 40.0


def test_the_headline_metric_averages_over_measured_fields(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        opened = open_session(session)
        record_focus(session, opened.id, "CN", 0.0, 10.0)
        record_focus(session, opened.id, "DOSIS", 10.0, 20.0)
        close_session(session, opened.id, ended_at=NOW)
        assert seconds_per_field(session) == 10.0


def test_no_measurement_yields_no_invented_average(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        assert seconds_per_field(session) is None
