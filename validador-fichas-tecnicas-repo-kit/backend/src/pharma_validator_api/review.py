"""Persistencia de decisiones de revisión sobre los núcleos ya verificados.

Esta capa **no** reimplementa ninguna regla clínica. Traduce entre la base de
datos y los módulos puros que ya las contienen:

- `validation_states` decide qué decisión es legítima y qué transición se admite;
- `reviewer_identity` decide quién puede firmarla;
- `provenance_conflicts` decide si las fuentes de un campo están en conflicto.

Si una regla se necesitase aquí, pertenece a esos módulos. Duplicarla crearía un
segundo lugar donde relajarla sin que las pruebas de contrato se enterasen.

Alcance provisional (spike de producto, no cierre de Fase 5): la cola de trabajo
(DEV-502), la pantalla de tres zonas (DEV-503), la navegación por teclado
(DEV-504) y el guardado incremental con precarga (DEV-505) no se implementan
aquí. La doble validación (11.1) tampoco: se registra una sola firma por evento.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast, get_args

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.models import (
    BlockInstance,
    FieldValue,
    SourceFragment,
    ValidationDecisionRecord,
    ValueProvenance,
)
from pharma_validator_api.provenance_conflicts import (
    ConflictEvaluation,
    FieldIdentity,
    LogicalState,
    SourceAssertion,
    evaluate_conflict,
)
from pharma_validator_api.reviewer_identity import ReviewerDirectory
from pharma_validator_api.validation_states import (
    ValidationDecision,
    ValidationState,
    assert_transition_allowed,
    validate_decision,
)

#: Vocabulario cerrado de estados lógicos de ADR-0007.
LOGICAL_STATES = frozenset(get_args(LogicalState))

#: Rol de procedencia declarado en el fixture -> rol de fuente de ADR-0007.
#: Un rol no declarado no se adivina: sin correspondencia no se afirma nada,
#: porque inventar la fuente de un valor falsearía la evaluación de conflicto.
PROVENANCE_ROLE_TO_SOURCE_ROLE = {
    "master_baseline": "master_baseline",
    "cima_structured": "cima_structured",
    "technical_sheet": "technical_sheet",
    "pharmacist_decision": "pharmacist_decision",
    "authorized_transformation": "authorized_transformation",
    "external_source": "external_source",
}


@dataclass(frozen=True)
class CurrentDecision:
    """Estado vigente de un campo: el último evento registrado."""

    state: ValidationState
    final_value: str | None
    comment: str | None
    reviewer_id: str
    reviewer_assurance: str
    sequence: int
    decided_at: datetime


def current_decision(session: Session, field_value_id: str) -> CurrentDecision | None:
    """Devuelve el evento vigente, o `None` si el campo nunca se decidió.

    Nunca se decidió y `pendiente` explícito no son lo mismo: el primero es
    ausencia de trabajo y el segundo una decisión registrada.
    """
    row = session.scalars(
        select(ValidationDecisionRecord)
        .where(ValidationDecisionRecord.field_value_id == field_value_id)
        .order_by(ValidationDecisionRecord.sequence.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    state: ValidationState = row.state  # type: ignore[assignment]
    return CurrentDecision(
        state=state,
        final_value=row.final_value,
        comment=row.comment,
        reviewer_id=row.reviewer_id,
        reviewer_assurance=row.reviewer_assurance,
        sequence=row.sequence,
        decided_at=row.decided_at,
    )


def effective_state(session: Session, field_value_id: str) -> ValidationState:
    """Estado efectivo de un campo, `pendiente` mientras nadie haya decidido."""
    decision = current_decision(session, field_value_id)
    return decision.state if decision is not None else "pendiente"


def record_decision(
    session: Session,
    *,
    field_value_id: str,
    decision: ValidationDecision,
    directory: ReviewerDirectory,
    decided_at: datetime | None = None,
) -> ValidationDecisionRecord:
    """Registra una decisión tras pasar por todas las barreras existentes.

    El orden importa: primero se resuelve la identidad, porque una decisión sin
    firma no debe llegar siquiera a evaluarse; después la legitimidad de la
    decisión; y por último la transición desde el estado vigente.
    """
    reviewer = directory.resolve(decision.reviewer_id)
    validate_decision(decision)
    previous = current_decision(session, field_value_id)
    if previous is not None:
        assert_transition_allowed(previous.state, decision.state, decision.comment)
    record = ValidationDecisionRecord(
        field_value_id=field_value_id,
        sequence=1 if previous is None else previous.sequence + 1,
        field_name=decision.field_name,
        state=decision.state,
        final_value=decision.final_value,
        comment=decision.comment,
        reviewer_id=reviewer.identifier,
        reviewer_role=decision.reviewer_role,
        reviewer_assurance=reviewer.assurance,
        seconds_spent=decision.seconds_spent,
        decided_at=decided_at or datetime.now(UTC),
    )
    session.add(record)
    session.commit()
    return record


def decision_history(
    session: Session, field_value_id: str
) -> tuple[ValidationDecisionRecord, ...]:
    """Historial completo en orden de registro; nada se sustituye ni se borra."""
    return tuple(
        session.scalars(
            select(ValidationDecisionRecord)
            .where(ValidationDecisionRecord.field_value_id == field_value_id)
            .order_by(ValidationDecisionRecord.sequence)
        ).all()
    )


def evaluate_field_conflict(
    session: Session,
    field_values: tuple[FieldValue, ...],
    catalog_ordinal: int,
    entity: str,
    block: str,
    field_name: str,
) -> ConflictEvaluation:
    """Evalúa el conflicto entre las fuentes que afirman un mismo campo.

    La unidad de evaluación es **el campo dentro de la ocurrencia de bloque**, no
    la fila de `field_value`. Dos fuentes que discrepan producen dos filas, y
    compararlas por separado daría siempre "sin conflicto": la discrepancia solo
    existe entre ellas. Este fue un defecto real detectado al probar el conjunto
    DEMO, donde maestro y CIMA afirman cantidades distintas del mismo campo.

    Se pasa `rule=None` deliberadamente: la matriz de prioridad por campo no está
    cargada en esta vertical, de modo que un conflicto real queda en
    `unresolved_pending_priority` y exige acción humana. Ninguna discrepancia se
    resuelve automáticamente.
    """
    assertions: list[SourceAssertion] = []
    for field_value in field_values:
        rows = session.scalars(
            select(ValueProvenance)
            .where(ValueProvenance.field_value_id == field_value.id)
            .order_by(ValueProvenance.id)
        ).all()
        for row in rows:
            source_role = PROVENANCE_ROLE_TO_SOURCE_ROLE.get(row.provenance_role)
            if source_role is None:
                # Un rol no declarado no se adivina: afirmar una fuente que el
                # dato no declara falsearía la evaluación.
                continue
            fragment = session.get(SourceFragment, row.source_fragment_id)
            if fragment is None:
                raise RuntimeError(f"Procedencia sin fragmento: {row.id}")
            assertions.append(
                SourceAssertion(
                    assertion_id=row.id,
                    literal_value=field_value.literal_value,
                    logical_state=_logical_state(field_value.logical_state),
                    source_role=source_role,  # type: ignore[arg-type]
                    source_version_id=fragment.document_version_id,
                    source_locator=fragment.locator,
                )
            )
    return evaluate_conflict(
        FieldIdentity(catalog_ordinal, entity, block, field_name),
        tuple(assertions),
    )


def _logical_state(value: str) -> LogicalState:
    """Traduce el estado lógico persistido al vocabulario de ADR-0007.

    Un estado no reconocido es un error explícito, no un valor por defecto:
    asumir `valued` convertiría un dato de significado desconocido en un dato
    afirmado, que es exactamente lo que la regla de no coerción silenciosa
    prohíbe.
    """
    if value not in LOGICAL_STATES:
        raise ValueError(f"Estado lógico no reconocido: {value!r}")
    return cast(LogicalState, value)


def record_block_count(session: Session, target_record_id: str) -> int:
    """Número de ocurrencias de bloque de un registro, sin colapsarlas."""
    return len(
        session.scalars(
            select(BlockInstance).where(BlockInstance.target_record_id == target_record_id)
        ).all()
    )
