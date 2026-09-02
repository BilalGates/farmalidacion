import pytest

from pharma_validator_api.validation_states import (
    ValidationDecision,
    ValidationStateError,
    assert_transition_allowed,
    evaluate_review_completeness,
    is_resolved,
    mark_pending_review,
    validate_decision,
)


def decision(**overrides: object) -> ValidationDecision:
    base: dict[str, object] = {
        "field_name": "ATC",
        "state": "confirmado",
        "final_value": "A02BC01",
        "reviewer_id": "mtorres",
        "reviewer_role": "farmaceutico",
    }
    base.update(overrides)
    return ValidationDecision(**base)  # type: ignore[arg-type]


def test_internal_resolution_is_not_provider_serialization() -> None:
    for state in ("confirmado", "corregido", "no_consta", "no_aplica"):
        assert is_resolved(state) is True  # type: ignore[arg-type]
    for state in ("pendiente", "descartado", "revision_pendiente"):
        assert is_resolved(state) is False  # type: ignore[arg-type]


def test_value_states_require_or_reject_final_value() -> None:
    validate_decision(decision(state="confirmado", final_value="A02BC01"))
    with pytest.raises(ValidationStateError, match="exige un valor final"):
        validate_decision(decision(state="corregido", final_value=None))
    with pytest.raises(ValidationStateError, match="no admite valor final"):
        validate_decision(decision(state="no_consta", final_value="20"))


def test_no_consta_requires_all_configured_required_sources() -> None:
    incomplete = decision(
        state="no_consta",
        final_value=None,
        applicable_sources=("master", "cima", "ft"),
        required_sources=("master", "ft"),
        reviewed_sources=("master",),
    )
    with pytest.raises(ValidationStateError, match="fuentes obligatorias.*ft"):
        validate_decision(incomplete)
    validate_decision(
        decision(
            state="no_consta",
            final_value=None,
            applicable_sources=("master", "cima", "ft"),
            required_sources=("master", "ft"),
            reviewed_sources=("master", "ft"),
        )
    )


def test_sources_must_be_unique_and_applicable() -> None:
    with pytest.raises(ValueError, match="duplicados"):
        decision(applicable_sources=("ft", "ft"))
    with pytest.raises(ValueError, match="obligatoria debe ser aplicable"):
        decision(applicable_sources=("ft",), required_sources=("cima",))
    with pytest.raises(ValueError, match="no aplicable"):
        decision(applicable_sources=("ft",), reviewed_sources=("cima",))


def test_no_consta_authority_and_conditional_comment() -> None:
    with pytest.raises(ValidationStateError, match="farmacéutico"):
        validate_decision(decision(state="no_consta", final_value=None, reviewer_role="otro"))
    validate_decision(decision(state="no_consta", final_value=None, comment=None))
    with pytest.raises(ValidationStateError, match="campo obligatorio"):
        validate_decision(
            decision(
                state="no_consta",
                final_value=None,
                field_required=True,
                comment=" ",
            )
        )


def test_no_aplica_requires_pharmacist_and_comment() -> None:
    with pytest.raises(ValidationStateError, match="farmacéutico"):
        validate_decision(
            decision(
                state="no_aplica",
                final_value=None,
                reviewer_role="otro",
                comment="No corresponde.",
            )
        )
    with pytest.raises(ValidationStateError, match="exige comentario"):
        validate_decision(decision(state="no_aplica", final_value=None))
    validate_decision(decision(state="no_aplica", final_value=None, comment="No corresponde."))


def test_pending_carries_neither_value_nor_comment() -> None:
    validate_decision(decision(state="pendiente", final_value=None))
    with pytest.raises(ValidationStateError, match="no registra comentario"):
        validate_decision(decision(state="pendiente", final_value=None, comment="algo"))


def test_identity_and_time_are_validated() -> None:
    with pytest.raises(ValueError, match="revisor"):
        decision(reviewer_id="")
    with pytest.raises(ValueError, match="negativo"):
        decision(seconds_spent=-1)


def test_resolved_decision_never_returns_to_pending() -> None:
    with pytest.raises(ValidationStateError, match="no vuelve a pendiente"):
        assert_transition_allowed("confirmado", "pendiente")


@pytest.mark.parametrize("state", ["no_consta", "no_aplica"])
def test_reverting_special_state_requires_comment(state: str) -> None:
    with pytest.raises(ValidationStateError, match="Revertir"):
        assert_transition_allowed(state, "confirmado")  # type: ignore[arg-type]
    assert_transition_allowed(state, "confirmado", comment="Decisión revisada.")  # type: ignore[arg-type]


def test_leaving_pending_review_requires_comment() -> None:
    with pytest.raises(ValidationStateError, match="exige comentario"):
        assert_transition_allowed("revision_pendiente", "confirmado")
    assert_transition_allowed("revision_pendiente", "confirmado", comment="Nueva versión revisada.")


def test_version_change_marks_but_does_not_erase() -> None:
    assert mark_pending_review("confirmado") == "revision_pendiente"
    assert mark_pending_review("no_aplica") == "revision_pendiente"
    assert mark_pending_review("pendiente") == "pendiente"


def test_review_completeness_withholds_unresolved_and_double_validation() -> None:
    result = evaluate_review_completeness(
        (
            decision(field_name="ATC", state="confirmado", final_value="A02BC01"),
            decision(field_name="FORMA", state="pendiente", final_value=None),
            decision(
                field_name="ADUDOMAXDIA",
                state="no_consta",
                final_value=None,
            ),
        ),
        unresolved_double_validation=("ATC",),
    )
    assert result.resolved == ("ADUDOMAXDIA",)
    assert result.withheld == (("ATC", "confirmado"), ("FORMA", "pendiente"))
    assert result.is_record_complete is False


def test_review_completeness_accepts_internal_no_aplica() -> None:
    result = evaluate_review_completeness(
        (
            decision(
                field_name="BLOQUE",
                state="no_aplica",
                final_value=None,
                comment="No corresponde.",
            ),
        )
    )
    assert result.is_record_complete is True
    assert result.resolved == ("BLOQUE",)
