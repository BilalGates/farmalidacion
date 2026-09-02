import pytest

from pharma_validator_api.provenance_conflicts import (
    FieldIdentity,
    FieldPriorityRule,
    SourceAssertion,
    evaluate_conflict,
)

FIELD = FieldIdentity(42, "medicamento", "Medicamento - General", "DESCRIPCION")


def assertion(
    assertion_id: str,
    value: str | None,
    source_role: str = "master_baseline",
    logical_state: str = "valued",
) -> SourceAssertion:
    return SourceAssertion(
        assertion_id=assertion_id,
        literal_value=value,
        logical_state=logical_state,  # type: ignore[arg-type]
        source_role=source_role,  # type: ignore[arg-type]
        source_version_id=f"version-{assertion_id}",
        source_locator=f"source!{assertion_id}",
    )


def test_equal_literal_claims_keep_both_provenances_without_selecting_one() -> None:
    result = evaluate_conflict(
        FIELD,
        (
            assertion("master", "Omeprazol"),
            assertion("cima", "Omeprazol", "cima_structured"),
        ),
    )
    assert result.status == "consistent_pending_priority"
    assert result.has_conflict is False
    assert [item.assertion_id for item in result.assertions] == ["cima", "master"]
    assert result.selected_assertion_ids == ()
    assert len(result.assertions) == 2


def test_no_assertions_is_explicit_and_not_a_conflict() -> None:
    result = evaluate_conflict(FIELD, ())
    assert result.status == "no_assertions"
    assert result.has_conflict is False
    assert result.distinct_claims == ()


def test_whitespace_and_case_are_not_normalized_and_pending_rule_selects_nothing() -> None:
    result = evaluate_conflict(
        FIELD,
        (
            assertion("master", "Omeprazol"),
            assertion("ft", " omeprazol ", "technical_sheet"),
        ),
        FieldPriorityRule(FIELD, "pending_human_validation"),
    )
    assert result.status == "unresolved_pending_priority"
    assert result.has_conflict is True
    assert result.selected_assertion_ids == ()
    assert {claim[1] for claim in result.distinct_claims} == {
        "Omeprazol",
        " omeprazol ",
    }


def test_logical_states_are_part_of_exact_claim_semantics() -> None:
    result = evaluate_conflict(
        FIELD,
        (
            assertion("not-known", None, logical_state="no_consta"),
            assertion("not-applicable", None, logical_state="no_aplica"),
        ),
    )
    assert result.has_conflict is True
    assert result.status == "unresolved_pending_priority"


def test_accepted_exact_rule_selects_highest_source_and_preserves_all_claims() -> None:
    rule = FieldPriorityRule(
        FIELD,
        "accepted",
        ("cima_structured", "master_baseline"),
        "DECISION-FIELD-042",
    )
    result = evaluate_conflict(
        FIELD,
        (
            assertion("master", "valor maestro"),
            assertion("cima", "valor CIMA", "cima_structured"),
        ),
        rule,
    )
    assert result.status == "resolved_by_accepted_priority"
    assert result.selected_assertion_ids == ("cima",)
    assert result.selected_claim == ("valued", "valor CIMA")
    assert result.applied_decision_reference == "DECISION-FIELD-042"
    assert len(result.assertions) == 2


def test_human_only_rule_never_selects_a_claim() -> None:
    rule = FieldPriorityRule(
        FIELD,
        "accepted",
        ("pharmacist_decision", "master_baseline"),
        "DECISION-INTERPRETABLE-042",
        automatic_resolution_allowed=False,
    )
    result = evaluate_conflict(
        FIELD,
        (
            assertion("master", "A"),
            assertion("ft", "B", "technical_sheet"),
        ),
        rule,
    )
    assert result.status == "human_action_required"
    assert result.selected_assertion_ids == ()


def test_accepted_rule_without_an_applicable_source_remains_unresolved() -> None:
    rule = FieldPriorityRule(
        FIELD,
        "accepted",
        ("pharmacist_decision",),
        "DECISION-PHARMACIST-042",
    )
    result = evaluate_conflict(
        FIELD,
        (
            assertion("master", "A"),
            assertion("cima", "B", "cima_structured"),
        ),
        rule,
    )
    assert result.status == "unresolved_no_applicable_source"
    assert result.selected_assertion_ids == ()


def test_conflicting_claims_inside_highest_source_remain_unresolved() -> None:
    rule = FieldPriorityRule(
        FIELD,
        "accepted",
        ("cima_structured", "master_baseline"),
        "DECISION-FIELD-042",
    )
    result = evaluate_conflict(
        FIELD,
        (
            assertion("cima-a", "A", "cima_structured"),
            assertion("cima-b", "B", "cima_structured"),
            assertion("master", "C"),
        ),
        rule,
    )
    assert result.status == "unresolved_authoritative_ambiguity"
    assert result.selected_assertion_ids == ()


def test_rule_requires_exact_field_and_accepted_decision_reference() -> None:
    other_field = FieldIdentity(43, "medicamento", "Medicamento - General", "NOMBRE")
    with pytest.raises(ValueError, match="decisión"):
        FieldPriorityRule(FIELD, "accepted", ("master_baseline",))
    with pytest.raises(ValueError, match="campo evaluado"):
        evaluate_conflict(
            FIELD,
            (assertion("master", "A"), assertion("cima", "B", "cima_structured")),
            FieldPriorityRule(
                other_field,
                "accepted",
                ("master_baseline",),
                "DECISION-OTHER-043",
            ),
        )


def test_assertions_require_verifiable_provenance_and_unique_ids() -> None:
    with pytest.raises(ValueError, match="versión"):
        SourceAssertion("a", "A", "valued", "master_baseline", "", "General!2")
    duplicate = assertion("same", "A")
    with pytest.raises(ValueError, match="único"):
        evaluate_conflict(FIELD, (duplicate, duplicate))
