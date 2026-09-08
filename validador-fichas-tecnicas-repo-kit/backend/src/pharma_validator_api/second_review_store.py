"""Segunda validación ciega y conciliación (DEV-607/608).

Las reglas de comparación y de cierre viven en `double_review`, que es puro.
Aquí sólo se persiste el flujo y se garantiza la parte que un módulo puro no
puede garantizar: **que el segundo revisor no reciba la primera decisión**.

Esa es la única forma de que la ceguera sea real. Ocultar la primera decisión
en la pantalla mientras la API la sigue entregando no es una segunda lectura
independiente: es la misma lectura con el dato a un `curl` de distancia. Por eso
`blind_view` no filtra un objeto ya cargado, sino que decide qué se consulta.

Flujo:

    pendiente → en_revision → acuerdo | desacuerdo → conciliado

`first_decision_sequence` ancla la comparación a la decisión concreta que se
revisó. Sin ella, una tercera decisión posterior haría que el acuerdo se
calculase contra algo que el segundo revisor nunca vio.

La conciliación **no sobrescribe** las decisiones enfrentadas: registra una
decisión nueva en el historial del campo y guarda por qué. Pisar las dos
originales destruiría la evidencia de que hubo desacuerdo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pharma_validator_api.audit_store import record_event
from pharma_validator_api.double_review import (
    FieldComparison,
    Reconciliation,
    ReviewerDecision,
    compare_field,
    resolve,
)
from pharma_validator_api.models import (
    BlockInstance,
    FieldValue,
    ReconciliationRecord,
    SecondReviewAssignment,
)
from pharma_validator_api.review import (
    current_decision,
    record_decision_in_transaction,
    record_independent_reading,
)
from pharma_validator_api.reviewer_identity import ReviewerDirectory
from pharma_validator_api.validation_states import ValidationDecision


class SecondReviewError(RuntimeError):
    """El flujo de segunda revisión no admite la operación pedida."""


class SecondReviewConflict(RuntimeError):
    """Otra persona cambió la asignación entre la lectura y la escritura."""


@dataclass(frozen=True)
class BlindField:
    """Lo que el segundo revisor puede ver de un campo.

    Deliberadamente **no** contiene la decisión del primer revisor ni su valor
    final. No es un objeto recortado: es todo lo que el store llegó a consultar.
    """

    assignment_id: str
    field_value_id: str
    field_name: str
    literal_value: str | None
    observed_type: str
    logical_state: str
    state: str
    #: Qué se le está pidiendo: emitir su propia lectura del valor de origen.
    instruction: str = (
        "Emita su lectura del valor de origen. La decisión del primer revisor "
        "no se muestra hasta que registre la suya."
    )


def open_second_review(
    session: Session,
    *,
    field_value_id: str,
    actor_id: str,
    actor_assurance: str = "declarada",
) -> SecondReviewAssignment:
    """Marca un campo ya decidido como pendiente de segunda revisión."""
    value = session.get(FieldValue, field_value_id)
    if value is None:
        raise SecondReviewError("Campo no encontrado.")
    existing = session.scalar(
        select(SecondReviewAssignment).where(
            SecondReviewAssignment.field_value_id == field_value_id
        )
    )
    if existing is not None:
        raise SecondReviewError("El campo ya tiene una segunda revisión abierta.")

    first = current_decision(session, field_value_id)
    if first is None:
        raise SecondReviewError(
            "No hay primera decisión que contrastar: la segunda revisión presupone una primera."
        )

    block = session.get(BlockInstance, value.block_instance_id)
    assert block is not None
    now = datetime.now(UTC)
    row = SecondReviewAssignment(
        field_value_id=field_value_id,
        target_record_id=block.target_record_id,
        state="pendiente",
        first_reviewer_id=first.reviewer_id,
        first_decision_sequence=first.sequence,
        revealed=False,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        entity_type="field_value",
        entity_id=field_value_id,
        action="segunda_revision_abierta",
        actor_id=actor_id,
        actor_assurance=actor_assurance,
        after_state={"state": "pendiente", "first_reviewer": first.reviewer_id},
        context={"assignment_id": row.id},
        recorded_at=now,
    )
    return row


def claim_second_review(
    session: Session,
    *,
    assignment_id: str,
    reviewer_id: str,
    expected_version: int | None = None,
    actor_assurance: str = "declarada",
) -> SecondReviewAssignment:
    """Asigna la segunda revisión a un revisor distinto del primero.

    La comprobación de versión y de estado se hace dentro del propio `UPDATE`:
    comprobar antes y escribir después deja una ventana en la que otra persona
    puede reclamar la misma asignación.
    """
    row = session.get(SecondReviewAssignment, assignment_id)
    if row is None:
        raise SecondReviewError("Asignación de segunda revisión no encontrada.")
    if row.first_reviewer_id == reviewer_id:
        raise SecondReviewError(
            "La doble validación exige dos revisores distintos: "
            f"{reviewer_id} firmó la primera decisión."
        )
    if expected_version is not None and expected_version != row.version:
        raise SecondReviewConflict("La asignación ha cambiado desde que la consultó. Recárguela.")

    now = datetime.now(UTC)
    acquired = session.execute(
        update(SecondReviewAssignment)
        .where(
            SecondReviewAssignment.id == assignment_id,
            SecondReviewAssignment.version == row.version,
            SecondReviewAssignment.state == "pendiente",
        )
        .values(
            state="en_revision",
            second_reviewer_id=reviewer_id,
            version=SecondReviewAssignment.version + 1,
            updated_at=now,
        )
        .returning(SecondReviewAssignment.id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if acquired is None:
        raise SecondReviewConflict("La segunda revisión ya no está disponible para reclamar.")

    record_event(
        session,
        entity_type="field_value",
        entity_id=row.field_value_id,
        action="segunda_revision_reclamada",
        actor_id=reviewer_id,
        actor_assurance=actor_assurance,
        before_state={"state": "pendiente"},
        after_state={"state": "en_revision", "second_reviewer": reviewer_id},
        context={"assignment_id": assignment_id},
        recorded_at=now,
    )
    session.refresh(row)
    return row


def blind_view(session: Session, assignment_id: str, reviewer_id: str) -> BlindField:
    """Lo que ve el segundo revisor. Nunca incluye la primera decisión.

    No se carga y luego se recorta: no se consulta. Un filtrado posterior es un
    olvido a un `return` de distancia de convertirse en una fuga.
    """
    row = session.get(SecondReviewAssignment, assignment_id)
    if row is None:
        raise SecondReviewError("Asignación de segunda revisión no encontrada.")
    if row.first_reviewer_id == reviewer_id:
        raise SecondReviewError("Quien firmó la primera decisión no puede realizar la segunda.")
    if row.second_reviewer_id not in (None, reviewer_id):
        raise SecondReviewError("La segunda revisión está asignada a otra persona.")

    value = session.get(FieldValue, row.field_value_id)
    assert value is not None
    return BlindField(
        assignment_id=row.id,
        field_value_id=row.field_value_id,
        field_name=value.field_name,
        literal_value=value.literal_value,
        observed_type=value.observed_type,
        logical_state=value.logical_state,
        state=row.state,
    )


def submit_second_review(
    session: Session,
    *,
    assignment_id: str,
    decision: ValidationDecision,
    directory: ReviewerDirectory,
    expected_version: int | None = None,
) -> SecondReviewAssignment:
    """Registra la segunda lectura y calcula acuerdo o desacuerdo.

    La segunda decisión se guarda como una decisión más del campo: es una
    lectura real, no un voto en una tabla aparte.
    """
    row = session.get(SecondReviewAssignment, assignment_id)
    if row is None:
        raise SecondReviewError("Asignación de segunda revisión no encontrada.")
    if row.state not in ("pendiente", "en_revision"):
        raise SecondReviewError(
            f"La segunda revisión está en estado {row.state} y ya no admite lectura."
        )
    if row.first_reviewer_id == decision.reviewer_id:
        raise SecondReviewError(
            "La doble validación exige dos revisores distintos: "
            f"{decision.reviewer_id} firmó la primera decisión."
        )
    if expected_version is not None and expected_version != row.version:
        raise SecondReviewConflict("La asignación ha cambiado desde que la consultó. Recárguela.")

    if row.second_reviewer_id not in (None, decision.reviewer_id):
        raise SecondReviewConflict("La asignación pertenece a otro revisor.")
    value = session.get(FieldValue, row.field_value_id)
    if value is None or value.field_name != decision.field_name:
        raise SecondReviewError("El campo de la decisión no corresponde a la asignación.")
    latest = current_decision(session, row.field_value_id)
    if latest is None or latest.sequence != row.first_decision_sequence:
        raise SecondReviewConflict("La primera decisión ha cambiado; reinicie la revisión.")
    _lock(session, row)
    first = _first_decision(session, row)
    # La segunda decisión se registra en el historial del campo, con todas las
    # barreras de `validation_states` y `reviewer_identity`.
    second_record = record_independent_reading(
        session,
        field_value_id=row.field_value_id,
        decision=decision,
        directory=directory,
    )

    comparison = compare_field(
        decision.field_name,
        first,
        ReviewerDecision(
            reviewer_id=decision.reviewer_id,
            state=decision.state,
            final_value=decision.final_value,
        ),
    )
    outcome = "acuerdo" if comparison.is_agreement else "desacuerdo"

    now = datetime.now(UTC)
    updated = session.execute(
        update(SecondReviewAssignment)
        .where(
            SecondReviewAssignment.id == assignment_id,
            SecondReviewAssignment.version == row.version,
        )
        .values(
            state=outcome,
            second_reviewer_id=decision.reviewer_id,
            second_decision_sequence=second_record.sequence,
            # Sólo ahora deja de estar oculta la primera decisión: ya no puede
            # influir en una lectura que ya está emitida.
            revealed=True,
            version=SecondReviewAssignment.version + 1,
            updated_at=now,
        )
        .returning(SecondReviewAssignment.id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if updated is None:
        raise SecondReviewConflict("La asignación cambió durante el registro.")

    record_event(
        session,
        entity_type="field_value",
        entity_id=row.field_value_id,
        action="segunda_revision_emitida",
        actor_id=decision.reviewer_id,
        before_state={"state": row.state, "revealed": False},
        after_state={"state": outcome, "revealed": True},
        reason=comparison.kind,
        context={
            "assignment_id": assignment_id,
            "second_sequence": second_record.sequence,
        },
        recorded_at=now,
    )
    session.commit()
    session.refresh(row)
    return row


def _first_decision(session: Session, row: SecondReviewAssignment) -> ReviewerDecision | None:
    """La primera decisión, anclada a la secuencia que se revisó."""
    from pharma_validator_api.models import ValidationDecisionRecord

    stored = session.scalar(
        select(ValidationDecisionRecord).where(
            ValidationDecisionRecord.field_value_id == row.field_value_id,
            ValidationDecisionRecord.sequence == row.first_decision_sequence,
        )
    )
    if stored is None:
        return None
    return ReviewerDecision(
        reviewer_id=stored.reviewer_id,
        state=stored.state,  # type: ignore[arg-type]
        final_value=stored.final_value,
    )


def comparison_for(session: Session, assignment_id: str) -> FieldComparison:
    """Comparación de las dos lecturas. Sólo tras emitir la segunda."""
    row = session.get(SecondReviewAssignment, assignment_id)
    if row is None:
        raise SecondReviewError("Asignación de segunda revisión no encontrada.")
    if not row.revealed:
        raise SecondReviewError(
            "Las dos lecturas no pueden compararse hasta que la segunda se emita."
        )
    value = session.get(FieldValue, row.field_value_id)
    assert value is not None
    return compare_field(
        value.field_name, _first_decision(session, row), _second_decision(session, row)
    )


def _second_decision(session: Session, row: SecondReviewAssignment) -> ReviewerDecision | None:
    from pharma_validator_api.models import ValidationDecisionRecord

    if row.second_decision_sequence is None:
        return None
    stored = session.scalar(
        select(ValidationDecisionRecord).where(
            ValidationDecisionRecord.field_value_id == row.field_value_id,
            ValidationDecisionRecord.sequence == row.second_decision_sequence,
        )
    )
    if stored is None:
        return None
    return ReviewerDecision(
        reviewer_id=stored.reviewer_id,
        state=stored.state,  # type: ignore[arg-type]
        final_value=stored.final_value,
    )


def reconcile(
    session: Session,
    *,
    assignment_id: str,
    reconciliation: Reconciliation,
    directory: ReviewerDirectory,
    reviewer_role: str = "farmaceutico",
    expected_version: int | None = None,
) -> ReconciliationRecord:
    """Cierra una discrepancia registrando una decisión nueva.

    Las dos decisiones enfrentadas se conservan intactas. La conciliación es un
    evento más del historial del campo, no una corrección de lo anterior.
    """
    row = session.get(SecondReviewAssignment, assignment_id)
    if row is None:
        raise SecondReviewError("Asignación de segunda revisión no encontrada.")
    if row.state == "conciliado":
        raise SecondReviewError("Esta discrepancia ya se concilió.")
    if expected_version is not None and expected_version != row.version:
        raise SecondReviewConflict("La asignación ha cambiado desde que la consultó. Recárguela.")

    comparison = comparison_for(session, assignment_id)
    latest = current_decision(session, row.field_value_id)
    if latest is None or latest.sequence != row.second_decision_sequence:
        raise SecondReviewConflict("Hay decisiones posteriores a las lecturas enfrentadas.")
    _lock(session, row)
    # `resolve` rechaza conciliar lo que no discrepa: hacerlo permitiría
    # reescribir un acuerdo sin constancia de que hubo dos lecturas iguales.
    chosen = resolve(comparison, reconciliation)

    reconciler = directory.resolve(reconciliation.resolved_by)
    record = record_decision_in_transaction(
        session,
        field_value_id=row.field_value_id,
        decision=ValidationDecision(
            field_name=comparison.field_name,
            state=chosen.state,
            final_value=chosen.final_value,
            reviewer_id=reconciler.identifier,
            reviewer_role=reviewer_role,  # type: ignore[arg-type]
            comment=reconciliation.comment,
        ),
        directory=directory,
    )

    now = datetime.now(UTC)
    stored = ReconciliationRecord(
        assignment_id=assignment_id,
        field_value_id=row.field_value_id,
        reconciler_id=reconciler.identifier,
        reconciler_assurance=reconciler.assurance,
        resulting_sequence=record.sequence,
        justification=reconciliation.comment,
        reconciled_at=now,
    )
    session.add(stored)

    updated = session.execute(
        update(SecondReviewAssignment)
        .where(
            SecondReviewAssignment.id == assignment_id,
            SecondReviewAssignment.version == row.version,
            SecondReviewAssignment.state == "desacuerdo",
        )
        .values(
            state="conciliado",
            version=SecondReviewAssignment.version + 1,
            updated_at=now,
        )
        .returning(SecondReviewAssignment.id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if updated is None:
        # Dos conciliaciones simultáneas: sólo una puede cerrar la discrepancia.
        session.rollback()
        raise SecondReviewConflict(
            "La discrepancia ya no está abierta: otra conciliación se adelantó."
        )

    record_event(
        session,
        entity_type="field_value",
        entity_id=row.field_value_id,
        action="conciliacion",
        actor_id=reconciler.identifier,
        actor_assurance=reconciler.assurance,
        before_state={"state": "desacuerdo", "kind": comparison.kind},
        after_state={"state": "conciliado", "sequence": record.sequence},
        reason=reconciliation.comment,
        context={"assignment_id": assignment_id, "choice": reconciliation.choice},
        recorded_at=now,
    )
    session.commit()
    return stored


def _lock(session: Session, row: SecondReviewAssignment) -> None:
    acquired = session.execute(
        update(SecondReviewAssignment)
        .where(
            SecondReviewAssignment.id == row.id,
            SecondReviewAssignment.version == row.version,
            SecondReviewAssignment.state == row.state,
        )
        .values(updated_at=datetime.now(UTC))
        .returning(SecondReviewAssignment.id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if acquired is None:
        raise SecondReviewConflict("La asignación cambió durante la operación.")


def pending_second_reviews(
    session: Session, *, reviewer_id: str | None = None
) -> list[SecondReviewAssignment]:
    """Segundas revisiones disponibles, excluyendo las del propio primer firmante."""
    query = select(SecondReviewAssignment).where(
        SecondReviewAssignment.state.in_(["pendiente", "en_revision"])
    )
    if reviewer_id is not None:
        query = query.where(SecondReviewAssignment.first_reviewer_id != reviewer_id)
    return list(session.scalars(query.order_by(SecondReviewAssignment.created_at)))


def disagreements(session: Session) -> list[SecondReviewAssignment]:
    """Discrepancias abiertas, pendientes de conciliar."""
    return list(
        session.scalars(
            select(SecondReviewAssignment)
            .where(SecondReviewAssignment.state == "desacuerdo")
            .order_by(SecondReviewAssignment.updated_at)
        )
    )
