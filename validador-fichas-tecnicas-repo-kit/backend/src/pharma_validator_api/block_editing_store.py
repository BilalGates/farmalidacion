"""Persistencia de la edición de bloques repetibles (DEV-507).

Las reglas viven en `block_editing`, que es puro. Aquí sólo se traduce entre
esas ocurrencias y las filas de `block_instance` / `field_value`, y se deja el
rastro en `block_edit_record`.

Dos invariantes gobiernan este módulo:

1. **Ninguna operación destruye el dato de origen sin registrarlo.** Antes de
   aplicar un cambio se serializa el estado previo de las ocurrencias afectadas
   en `before_state`. Eliminar y fusionar dejan de ser irreversibles de hecho.

2. **La procedencia no se fabrica.** Una ocurrencia creada por un revisor nace
   sin `source_fragment_id` y sus valores sin `value_provenance`: no hay ninguna
   fuente que la afirme, y decir lo contrario haría indistinguible una fila
   inventada de una importada del maestro.

Todo se aplica dentro de la transacción de la sesión que se recibe. El llamante
decide cuándo confirmar, de modo que una operación a medio aplicar no pueda
quedar escrita.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.block_editing import (
    BlockEdit,
    BlockEditingError,
    BlockOccurrence,
    create_occurrence,
    delete_occurrence,
    mark_not_applicable,
    merge_occurrences,
    reorder_occurrences,
    revert_not_applicable,
)
from pharma_validator_api.models import (
    BlockEditRecord,
    BlockInstance,
    FieldValue,
    ValueProvenance,
)


def load_occurrences(
    session: Session, target_record_id: str, block_type: str
) -> tuple[BlockOccurrence, ...]:
    """Lee las ocurrencias de un bloque en el orden declarado por su ordinal."""
    blocks = session.scalars(
        select(BlockInstance)
        .where(
            BlockInstance.target_record_id == target_record_id,
            BlockInstance.block_type == block_type,
        )
        .order_by(BlockInstance.ordinal)
    ).all()

    occurrences: list[BlockOccurrence] = []
    for block in blocks:
        values = session.scalars(
            select(FieldValue)
            .where(FieldValue.block_instance_id == block.id)
            .order_by(FieldValue.field_name)
        ).all()
        occurrences.append(
            BlockOccurrence(
                occurrence_id=block.id,
                ordinal=block.ordinal,
                values=tuple((item.field_name, item.literal_value) for item in values),
                # La ocurrencia procede de una fuente si tiene fragmento. Es la
                # misma distinción que usa `block_editing` para proteger el dato.
                origin_provenance=block.source_fragment_id,
                not_applicable=bool(block.not_applicable),
                comment=block.edit_comment,
            )
        )
    return tuple(occurrences)


def _serialize(occurrences: tuple[BlockOccurrence, ...], affected: tuple[str, ...]) -> str:
    """Estado previo de las ocurrencias afectadas, para poder auditarlo."""
    return json.dumps(
        [
            {
                "occurrence_id": item.occurrence_id,
                "ordinal": item.ordinal,
                "values": [[name, value] for name, value in item.values],
                "origin_provenance": item.origin_provenance,
                "not_applicable": item.not_applicable,
                "comment": item.comment,
            }
            for item in occurrences
            if item.occurrence_id in affected
        ],
        ensure_ascii=False,
        sort_keys=True,
    )


def _next_sequence(session: Session, target_record_id: str) -> int:
    current = session.scalar(
        select(func.max(BlockEditRecord.sequence)).where(
            BlockEditRecord.target_record_id == target_record_id
        )
    )
    return (current or 0) + 1


def _apply(
    session: Session,
    target_record_id: str,
    block_type: str,
    before: tuple[BlockOccurrence, ...],
    edit: BlockEdit,
    reviewer_id: str,
    reviewer_assurance: str,
) -> None:
    """Escribe el resultado de una operación ya decidida por el módulo puro."""
    existing = {item.occurrence_id for item in before}
    resulting = {item.occurrence_id for item in edit.occurrences}

    # 1. Rastro primero: si algo falla después, la transacción entera se
    #    deshace, pero nunca se aplica un cambio que no quede registrado.
    session.add(
        BlockEditRecord(
            target_record_id=target_record_id,
            sequence=_next_sequence(session, target_record_id),
            block_type=block_type,
            operation=edit.operation,
            affected_ids=json.dumps(list(edit.affected_ids), ensure_ascii=False),
            before_state=_serialize(before, edit.affected_ids),
            comment=edit.detail,
            reviewer_id=reviewer_id,
            reviewer_assurance=reviewer_assurance,
            edited_at=datetime.now(UTC),
        )
    )

    # 2. Ocurrencias retiradas. Se borran sus valores y su procedencia: la fila
    #    ya no existe en el modelo canónico y `before_state` conserva qué había.
    for removed in existing - resulting:
        value_ids = list(
            session.scalars(
                select(FieldValue.id).where(FieldValue.block_instance_id == removed)
            )
        )
        if value_ids:
            session.execute(
                delete(ValueProvenance).where(ValueProvenance.field_value_id.in_(value_ids))
            )
            session.execute(delete(FieldValue).where(FieldValue.id.in_(value_ids)))
        session.execute(delete(BlockInstance).where(BlockInstance.id == removed))

    # 3. Ocurrencias nuevas y actualizadas.
    for occurrence in edit.occurrences:
        block = session.get(BlockInstance, occurrence.occurrence_id)
        if block is None:
            # Creada por el revisor: sin fragmento de origen, porque ninguna
            # fuente la afirma. `block_editing` ya impide declarar procedencia.
            block = BlockInstance(
                id=occurrence.occurrence_id,
                target_record_id=target_record_id,
                block_type=block_type,
                ordinal=occurrence.ordinal,
                source_fragment_id=None,
            )
            session.add(block)
            for name, value in occurrence.values:
                session.add(
                    FieldValue(
                        block_instance_id=block.id,
                        field_name=name,
                        literal_value=value,
                        observed_type="texto",
                        logical_state="valued" if value is not None else "empty",
                    )
                )
        else:
            block.ordinal = occurrence.ordinal
            _update_values(session, block, occurrence)
        block.not_applicable = occurrence.not_applicable
        block.edit_comment = occurrence.comment


def _update_values(session: Session, block: BlockInstance, occurrence: BlockOccurrence) -> None:
    """Actualiza los valores de una ocurrencia existente.

    Un campo que la operación añade (por ejemplo, el que aporta la ocurrencia
    fusionada) se crea sin procedencia: el valor pasa a afirmarlo el revisor y
    no la fuente, y atribuirlo al maestro sería falsear la trazabilidad.
    """
    stored = {
        item.field_name: item
        for item in session.scalars(
            select(FieldValue).where(FieldValue.block_instance_id == block.id)
        )
    }
    for name, value in occurrence.values:
        current = stored.get(name)
        if current is None:
            session.add(
                FieldValue(
                    block_instance_id=block.id,
                    field_name=name,
                    literal_value=value,
                    observed_type="texto",
                    logical_state="valued" if value is not None else "empty",
                )
            )
        elif current.literal_value != value:
            current.literal_value = value
            current.logical_state = "valued" if value is not None else "empty"


def _run(
    session: Session,
    target_record_id: str,
    block_type: str,
    reviewer_id: str,
    reviewer_assurance: str,
    operation: str,
    **kwargs: object,
) -> tuple[BlockOccurrence, ...]:
    before = load_occurrences(session, target_record_id, block_type)
    if not before and operation != "crear":
        raise BlockEditingError(f"El registro no tiene ocurrencias de {block_type}.")

    if operation == "crear":
        values: tuple[tuple[str, str | None], ...] = tuple(kwargs["values"])  # type: ignore[arg-type]
        new = BlockOccurrence(
            occurrence_id=str(kwargs["occurrence_id"]),
            ordinal=len(before) + 1,
            values=values,
        )
        edit = create_occurrence(before, new)
    elif operation == "eliminar":
        edit = delete_occurrence(
            before, str(kwargs["occurrence_id"]), kwargs.get("comment")  # type: ignore[arg-type]
        )
    elif operation == "reordenar":
        edit = reorder_occurrences(before, tuple(kwargs["ordered_ids"]))  # type: ignore[arg-type]
    elif operation == "fusionar":
        edit = merge_occurrences(
            before,
            str(kwargs["source_id"]),
            str(kwargs["target_id"]),
            str(kwargs["comment"]),
        )
    elif operation == "marcar_no_aplicable":
        edit = mark_not_applicable(
            before, str(kwargs["occurrence_id"]), str(kwargs["comment"])
        )
    elif operation == "revertir_no_aplicable":
        edit = revert_not_applicable(
            before, str(kwargs["occurrence_id"]), str(kwargs["comment"])
        )
    else:
        raise BlockEditingError(f"Operación de bloque no reconocida: {operation}.")

    _apply(session, target_record_id, block_type, before, edit, reviewer_id, reviewer_assurance)
    session.flush()
    return edit.occurrences


def edit_block(
    session: Session,
    *,
    target_record_id: str,
    block_type: str,
    reviewer_id: str,
    reviewer_assurance: str,
    operation: str,
    **kwargs: object,
) -> tuple[BlockOccurrence, ...]:
    """Aplica una operación de bloque y deja su rastro. No confirma."""
    return _run(
        session,
        target_record_id,
        block_type,
        reviewer_id,
        reviewer_assurance,
        operation,
        **kwargs,
    )


def edit_history(session: Session, target_record_id: str) -> list[BlockEditRecord]:
    """Historial de ediciones de bloque de un registro, en orden."""
    return list(
        session.scalars(
            select(BlockEditRecord)
            .where(BlockEditRecord.target_record_id == target_record_id)
            .order_by(BlockEditRecord.sequence)
        )
    )
