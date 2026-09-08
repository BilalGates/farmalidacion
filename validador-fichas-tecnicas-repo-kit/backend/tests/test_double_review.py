"""Doble validacion: comparacion y conciliacion (DEV-510).

Los revisores de estas pruebas son ficticios y estan marcados como tales. No
representan farmaceuticos reales ni sustituyen a GOLD-002.
"""

import pytest

from pharma_validator_api.double_review import (
    DoubleReviewError,
    Reconciliation,
    ReviewerDecision,
    compare_field,
    compare_reviews,
    resolve,
)

A = "test_reviewer_a"
B = "test_reviewer_b"


def decision(reviewer: str, state: str = "confirmado", value: str | None = "10 mg"):
    return ReviewerDecision(reviewer_id=reviewer, state=state, final_value=value)  # type: ignore[arg-type]


def test_identical_decisions_agree() -> None:
    result = compare_field("DOSIS", decision(A), decision(B))
    assert result.kind == "acuerdo"
    assert result.is_agreement


def test_same_state_with_different_values_is_a_disagreement() -> None:
    """Dos personas que confirman cosas distintas no han confirmado lo mismo."""
    result = compare_field("DOSIS", decision(A, value="10 mg"), decision(B, value="20 mg"))
    assert result.kind == "discrepancia_valor"
    assert result.is_disagreement


def test_different_states_are_a_disagreement() -> None:
    result = compare_field("DOSIS", decision(A, "confirmado"), decision(B, "no_consta", None))
    assert result.kind == "discrepancia_estado"


def test_a_single_review_is_not_agreement() -> None:
    """Confundir incompleto con acuerdo daria por validado lo que vio una persona."""
    result = compare_field("DOSIS", decision(A), None)
    assert result.kind == "pendiente_segunda_revision"
    assert not result.is_agreement
    assert not result.is_disagreement


def test_nobody_reviewed_yet() -> None:
    assert compare_field("DOSIS", None, None).kind == "pendiente_primera_revision"


def test_a_reviewer_cannot_double_validate_alone() -> None:
    """La independencia es el requisito; el mismo revisor dos veces no la cumple."""
    with pytest.raises(DoubleReviewError):
        compare_field("DOSIS", decision(A), decision(A))


def test_a_summary_separates_agreement_disagreement_and_pending() -> None:
    summary = compare_reviews(
        {
            "CN": decision(A, value="707703"),
            "DOSIS": decision(A, value="10 mg"),
            "VIA": decision(A, value="oral"),
        },
        {
            "CN": decision(B, value="707703"),
            "DOSIS": decision(B, value="20 mg"),
        },
    )
    assert summary.agreement_count == 1
    assert len(summary.disagreements) == 1
    assert len(summary.pending) == 1
    assert not summary.is_complete
    assert not summary.is_reconciled


def test_agreement_rate_ignores_fields_only_one_person_saw() -> None:
    summary = compare_reviews(
        {"CN": decision(A, value="1"), "DOSIS": decision(A, value="10 mg")},
        {"CN": decision(B, value="1")},
    )
    # Un solo campo comparable, y coincide.
    assert summary.agreement_rate() == 1.0


def test_no_comparable_field_yields_no_invented_rate() -> None:
    summary = compare_reviews({"CN": decision(A)}, {})
    assert summary.agreement_rate() is None


def test_a_disagreement_is_never_resolved_automatically() -> None:
    """El nucleo del modulo: nadie gana por antiguedad, rol ni orden de llegada."""
    summary = compare_reviews(
        {"DOSIS": decision(A, value="10 mg")}, {"DOSIS": decision(B, value="20 mg")}
    )
    assert not summary.is_reconciled
    assert summary.disagreements[0].kind == "discrepancia_valor"


def test_reconciling_requires_a_justification() -> None:
    """Sin justificacion no queda constancia de por que se descarto una lectura."""
    with pytest.raises(DoubleReviewError):
        Reconciliation(field_name="DOSIS", choice="revisor_a", resolved_by="jefe", comment="  ")


def test_a_new_value_must_be_supplied() -> None:
    with pytest.raises(DoubleReviewError):
        Reconciliation(
            field_name="DOSIS", choice="valor_nuevo", resolved_by="jefe", comment="ok"
        )


def test_resolving_keeps_the_chosen_reading_and_the_new_author() -> None:
    comparison = compare_field(
        "DOSIS", decision(A, value="10 mg"), decision(B, value="20 mg")
    )
    resolved = resolve(
        comparison,
        Reconciliation(
            field_name="DOSIS",
            choice="revisor_b",
            resolved_by="test_conciliador",
            comment="Coincide con la ficha tecnica.",
        ),
    )
    assert resolved.final_value == "20 mg"
    assert resolved.reviewer_id == "test_conciliador"


def test_resolving_with_a_third_value_marks_it_corrected() -> None:
    comparison = compare_field(
        "DOSIS", decision(A, value="10 mg"), decision(B, value="20 mg")
    )
    resolved = resolve(
        comparison,
        Reconciliation(
            field_name="DOSIS",
            choice="valor_nuevo",
            resolved_by="test_conciliador",
            comment="Ninguna de las dos.",
            final_value="15 mg",
        ),
    )
    assert (resolved.state, resolved.final_value) == ("corregido", "15 mg")


def test_an_agreement_cannot_be_reconciled_away() -> None:
    """Reescribir un acuerdo borraria que dos lecturas coincidieron."""
    comparison = compare_field("DOSIS", decision(A), decision(B))
    with pytest.raises(DoubleReviewError):
        resolve(
            comparison,
            Reconciliation(
                field_name="DOSIS",
                choice="revisor_a",
                resolved_by="jefe",
                comment="por que si",
            ),
        )


def test_a_reconciliation_must_match_its_field() -> None:
    comparison = compare_field("DOSIS", decision(A, value="1"), decision(B, value="2"))
    with pytest.raises(DoubleReviewError):
        resolve(
            comparison,
            Reconciliation(
                field_name="OTRO", choice="revisor_a", resolved_by="jefe", comment="x"
            ),
        )
