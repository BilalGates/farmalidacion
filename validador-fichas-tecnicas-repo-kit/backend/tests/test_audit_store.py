"""Diario de auditoría append-only (DEV-609).

Lo que se comprueba no es que se escriban filas, sino que no se pueda borrar ni
reescribir la historia, que un fallo no deje rastro de algo que no ocurrió, y
que el historial reconstruya el orden real uniendo las tres fuentes.

Base desechable con el esquema real; el corpus real no se toca.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from conftest import seed_reviewable_record
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pharma_validator_api.audit_store import (
    events_for,
    record_event,
    record_history,
)
from pharma_validator_api.block_editing_store import edit_block
from pharma_validator_api.models import AuditEvent, ValidationDecisionRecord

BLOCK = "active_ingredient_general"


@pytest.fixture
def session(scratch_db_url: str):
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session, occurrences=2)
        yield session
    engine.dispose()


def test_records_actor_action_and_both_states(session: Session) -> None:
    record_event(
        session,
        entity_type="field_value",
        entity_id="fv-rec-1-1-0",
        action="segunda_revision_emitida",
        actor_id="luis",
        before_state={"state": "pendiente"},
        after_state={"state": "confirmado"},
        reason="Coincide con la ficha técnica.",
    )
    session.commit()

    stored = session.scalar(select(AuditEvent))
    assert stored is not None
    assert stored.actor_id == "luis"
    assert stored.actor_assurance == "declarada"
    assert stored.action == "segunda_revision_emitida"
    # El estado anterior es lo que hace auditable el cambio: sin él habría que
    # reconstruirlo confiando en que nada más lo tocó.
    assert '"state": "pendiente"' in (stored.before_state or "")
    assert '"state": "confirmado"' in (stored.after_state or "")


def test_the_journal_cannot_be_rewritten(session: Session) -> None:
    record_event(
        session,
        entity_type="export_run",
        entity_id="run-1",
        action="exportacion_completada",
        actor_id="ana",
    )
    session.commit()

    stored = session.scalar(select(AuditEvent))
    assert stored is not None
    stored.reason = "otra cosa"
    with pytest.raises(Exception, match="append-only"):
        session.commit()
    session.rollback()


def test_the_journal_cannot_be_deleted(session: Session) -> None:
    record_event(
        session,
        entity_type="export_run",
        entity_id="run-1",
        action="exportacion_completada",
        actor_id="ana",
    )
    session.commit()

    stored = session.scalar(select(AuditEvent))
    assert stored is not None
    session.delete(stored)
    with pytest.raises(Exception, match="append-only"):
        session.commit()
    session.rollback()


def test_a_rolled_back_operation_leaves_no_trace(session: Session) -> None:
    # El evento vive en la transacción del llamante: si la operación se
    # deshace, su rastro se deshace con ella. Un diario que registrase intentos
    # fallidos como hechos consumados mentiría.
    record_event(
        session,
        entity_type="field_value",
        entity_id="fv-rec-1-1-0",
        action="conciliacion",
        actor_id="ana",
    )
    session.rollback()
    assert events_for(session) == []


def test_an_event_without_actor_is_refused(session: Session) -> None:
    with pytest.raises(ValueError, match="actor"):
        record_event(
            session,
            entity_type="field_value",
            entity_id="fv-1",
            action="algo",
            actor_id="",
        )


def test_events_can_be_filtered_by_entity(session: Session) -> None:
    record_event(
        session,
        entity_type="export_run",
        entity_id="run-1",
        action="exportacion_completada",
        actor_id="ana",
    )
    record_event(
        session,
        entity_type="field_value",
        entity_id="fv-9",
        action="conciliacion",
        actor_id="luis",
    )
    session.commit()

    assert len(events_for(session)) == 2
    assert len(events_for(session, entity_type="export_run")) == 1
    assert len(events_for(session, entity_id="fv-9")) == 1


def test_history_joins_decisions_blocks_and_journal_in_order(session: Session) -> None:
    base = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)

    # 1. Una decisión sobre un campo del registro.
    session.add(
        ValidationDecisionRecord(
            field_value_id="fv-rec-1-1-0",
            sequence=1,
            field_name="DESCRIPCION",
            state="confirmado",
            final_value="valor",
            comment="primera decision",
            reviewer_id="ana",
            reviewer_role="farmaceutico",
            reviewer_assurance="declarada",
            decided_at=base,
        )
    )
    session.commit()

    # 2. Una edición de bloque.
    edit_block(
        session,
        target_record_id="rec-1",
        block_type=BLOCK,
        reviewer_id="ana",
        reviewer_assurance="declarada",
        operation="marcar_no_aplicable",
        occurrence_id="blk-rec-1-2",
        comment="Fuera de alcance.",
    )
    session.commit()

    # 3. Un evento del diario transversal.
    record_event(
        session,
        entity_type="field_value",
        entity_id="fv-rec-1-1-0",
        action="segunda_revision_emitida",
        actor_id="luis",
        reason="acuerdo",
        recorded_at=base + timedelta(hours=2),
    )
    session.commit()

    history = record_history(session, "rec-1")
    # Las tres fuentes aparecen unidas: quien audite no tiene que saber que
    # existen tres tablas con tres formatos.
    assert {item.source for item in history} == {"decision", "bloque", "field_value"}
    assert [item.actor_id for item in history] == ["ana", "ana", "luis"]
    # Y en orden cronológico real.
    assert history == sorted(history, key=lambda item: item.occurred_at)


def test_history_ignores_other_records(session: Session) -> None:
    seed_reviewable_record(session, record_id="rec-2")
    record_event(
        session,
        entity_type="target_record",
        entity_id="rec-2",
        action="exportado",
        actor_id="ana",
    )
    session.commit()

    assert record_history(session, "rec-1") == []
    assert len(record_history(session, "rec-2")) == 1


def test_history_is_stable_across_reads(session: Session) -> None:
    base = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
    for index in range(3):
        record_event(
            session,
            entity_type="target_record",
            entity_id="rec-1",
            action=f"accion-{index}",
            actor_id="ana",
            recorded_at=base,
        )
    session.commit()

    # Mismo instante en los tres: el orden no puede depender del azar, o dos
    # lecturas del mismo historial contarían historias distintas.
    assert record_history(session, "rec-1") == record_history(session, "rec-1")
