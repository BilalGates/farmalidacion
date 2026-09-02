import pytest

from pharma_validator_api.prefill_policy import (
    CLINICAL_JUDGEMENT_WARNING,
    EvidenceCitation,
    PrefillPolicyError,
    assert_bulk_confirmation_allowed,
    assert_no_protected_preselection,
    plan_field_presentation,
    select_bulk_confirmable,
)

EVIDENCE = EvidenceCitation(
    "4.2", "La dosis recomendada es de 20 mg una vez al día", 10, 55
)


def test_direct_field_arrives_prefilled_with_its_evidence() -> None:
    plan = plan_field_presentation("ATC", "proponer_valor", "A02BC01", evidence=EVIDENCE)
    assert plan.presentation == "valor_precargado"
    assert plan.prefilled_value == "A02BC01"
    assert plan.evidence is not None
    assert plan.is_protected is False


def test_interpretation_field_offers_options_with_none_preselected() -> None:
    plan = plan_field_presentation(
        "FRECUENCIA",
        "proponer_opciones",
        options=("cada 8 horas", "cada 12 horas"),
        evidence=EVIDENCE,
    )
    assert plan.presentation == "opciones_sin_marcar"
    assert plan.prefilled_value is None
    assert plan.options == ("cada 8 horas", "cada 12 horas")


def test_clinical_field_leaves_the_box_empty_with_a_warning() -> None:
    """Ejemplo canónico de 9.2: el techo de alerta no está en la ficha."""
    plan = plan_field_presentation("ADUDOMAXDIA", "solo_evidencia", evidence=EVIDENCE)
    assert plan.presentation == "casilla_vacia"
    assert plan.prefilled_value is None
    assert plan.options == ()
    assert plan.warning == CLINICAL_JUDGEMENT_WARNING
    # La evidencia sí se muestra: es lo que permite juzgar sin decidir por nadie.
    assert plan.evidence is not None


def test_hidden_field_does_not_appear_on_this_screen() -> None:
    plan = plan_field_presentation("INTERNO", "oculto", "valor")
    assert plan.presentation == "no_visible"
    assert plan.prefilled_value is None


def test_a_value_passed_for_a_protected_field_is_discarded_not_shown() -> None:
    """La política es una regla, no una recomendación."""
    for policy in ("proponer_opciones", "solo_evidencia"):
        plan = plan_field_presentation(
            "ADUDOMAXDIA", policy, "40", evidence=EVIDENCE  # type: ignore[arg-type]
        )
        assert plan.prefilled_value is None
        assert plan.presentation != "valor_precargado"


def test_protected_fields_are_reported_as_protected() -> None:
    for policy in ("proponer_opciones", "solo_evidencia"):
        plan = plan_field_presentation("X", policy)  # type: ignore[arg-type]
        assert plan.is_protected is True
    for policy in ("proponer_valor", "oculto"):
        plan = plan_field_presentation("X", policy)  # type: ignore[arg-type]
        assert plan.is_protected is False


def test_screen_wide_check_passes_when_policies_are_respected() -> None:
    plans = (
        plan_field_presentation("ATC", "proponer_valor", "A02BC01", evidence=EVIDENCE),
        plan_field_presentation("ADUDOMAXDIA", "solo_evidencia", evidence=EVIDENCE),
        plan_field_presentation(
            "FRECUENCIA", "proponer_opciones", options=("a", "b"), evidence=EVIDENCE
        ),
    )
    assert_no_protected_preselection(plans)


def test_screen_wide_check_catches_a_hand_built_violation() -> None:
    """Un plan construido a mano no puede saltarse la comprobación."""
    honest = plan_field_presentation("ADUDOMAXDIA", "solo_evidencia", evidence=EVIDENCE)
    tampered = type(honest)(
        honest.field_name,
        honest.policy,
        "valor_precargado",
        "40",
        (),
        honest.evidence,
        honest.warning,
    )
    with pytest.raises(PrefillPolicyError, match="ADUDOMAXDIA"):
        assert_no_protected_preselection((tampered,))


def test_only_direct_fields_with_evidence_admit_bulk_confirmation() -> None:
    with_evidence = plan_field_presentation(
        "ATC", "proponer_valor", "A02BC01", evidence=EVIDENCE
    )
    without_evidence = plan_field_presentation("NOMBRE", "proponer_valor", "Omeprazol")
    protected = plan_field_presentation("ADUDOMAXDIA", "solo_evidencia", evidence=EVIDENCE)

    assert with_evidence.can_be_bulk_confirmed is True
    assert without_evidence.can_be_bulk_confirmed is False
    assert protected.can_be_bulk_confirmed is False

    selected = select_bulk_confirmable((with_evidence, without_evidence, protected))
    assert [item.field_name for item in selected] == ["ATC"]


def test_bulk_confirmation_is_refused_without_visible_evidence() -> None:
    plan = plan_field_presentation("ATC", "proponer_valor", "A02BC01", evidence=EVIDENCE)
    with pytest.raises(PrefillPolicyError, match="evidencia visible"):
        assert_bulk_confirmation_allowed((plan,), evidence_visible=False)


def test_bulk_confirmation_is_refused_for_protected_fields() -> None:
    protected = plan_field_presentation(
        "FRECUENCIA", "proponer_opciones", options=("a",), evidence=EVIDENCE
    )
    with pytest.raises(PrefillPolicyError, match="no admite confirmación en bloque"):
        assert_bulk_confirmation_allowed((protected,), evidence_visible=True)


def test_bulk_confirmation_is_allowed_for_direct_fields_with_evidence() -> None:
    plan = plan_field_presentation("ATC", "proponer_valor", "A02BC01", evidence=EVIDENCE)
    assert_bulk_confirmation_allowed((plan,), evidence_visible=True)


def test_planning_is_deterministic() -> None:
    first = plan_field_presentation("ATC", "proponer_valor", "A02BC01", evidence=EVIDENCE)
    second = plan_field_presentation("ATC", "proponer_valor", "A02BC01", evidence=EVIDENCE)
    assert first == second
