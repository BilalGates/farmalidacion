import pytest

from pharma_validator_api.evidence_verification import DocumentSection
from pharma_validator_api.section_grouping import (
    CatalogField,
    group_fields_by_section,
    parse_sections,
)

SECTIONS = tuple(
    DocumentSection("version-1", section, f"<p>Texto del apartado {section}.</p>")
    for section in ("1", "2", "4.2", "5.1", "5.2", "6.6")
)


def field(
    name: str,
    literal: str | None = "4.2",
    policy: str = "proponer_valor",
) -> CatalogField:
    return CatalogField(name, f"Descripción de {name}", "CHAR(100)", policy, literal)  # type: ignore[arg-type]


def group(*fields: CatalogField):
    return group_fields_by_section(fields, SECTIONS, "version-1", "Omeprazol 20 mg")


def test_single_section_literal_is_parsed() -> None:
    assert parse_sections("4.2") == ("4.2",)


def test_multiple_sections_are_split_on_the_catalog_separator() -> None:
    # Literales reales del catálogo importado en DEV-302.
    assert parse_sections("4.2 / 6.6") == ("4.2", "6.6")
    assert parse_sections("1 / 2") == ("1", "2")


def test_section_order_in_the_literal_is_not_significant() -> None:
    assert parse_sections("6.6 / 4.2") == parse_sections("4.2 / 6.6")


def test_absence_markers_yield_no_sections() -> None:
    for literal in (None, "", "  ", "-", "–", "—"):
        assert parse_sections(literal) == ()


def test_unrecognised_literal_is_an_error_not_a_guess() -> None:
    with pytest.raises(ValueError):
        parse_sections("apartado 4.2")
    with pytest.raises(ValueError):
        parse_sections("0.375")


def test_fields_sharing_a_section_produce_one_request() -> None:
    result = group(field("POSOLOGIA"), field("ADUDOMAXDIA"), field("VIA"))
    assert result.call_count == 1
    assert result.requests[0].section.section == "4.2"
    assert [item.field_name for item in result.requests[0].fields] == [
        "ADUDOMAXDIA",
        "POSOLOGIA",
        "VIA",
    ]


def test_field_cited_in_two_sections_appears_in_both_requests() -> None:
    result = group(field("COMPOSICION", "4.2 / 6.6"))
    assert [item.section.section for item in result.requests] == ["4.2", "6.6"]
    assert result.diagnostics == ()


def test_field_without_declared_section_is_a_diagnostic_not_a_silent_drop() -> None:
    result = group(field("SIN_SECCION", None))
    assert result.requests == ()
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].field_name == "SIN_SECCION"


def test_hidden_policy_is_not_requested_and_raises_no_diagnostic() -> None:
    result = group(field("OCULTO", "4.2", "oculto"))
    assert result.requests == ()
    assert result.diagnostics == ()


def test_section_absent_from_the_version_is_reported() -> None:
    result = group(field("POSOLOGIA", "9.9"))
    assert result.requests == ()
    assert "9.9" in result.diagnostics[0].reason


def test_partially_available_sections_keep_the_available_one() -> None:
    result = group(field("MIXTO", "4.2 / 9.9"))
    assert [item.section.section for item in result.requests] == ["4.2"]
    assert len(result.diagnostics) == 1


def test_unrecognised_literal_becomes_a_diagnostic_with_its_literal() -> None:
    result = group(field("RARO", "apartado cuatro"))
    assert result.requests == ()
    assert result.diagnostics[0].literal == "apartado cuatro"


def test_requests_are_ordered_numerically_not_lexicographically() -> None:
    result = group(
        field("A", "1"), field("B", "2"), field("C", "4.2"), field("D", "5.1")
    )
    assert [item.section.section for item in result.requests] == ["1", "2", "4.2", "5.1"]


def test_grouping_reduces_calls_to_the_number_of_distinct_sections() -> None:
    fields = tuple(field(f"CAMPO_{index}", "4.2") for index in range(40))
    result = group(*fields, field("OTRO", "5.1"))
    # 41 campos resueltos en 2 llamadas, no en 41.
    assert result.call_count == 2


def test_duplicate_sections_are_a_usage_error() -> None:
    duplicated = (*SECTIONS, SECTIONS[0])
    with pytest.raises(ValueError):
        group_fields_by_section((field("A"),), duplicated, "version-1", "Omeprazol")


def test_grouping_is_deterministic() -> None:
    first = group(field("B", "4.2"), field("A", "1 / 4.2"))
    second = group(field("B", "4.2"), field("A", "1 / 4.2"))
    assert first == second


def test_repeated_field_name_in_the_same_section_is_a_diagnostic() -> None:
    """El catálogo conserva identidades (bloque, campo) repetidas.

    DEV-302 documentó cinco pares repetidos y prohíbe fusionarlos. Una petición
    no puede llevar el mismo nombre dos veces, así que la repetición se informa
    en lugar de romper la agrupación o deduplicar en silencio.
    """
    result = group(field("DESCRIPCION", "4.2"), field("DESCRIPCION", "4.2"))
    assert result.call_count == 1
    assert [item.field_name for item in result.requests[0].fields] == ["DESCRIPCION"]
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].field_name == "DESCRIPCION"
