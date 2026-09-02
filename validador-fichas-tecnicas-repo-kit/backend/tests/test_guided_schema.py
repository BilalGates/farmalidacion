from typing import Any

import pytest

from pharma_validator_api.extractor import FieldRequest
from pharma_validator_api.guided_schema import (
    SCHEMA_VERSION,
    GuidedSchemaError,
    build_schema,
    constraint_for,
    parse_response,
    validate_value_against_type,
)

POSOLOGIA = FieldRequest("POSOLOGIA", "Dosis", "CHAR(100)", "proponer_valor")
DOSIS = FieldRequest("ADUDOMAXDIA", "Dosis máxima", "DECIMAL(10,3)", "proponer_valor")
FLAG = FieldRequest("ES_HUERFANO", "Huérfano", "BIT", "proponer_valor")


def entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "campo": "POSOLOGIA",
        "estado": "encontrado",
        "valor": "20 mg",
        "opciones": None,
        "evidencia_texto": "La dosis recomendada es de 20 mg",
        "evidencia_ini": 10,
        "evidencia_fin": 42,
        "confianza": 0.9,
    }
    base.update(overrides)
    return base


def test_schema_is_closed_and_requires_every_result_field() -> None:
    schema = build_schema((POSOLOGIA,))
    assert schema["title"] == SCHEMA_VERSION
    assert schema["additionalProperties"] is False
    item = schema["properties"]["resultados"]["items"]
    assert item["additionalProperties"] is False
    assert "evidencia_texto" in item["required"]
    assert item["properties"]["campo"]["enum"] == ["POSOLOGIA"]


def test_schema_pins_the_result_count_to_the_requested_fields() -> None:
    schema = build_schema((POSOLOGIA, DOSIS))
    results = schema["properties"]["resultados"]
    assert results["minItems"] == 2
    assert results["maxItems"] == 2


def test_schema_bounds_evidence_length_as_the_specification_requires() -> None:
    properties = build_schema((POSOLOGIA,))["properties"]["resultados"]["items"]["properties"]
    assert properties["evidencia_texto"]["minLength"] == 10
    assert properties["evidencia_texto"]["maxLength"] == 400


def test_schema_rejects_duplicate_or_empty_field_lists() -> None:
    with pytest.raises(ValueError):
        build_schema(())
    with pytest.raises(ValueError):
        build_schema((POSOLOGIA, POSOLOGIA))


def test_char_type_is_never_truncated() -> None:
    constraint = constraint_for("CHAR(10)")
    validate_value_against_type("0123456789", constraint)
    with pytest.raises(GuidedSchemaError, match="no se trunca"):
        validate_value_against_type("01234567890", constraint)


def test_decimal_scale_is_never_rounded() -> None:
    constraint = constraint_for("DECIMAL(10,3)")
    validate_value_against_type("12.345", constraint)
    with pytest.raises(GuidedSchemaError, match="no se redondea"):
        validate_value_against_type("12.3456", constraint)


def test_decimal_precision_is_enforced() -> None:
    with pytest.raises(GuidedSchemaError, match="precisión"):
        validate_value_against_type("12345678901.0", constraint_for("DECIMAL(10,3)"))


def test_bit_type_admits_only_zero_or_one() -> None:
    validate_value_against_type("1", constraint_for("BIT"))
    with pytest.raises(GuidedSchemaError):
        validate_value_against_type("sí", constraint_for("BIT"))


def test_unknown_type_is_not_relaxed_to_free_text() -> None:
    constraint = constraint_for("GEOGRAPHY")
    assert constraint.max_length is None
    assert constraint.is_boolean is False


def test_parse_response_builds_a_proposal_with_the_requested_section() -> None:
    proposals = parse_response({"resultados": [entry()]}, (POSOLOGIA,), "4.2")
    assert len(proposals) == 1
    assert proposals[0].evidence_section == "4.2"
    assert proposals[0].proposed_value == "20 mg"


def test_section_comes_from_the_request_not_from_the_model() -> None:
    proposals = parse_response(
        {"resultados": [entry(seccion="9.9")]}, (POSOLOGIA,), "4.2"
    )
    assert proposals[0].evidence_section == "4.2"


def test_absent_evidence_leaves_the_section_unset() -> None:
    proposals = parse_response(
        {
            "resultados": [
                entry(
                    estado="no_encontrado",
                    valor=None,
                    evidencia_texto=None,
                    evidencia_ini=None,
                    evidencia_fin=None,
                )
            ]
        },
        (POSOLOGIA,),
        "4.2",
    )
    assert proposals[0].evidence_section is None


def test_missing_result_is_an_error_not_a_silent_gap() -> None:
    with pytest.raises(GuidedSchemaError, match="ADUDOMAXDIA"):
        parse_response({"resultados": [entry()]}, (POSOLOGIA, DOSIS), "4.2")


def test_unknown_field_in_response_is_rejected() -> None:
    with pytest.raises(GuidedSchemaError, match="desconocido"):
        parse_response({"resultados": [entry(campo="OTRO")]}, (POSOLOGIA,), "4.2")


def test_duplicate_field_in_response_is_rejected() -> None:
    with pytest.raises(GuidedSchemaError, match="más de una vez"):
        parse_response({"resultados": [entry(), entry()]}, (POSOLOGIA,), "4.2")


def test_invalid_state_is_rejected() -> None:
    with pytest.raises(GuidedSchemaError, match="Estado"):
        parse_response({"resultados": [entry(estado="quizas")]}, (POSOLOGIA,), "4.2")


def test_response_without_results_is_rejected() -> None:
    with pytest.raises(GuidedSchemaError, match="resultados"):
        parse_response({}, (POSOLOGIA,), "4.2")


def test_value_exceeding_the_declared_type_is_rejected_on_parse() -> None:
    with pytest.raises(GuidedSchemaError, match="no se trunca"):
        parse_response({"resultados": [entry(valor="x" * 101)]}, (POSOLOGIA,), "4.2")


def test_boolean_offsets_are_not_accepted_as_integers() -> None:
    with pytest.raises(GuidedSchemaError, match="desplazamientos"):
        parse_response({"resultados": [entry(evidencia_ini=True)]}, (POSOLOGIA,), "4.2")


def test_bit_field_value_is_validated_through_parse() -> None:
    payload = {
        "resultados": [
            entry(campo="ES_HUERFANO", valor="2", evidencia_texto="medicamento huerfano")
        ]
    }
    with pytest.raises(GuidedSchemaError, match="BIT"):
        parse_response(payload, (FLAG,), "4.2")


def test_parse_requires_an_explicit_section() -> None:
    with pytest.raises(ValueError):
        parse_response({"resultados": [entry()]}, (POSOLOGIA,), "")


def test_parse_is_deterministic_and_ordered_by_field() -> None:
    payload = {
        "resultados": [
            entry(campo="POSOLOGIA"),
            entry(campo="ADUDOMAXDIA", valor="10.5", evidencia_texto="dosis maxima diaria"),
        ]
    }
    first = parse_response(payload, (POSOLOGIA, DOSIS), "4.2")
    second = parse_response(payload, (POSOLOGIA, DOSIS), "4.2")
    assert first == second
    assert [item.field_name for item in first] == ["ADUDOMAXDIA", "POSOLOGIA"]
