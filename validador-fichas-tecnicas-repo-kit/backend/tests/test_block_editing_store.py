"""Persistencia de la edición de bloques repetibles (DEV-507).

Lo que se comprueba aquí no es que las operaciones funcionen —eso ya lo cubre
`test_block_editing` sobre el módulo puro— sino que al escribirlas en la base
no se pierda dato de origen, no se fabrique procedencia y quede rastro.

Todas usan una base desechable construida con el esquema real (`scratch_db_url`
en `conftest`). El corpus real no es entorno de escritura.
"""

from __future__ import annotations

import json

import pytest
from conftest import seed_reviewable_record
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pharma_validator_api.block_editing import BlockEditingError
from pharma_validator_api.block_editing_store import (
    edit_block,
    edit_history,
    load_occurrences,
)
from pharma_validator_api.models import (
    BlockEditRecord,
    BlockInstance,
    FieldValue,
    ValueProvenance,
)

BLOCK = "active_ingredient_general"


@pytest.fixture
def session(scratch_db_url: str):
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session, occurrences=2)
        yield session
    engine.dispose()


def test_reads_occurrences_with_their_origin(session: Session) -> None:
    occurrences = load_occurrences(session, "rec-1", BLOCK)
    assert [item.ordinal for item in occurrences] == [1, 2]
    # Ambas vienen del maestro: tienen fragmento de origen.
    assert all(item.is_from_source for item in occurrences)


def test_created_occurrence_carries_no_fabricated_provenance(session: Session) -> None:
    edit_block(
        session,
        target_record_id="rec-1",
        block_type=BLOCK,
        reviewer_id="ana",
        reviewer_assurance="declarada",
        operation="crear",
        occurrence_id="nueva-1",
        values=(("DESCRIPCION", "añadida por el revisor"),),
    )
    session.commit()

    block = session.get(BlockInstance, "nueva-1")
    assert block is not None
    # Sin fragmento: ninguna fuente afirma esta fila.
    assert block.source_fragment_id is None
    value = session.scalar(
        select(FieldValue).where(FieldValue.block_instance_id == "nueva-1")
    )
    assert value is not None
    assert session.scalar(
        select(ValueProvenance).where(ValueProvenance.field_value_id == value.id)
    ) is None


def test_deleting_an_imported_occurrence_requires_a_comment(session: Session) -> None:
    with pytest.raises(BlockEditingError, match="comentario"):
        edit_block(
            session,
            target_record_id="rec-1",
            block_type=BLOCK,
            reviewer_id="ana",
            reviewer_assurance="declarada",
            operation="eliminar",
            occurrence_id="blk-rec-1-1",
        )
    session.rollback()
    # Nada se ha borrado.
    assert len(load_occurrences(session, "rec-1", BLOCK)) == 2


def test_deletion_preserves_the_previous_state_in_the_audit_trail(session: Session) -> None:
    before = load_occurrences(session, "rec-1", BLOCK)
    original = next(item for item in before if item.occurrence_id == "blk-rec-1-1")

    edit_block(
        session,
        target_record_id="rec-1",
        block_type=BLOCK,
        reviewer_id="ana",
        reviewer_assurance="declarada",
        operation="eliminar",
        occurrence_id="blk-rec-1-1",
        comment="La fuente la duplicaba.",
    )
    session.commit()

    assert session.get(BlockInstance, "blk-rec-1-1") is None
    record = session.scalar(select(BlockEditRecord))
    assert record is not None
    assert record.operation == "eliminar"
    assert record.comment == "La fuente la duplicaba."
    # El dato de origen no desaparece: queda serializado y recuperable.
    kept = json.loads(record.before_state)
    assert kept[0]["occurrence_id"] == "blk-rec-1-1"
    assert [list(pair) for pair in original.values] == kept[0]["values"]


def test_deletion_removes_orphan_values_and_provenance(session: Session) -> None:
    values = list(
        session.scalars(
            select(FieldValue.id).where(FieldValue.block_instance_id == "blk-rec-1-2")
        )
    )
    edit_block(
        session,
        target_record_id="rec-1",
        block_type=BLOCK,
        reviewer_id="ana",
        reviewer_assurance="declarada",
        operation="eliminar",
        occurrence_id="blk-rec-1-2",
        comment="Retirada.",
    )
    session.commit()

    # No quedan valores ni procedencia colgando de una ocurrencia inexistente.
    assert session.scalars(select(FieldValue).where(FieldValue.id.in_(values))).all() == []
    assert (
        session.scalars(
            select(ValueProvenance).where(ValueProvenance.field_value_id.in_(values))
        ).all()
        == []
    )


def test_reordering_renumbers_without_losing_occurrences(session: Session) -> None:
    edit_block(
        session,
        target_record_id="rec-1",
        block_type=BLOCK,
        reviewer_id="ana",
        reviewer_assurance="declarada",
        operation="reordenar",
        ordered_ids=("blk-rec-1-2", "blk-rec-1-1"),
    )
    session.commit()

    occurrences = load_occurrences(session, "rec-1", BLOCK)
    assert [item.occurrence_id for item in occurrences] == ["blk-rec-1-2", "blk-rec-1-1"]
    assert [item.ordinal for item in occurrences] == [1, 2]


def test_reordering_cannot_drop_an_occurrence(session: Session) -> None:
    # Omitir una ocurrencia la eliminaría de hecho, esquivando la salvaguarda.
    with pytest.raises(BlockEditingError, match="todas las ocurrencias"):
        edit_block(
            session,
            target_record_id="rec-1",
            block_type=BLOCK,
            reviewer_id="ana",
            reviewer_assurance="declarada",
            operation="reordenar",
            ordered_ids=("blk-rec-1-1",),
        )
    session.rollback()
    assert len(load_occurrences(session, "rec-1", BLOCK)) == 2


def test_merging_conflicting_values_is_refused(session: Session) -> None:
    # Las dos ocurrencias sembradas afirman lo mismo; se provoca la diferencia.
    value = session.scalar(
        select(FieldValue).where(
            FieldValue.block_instance_id == "blk-rec-1-2",
            FieldValue.field_name == "DESCRIPCION",
        )
    )
    assert value is not None
    value.literal_value = "otra descripción"
    session.commit()

    with pytest.raises(BlockEditingError, match="valores distintos"):
        edit_block(
            session,
            target_record_id="rec-1",
            block_type=BLOCK,
            reviewer_id="ana",
            reviewer_assurance="declarada",
            operation="fusionar",
            source_id="blk-rec-1-2",
            target_id="blk-rec-1-1",
            comment="Duplicadas.",
        )
    session.rollback()
    assert len(load_occurrences(session, "rec-1", BLOCK)) == 2


def test_marking_not_applicable_keeps_the_values_intact(session: Session) -> None:
    before = load_occurrences(session, "rec-1", BLOCK)
    original = next(item for item in before if item.occurrence_id == "blk-rec-1-1")

    edit_block(
        session,
        target_record_id="rec-1",
        block_type=BLOCK,
        reviewer_id="ana",
        reviewer_assurance="declarada",
        operation="marcar_no_aplicable",
        occurrence_id="blk-rec-1-1",
        comment="Fuera de alcance para esta ficha.",
    )
    session.commit()

    block = session.get(BlockInstance, "blk-rec-1-1")
    assert block is not None and block.not_applicable is True
    # Marcar no borra: los valores siguen ahí, que es lo que la distingue de
    # eliminar y lo que la hace reversible.
    after = next(
        item
        for item in load_occurrences(session, "rec-1", BLOCK)
        if item.occurrence_id == "blk-rec-1-1"
    )
    assert after.values == original.values


def test_marking_is_reversible(session: Session) -> None:
    for operation, comment in (
        ("marcar_no_aplicable", "Fuera de alcance."),
        ("revertir_no_aplicable", "Vuelve a aplicar."),
    ):
        edit_block(
            session,
            target_record_id="rec-1",
            block_type=BLOCK,
            reviewer_id="ana",
            reviewer_assurance="declarada",
            operation=operation,
            occurrence_id="blk-rec-1-1",
            comment=comment,
        )
    session.commit()

    block = session.get(BlockInstance, "blk-rec-1-1")
    assert block is not None and block.not_applicable is False
    assert [item.operation for item in edit_history(session, "rec-1")] == [
        "marcar_no_aplicable",
        "revertir_no_aplicable",
    ]


def test_history_is_append_only(session: Session) -> None:
    edit_block(
        session,
        target_record_id="rec-1",
        block_type=BLOCK,
        reviewer_id="ana",
        reviewer_assurance="declarada",
        operation="marcar_no_aplicable",
        occurrence_id="blk-rec-1-1",
        comment="Fuera de alcance.",
    )
    session.commit()

    record = session.scalar(select(BlockEditRecord))
    assert record is not None
    record.comment = "otra cosa"
    with pytest.raises(Exception, match="append-only"):
        session.commit()
    session.rollback()


def test_sequence_advances_per_record(session: Session) -> None:
    for index in range(2):
        edit_block(
            session,
            target_record_id="rec-1",
            block_type=BLOCK,
            reviewer_id="ana",
            reviewer_assurance="declarada",
            operation="crear",
            occurrence_id=f"nueva-{index}",
            values=(("DESCRIPCION", f"valor {index}"),),
        )
    session.commit()
    assert [item.sequence for item in edit_history(session, "rec-1")] == [1, 2]


def test_a_failed_operation_leaves_no_trace(session: Session) -> None:
    with pytest.raises(BlockEditingError):
        edit_block(
            session,
            target_record_id="rec-1",
            block_type=BLOCK,
            reviewer_id="ana",
            reviewer_assurance="declarada",
            operation="eliminar",
            occurrence_id="blk-rec-1-1",
        )
    session.rollback()
    # Ni cambio ni registro: la operación rechazada no deja rastro a medias.
    assert edit_history(session, "rec-1") == []
    assert len(load_occurrences(session, "rec-1", BLOCK)) == 2
