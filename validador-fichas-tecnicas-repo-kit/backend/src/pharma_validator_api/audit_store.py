"""Diario de auditoría append-only (DEV-609).

Un **único** diario transversal. Los historiales de dominio que ya existen
—`validation_decision_record` y `block_edit_record`— siguen siendo la verdad de
lo suyo; este módulo no los duplica ni los sustituye. Registra las operaciones
que ninguno de los dos cubre (segunda revisión, conciliación, exportación,
exclusión) y ofrece una lectura ordenada que los une, de modo que se pueda
reconstruir qué pasó sin consultar tres sitios con tres formatos.

Reglas:

- **No se confirma nada aquí.** El evento se añade a la transacción del
  llamante. Si la operación se deshace, su rastro se deshace con ella: un
  diario que registrase intentos fallidos como hechos consumados mentiría.
- **Nunca se actualiza ni se borra.** Lo garantiza el modelo; este módulo no
  ofrece siquiera una función para intentarlo.
- **El contexto no lleva datos de paciente.** Se serializa lo mínimo para
  entender la operación.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.models import (
    AuditEvent,
    BlockEditRecord,
    ValidationDecisionRecord,
)


def _dump(value: Any) -> str | None:
    """Serializa de forma estable: dos estados iguales dan la misma cadena."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def record_event(
    session: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: str,
    actor_assurance: str = "declarada",
    before_state: Any = None,
    after_state: Any = None,
    reason: str | None = None,
    context: Any = None,
    recorded_at: datetime | None = None,
) -> AuditEvent:
    """Añade un evento a la transacción en curso. No hace commit."""
    if not entity_type or not entity_id or not action:
        raise ValueError("Un evento de auditoría exige entidad y acción.")
    if not actor_id:
        raise ValueError("Un evento de auditoría exige actor identificado.")
    row = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        actor_assurance=actor_assurance,
        before_state=_dump(before_state),
        after_state=_dump(after_state),
        reason=reason,
        context=_dump(context),
        recorded_at=recorded_at or datetime.now(UTC),
    )
    session.add(row)
    return row


@dataclass(frozen=True)
class HistoryEntry:
    """Una línea del historial unificado de un registro (DEV-609)."""

    occurred_at: datetime
    source: str
    action: str
    actor_id: str
    entity_id: str
    detail: str | None
    sequence: int | None = None


def _aware(moment: datetime) -> datetime:
    """SQLite devuelve `datetime` sin zona; ordenarlos mezclados falla."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def record_history(session: Session, target_record_id: str) -> list[HistoryEntry]:
    """Historial completo de un registro, en orden cronológico.

    Une las tres fuentes en lugar de exigir que quien audite sepa que existen:
    decisiones de validación de cualquier campo del registro, ediciones de
    bloque y eventos del diario transversal.
    """
    entries: list[HistoryEntry] = []

    # Decisiones: se llega a ellas por los bloques del registro.
    from pharma_validator_api.models import BlockInstance, FieldValue

    field_ids = list(
        session.scalars(
            select(FieldValue.id)
            .join(BlockInstance, BlockInstance.id == FieldValue.block_instance_id)
            .where(BlockInstance.target_record_id == target_record_id)
        )
    )
    if field_ids:
        decisions = session.scalars(
            select(ValidationDecisionRecord)
            .where(ValidationDecisionRecord.field_value_id.in_(field_ids))
            .order_by(ValidationDecisionRecord.sequence)
        )
        for item in decisions:
            entries.append(
                HistoryEntry(
                    occurred_at=_aware(item.decided_at),
                    source="decision",
                    action=item.state,
                    actor_id=item.reviewer_id,
                    entity_id=item.field_value_id,
                    detail=item.comment or item.field_name,
                    sequence=item.sequence,
                )
            )

    for edit in session.scalars(
        select(BlockEditRecord)
        .where(BlockEditRecord.target_record_id == target_record_id)
        .order_by(BlockEditRecord.sequence)
    ):
        entries.append(
            HistoryEntry(
                occurred_at=_aware(edit.edited_at),
                source="bloque",
                action=edit.operation,
                actor_id=edit.reviewer_id,
                entity_id=edit.block_type,
                detail=edit.comment,
                sequence=edit.sequence,
            )
        )

    # Eventos del diario que apuntan al registro o a alguno de sus campos.
    referenced = {target_record_id, *field_ids}
    for row in session.scalars(
        select(AuditEvent).order_by(AuditEvent.recorded_at)
    ):
        if row.entity_id not in referenced:
            continue
        entries.append(
            HistoryEntry(
                occurred_at=_aware(row.recorded_at),
                source=row.entity_type,
                action=row.action,
                actor_id=row.actor_id,
                entity_id=row.entity_id,
                detail=row.reason,
            )
        )

    # Orden estable: la fecha manda, y a igualdad se conserva el orden de
    # llegada por fuente para que dos ejecuciones den la misma lista.
    entries.sort(key=lambda item: (item.occurred_at, item.source, item.sequence or 0))
    return entries


def events_for(
    session: Session, *, entity_type: str | None = None, entity_id: str | None = None
) -> list[AuditEvent]:
    """Eventos del diario, filtrados y en orden."""
    query = select(AuditEvent)
    if entity_type is not None:
        query = query.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(AuditEvent.entity_id == entity_id)
    return list(session.scalars(query.order_by(AuditEvent.recorded_at)))
