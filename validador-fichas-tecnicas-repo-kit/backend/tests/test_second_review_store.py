"""Segunda validación ciega y conciliación (DEV-607/608).

Lo que se comprueba:

- que la ceguera exista **en el dato**, no en la presentación;
- que quien firmó la primera lectura no pueda hacer la segunda;
- que conciliar no borre ninguna de las dos decisiones enfrentadas;
- que dos actores concurrentes no puedan cerrar la misma discrepancia.

Base desechable con el esquema real; el corpus real no se toca.
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields

import pytest
from conftest import seed_reviewable_record
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pharma_validator_api.double_review import DoubleReviewError, Reconciliation
from pharma_validator_api.models import (
    ReconciliationRecord,
    ValidationDecisionRecord,
)
from pharma_validator_api.review import record_decision
from pharma_validator_api.reviewer_identity import ReviewerDirectory
from pharma_validator_api.second_review_store import (
    BlindField,
    SecondReviewConflict,
    SecondReviewError,
    blind_view,
    claim_second_review,
    comparison_for,
    disagreements,
    open_second_review,
    pending_second_reviews,
    reconcile,
    submit_second_review,
)
from pharma_validator_api.validation_states import ValidationDecision

FIELD = "fv-rec-1-1-0"


@pytest.fixture
def directory() -> ReviewerDirectory:
    return ReviewerDirectory.from_configuration(("ana:Ana", "luis:Luis", "eva:Eva"))


@pytest.fixture
def session(scratch_db_url: str):
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session)
        yield session
    engine.dispose()


def first_decision(
    session: Session, directory: ReviewerDirectory, *, value: str = "ácido nicotínico"
) -> None:
    record_decision(
        session,
        field_value_id=FIELD,
        decision=ValidationDecision(
            field_name="DESCRIPCION",
            state="confirmado",
            final_value=value,
            reviewer_id="ana",
            reviewer_role="farmaceutico",
        ),
        directory=directory,
    )


def test_a_second_review_presupposes_a_first(session: Session) -> None:
    with pytest.raises(SecondReviewError, match="presupone una primera"):
        open_second_review(session, field_value_id=FIELD, actor_id="ana")


def test_opening_anchors_the_first_decision(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory)
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()

    assert row.state == "pendiente"
    assert row.first_reviewer_id == "ana"
    # Anclada a la secuencia concreta que se revisó: una decisión posterior no
    # puede cambiar contra qué se compara.
    assert row.first_decision_sequence == 1
    assert row.revealed is False


def test_the_blind_view_never_carries_the_first_decision(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory, value="valor de la primera lectura")
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()

    view = blind_view(session, row.id, "luis")
    assert isinstance(view, BlindField)
    # El valor de origen sí se ve: es lo que hay que leer.
    assert view.literal_value == "ácido nicotínico"

    # Ningún atributo del objeto contiene la lectura del primer revisor. Se
    # comprueba sobre el objeto entero y no sobre una lista de campos elegidos,
    # porque añadir un campo nuevo no debe poder abrir una fuga en silencio.
    serialized = " ".join(
        str(getattr(view, item.name)) for item in dataclass_fields(view)
    )
    assert "valor de la primera lectura" not in serialized
    assert "ana" not in serialized
    assert "confirmado" not in serialized


def test_the_first_reviewer_cannot_perform_the_second_review(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory)
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()

    with pytest.raises(SecondReviewError, match="primera decisión"):
        blind_view(session, row.id, "ana")
    with pytest.raises(SecondReviewError, match="dos revisores distintos"):
        claim_second_review(session, assignment_id=row.id, reviewer_id="ana")


def test_comparison_is_refused_until_the_second_reading_exists(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory)
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()

    # Comparar antes de emitir revelaría la primera lectura por otra vía.
    with pytest.raises(SecondReviewError, match="hasta que la segunda se emita"):
        comparison_for(session, row.id)


def test_two_equal_readings_produce_agreement(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory)
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()
    claim_second_review(session, assignment_id=row.id, reviewer_id="luis")
    session.commit()

    result = submit_second_review(
        session,
        assignment_id=row.id,
        decision=ValidationDecision(
            field_name="DESCRIPCION",
            state="confirmado",
            final_value="ácido nicotínico",
            reviewer_id="luis",
            reviewer_role="farmaceutico",
        ),
        directory=directory,
    )
    assert result.state == "acuerdo"
    # Sólo ahora deja de estar oculta: ya no puede influir en la lectura.
    assert result.revealed is True
    assert comparison_for(session, row.id).is_agreement


def test_same_state_with_different_value_is_a_disagreement(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory, value="2,5 mg")
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()

    result = submit_second_review(
        session,
        assignment_id=row.id,
        decision=ValidationDecision(
            field_name="DESCRIPCION",
            state="confirmado",
            final_value="2,5 mg/comprimido",
            reviewer_id="luis",
            reviewer_role="farmaceutico",
        ),
        directory=directory,
    )
    # Dos personas que confirman cosas distintas no han confirmado lo mismo.
    assert result.state == "desacuerdo"
    assert comparison_for(session, row.id).kind == "discrepancia_valor"


def test_reconciling_preserves_both_original_decisions(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory, value="2,5 mg")
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()
    submit_second_review(
        session,
        assignment_id=row.id,
        decision=ValidationDecision(
            field_name="DESCRIPCION",
            state="confirmado",
            final_value="2,5 mg/comprimido",
            reviewer_id="luis",
            reviewer_role="farmaceutico",
        ),
        directory=directory,
    )

    stored = reconcile(
        session,
        assignment_id=row.id,
        reconciliation=Reconciliation(
            field_name="DESCRIPCION",
            choice="valor_nuevo",
            resolved_by="eva",
            comment="La ficha técnica declara 2,5 mg por comprimido.",
            final_value="2,5 mg por comprimido",
        ),
        directory=directory,
    )

    assert stored.reconciler_id == "eva"
    assert stored.resulting_sequence == 3
    session.refresh(row)
    assert row.state == "conciliado"

    # Las dos lecturas enfrentadas siguen intactas en el historial.
    history = session.scalars(
        select(ValidationDecisionRecord)
        .where(ValidationDecisionRecord.field_value_id == FIELD)
        .order_by(ValidationDecisionRecord.sequence)
    ).all()
    assert [item.sequence for item in history] == [1, 2, 3]
    assert history[0].final_value == "2,5 mg"
    assert history[0].reviewer_id == "ana"
    assert history[1].final_value == "2,5 mg/comprimido"
    assert history[1].reviewer_id == "luis"
    # Y la conciliación es una decisión más, no una corrección de las otras.
    assert history[2].final_value == "2,5 mg por comprimido"
    assert history[2].reviewer_id == "eva"


def test_reconciling_requires_a_justification() -> None:
    # La barrera vive en el módulo puro y no se relaja al persistir.
    with pytest.raises(DoubleReviewError, match="justificacion"):
        Reconciliation(
            field_name="DESCRIPCION",
            choice="revisor_a",
            resolved_by="eva",
            comment="   ",
        )


def test_an_agreement_cannot_be_reconciled(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory)
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()
    submit_second_review(
        session,
        assignment_id=row.id,
        decision=ValidationDecision(
            field_name="DESCRIPCION",
            state="confirmado",
            final_value="ácido nicotínico",
            reviewer_id="luis",
            reviewer_role="farmaceutico",
        ),
        directory=directory,
    )

    # Conciliar un acuerdo permitiría reescribirlo sin constancia de que dos
    # lecturas coincidieron.
    with pytest.raises(DoubleReviewError, match="no presenta discrepancia"):
        reconcile(
            session,
            assignment_id=row.id,
            reconciliation=Reconciliation(
                field_name="DESCRIPCION",
                choice="revisor_a",
                resolved_by="eva",
                comment="Cambio de criterio.",
            ),
            directory=directory,
        )


def test_a_discrepancy_is_reconciled_only_once(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory, value="2,5 mg")
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()
    submit_second_review(
        session,
        assignment_id=row.id,
        decision=ValidationDecision(
            field_name="DESCRIPCION",
            state="confirmado",
            final_value="otro valor",
            reviewer_id="luis",
            reviewer_role="farmaceutico",
        ),
        directory=directory,
    )

    payload = Reconciliation(
        field_name="DESCRIPCION",
        choice="revisor_a",
        resolved_by="eva",
        comment="Coincide con la fuente.",
    )
    reconcile(session, assignment_id=row.id, reconciliation=payload, directory=directory)

    with pytest.raises(SecondReviewError, match="ya se concilió"):
        reconcile(
            session, assignment_id=row.id, reconciliation=payload, directory=directory
        )
    # Una sola conciliación registrada, no dos.
    assert len(session.scalars(select(ReconciliationRecord)).all()) == 1


def test_a_stale_version_is_refused(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory)
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()
    observed = row.version
    claim_second_review(session, assignment_id=row.id, reviewer_id="luis")
    session.commit()

    # Otro cliente que vio la versión anterior no puede escribir encima.
    with pytest.raises(SecondReviewConflict, match="ha cambiado"):
        submit_second_review(
            session,
            assignment_id=row.id,
            decision=ValidationDecision(
                field_name="DESCRIPCION",
                state="confirmado",
                final_value="x",
                reviewer_id="eva",
                reviewer_role="farmaceutico",
            ),
            directory=directory,
            expected_version=observed,
        )


def test_a_claimed_review_cannot_be_claimed_again(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory)
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()
    claim_second_review(session, assignment_id=row.id, reviewer_id="luis")
    session.commit()

    with pytest.raises(SecondReviewConflict, match="ya no está disponible"):
        claim_second_review(session, assignment_id=row.id, reviewer_id="eva")


def test_pending_list_hides_your_own_first_readings(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory)
    open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()

    # Ana firmó la primera: no debe verla ofrecida como segunda revisión.
    assert pending_second_reviews(session, reviewer_id="ana") == []
    assert len(pending_second_reviews(session, reviewer_id="luis")) == 1


def test_disagreements_are_listed_for_reconciliation(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory, value="2,5 mg")
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()
    assert disagreements(session) == []

    submit_second_review(
        session,
        assignment_id=row.id,
        decision=ValidationDecision(
            field_name="DESCRIPCION",
            state="confirmado",
            final_value="distinto",
            reviewer_id="luis",
            reviewer_role="farmaceutico",
        ),
        directory=directory,
    )
    assert [item.id for item in disagreements(session)] == [row.id]


def test_a_field_opens_only_one_second_review(
    session: Session, directory: ReviewerDirectory
) -> None:
    first_decision(session, directory)
    open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()

    with pytest.raises(SecondReviewError, match="ya tiene una segunda revisión"):
        open_second_review(session, field_value_id=FIELD, actor_id="ana")


def test_the_flow_is_recorded_in_the_audit_journal(
    session: Session, directory: ReviewerDirectory
) -> None:
    from pharma_validator_api.audit_store import events_for

    first_decision(session, directory, value="2,5 mg")
    row = open_second_review(session, field_value_id=FIELD, actor_id="ana")
    session.commit()
    claim_second_review(session, assignment_id=row.id, reviewer_id="luis")
    session.commit()
    submit_second_review(
        session,
        assignment_id=row.id,
        decision=ValidationDecision(
            field_name="DESCRIPCION",
            state="confirmado",
            final_value="distinto",
            reviewer_id="luis",
            reviewer_role="farmaceutico",
        ),
        directory=directory,
    )
    reconcile(
        session,
        assignment_id=row.id,
        reconciliation=Reconciliation(
            field_name="DESCRIPCION",
            choice="revisor_a",
            resolved_by="eva",
            comment="La fuente respalda la primera lectura.",
        ),
        directory=directory,
    )

    actions = [item.action for item in events_for(session, entity_id=FIELD)]
    assert actions == [
        "segunda_revision_abierta",
        "segunda_revision_reclamada",
        "segunda_revision_emitida",
        "conciliacion",
    ]
