import pytest

from pharma_validator_api.evidence_verification import (
    DocumentSection,
    EvidenceVerificationError,
    ProposedExtraction,
    verify_extraction,
)

SECTION_TEXT = (
    '<div><p style="margin:0pt"><span>La dosis recomendada es de 20 mg una vez al d&#237;a '
    "durante cuatro semanas.</span></p></div>"
)
SECTION = DocumentSection("version-1", "4.2", SECTION_TEXT)
SECTIONS = (SECTION,)


def cited(text: str) -> tuple[int, int]:
    start = SECTION_TEXT.index(text)
    return start, start + len(text)


def proposal(**overrides: object) -> ProposedExtraction:
    quote = "La dosis recomendada es de 20 mg una vez al d&#237;a"
    start, end = cited(quote)
    base = {
        "field_name": "POSOLOGIA",
        "state": "encontrado",
        "proposed_value": "20 mg",
        "evidence_section": "4.2",
        "evidence_text": quote,
        "evidence_start": start,
        "evidence_end": end,
    }
    base.update(overrides)
    return ProposedExtraction(**base)  # type: ignore[arg-type]


def test_exact_literal_citation_is_admitted() -> None:
    result = verify_extraction(proposal(), SECTIONS, "proponer_valor")
    assert result.admitted is True
    assert result.status == "admitida"
    assert result.verified_text is not None


def test_invented_citation_absent_from_section_is_rejected() -> None:
    result = verify_extraction(
        proposal(evidence_text="La dosis recomendada es de 40 mg cada ocho horas"),
        SECTIONS,
        "proponer_valor",
    )
    assert result.admitted is False
    assert result.status == "rechazada_texto_no_literal"


def test_citation_shifted_by_one_character_is_rejected() -> None:
    quote = "La dosis recomendada es de 20 mg una vez al d&#237;a"
    start, end = cited(quote)
    result = verify_extraction(
        proposal(evidence_start=start + 1, evidence_end=end),
        SECTIONS,
        "proponer_valor",
    )
    assert result.status == "rechazada_texto_no_literal"


def test_citation_may_split_an_html_entity_when_offsets_match_exactly() -> None:
    # El corpus real conserva entidades sin desescapar. Un intervalo puede partir
    # `&#237;`; el contrato del conjunto oro prohíbe expandirlo hasta un límite limpio.
    quote = SECTION_TEXT[60:110]
    start, end = 60, 110
    assert "&#" in SECTION_TEXT
    result = verify_extraction(
        proposal(evidence_text=quote, evidence_start=start, evidence_end=end),
        SECTIONS,
        "proponer_valor",
    )
    assert result.admitted is True


def test_unescaped_citation_does_not_match_canonical_text() -> None:
    result = verify_extraction(
        proposal(evidence_text="La dosis recomendada es de 20 mg una vez al día"),
        SECTIONS,
        "proponer_valor",
    )
    assert result.status == "rechazada_texto_no_literal"


def test_value_without_citation_is_never_persisted() -> None:
    result = verify_extraction(
        proposal(evidence_text=None, evidence_section=None),
        SECTIONS,
        "proponer_valor",
    )
    assert result.status == "rechazada_sin_evidencia"


def test_unknown_section_is_rejected() -> None:
    result = verify_extraction(proposal(evidence_section="4.9"), SECTIONS, "proponer_valor")
    assert result.status == "rechazada_seccion_desconocida"


def test_offsets_outside_the_section_are_rejected() -> None:
    result = verify_extraction(
        proposal(evidence_start=0, evidence_end=len(SECTION_TEXT) + 5),
        SECTIONS,
        "proponer_valor",
    )
    assert result.status == "rechazada_offsets_invalidos"


def test_citation_shorter_than_the_minimum_is_rejected() -> None:
    quote = SECTION_TEXT[10:15]
    result = verify_extraction(
        proposal(evidence_text=quote, evidence_start=10, evidence_end=15),
        SECTIONS,
        "proponer_valor",
    )
    assert result.status == "rechazada_longitud_evidencia"


def test_not_found_state_is_admitted_only_without_value() -> None:
    admitted = verify_extraction(
        ProposedExtraction(field_name="POSOLOGIA", state="no_encontrado"),
        SECTIONS,
        "proponer_valor",
    )
    assert admitted.admitted is True
    assert admitted.verified_text is None

    rejected = verify_extraction(
        ProposedExtraction(
            field_name="POSOLOGIA", state="no_encontrado", proposed_value="20 mg"
        ),
        SECTIONS,
        "proponer_valor",
    )
    assert rejected.status == "rechazada_valor_sin_soporte"


def test_hidden_policy_never_persists_a_proposal() -> None:
    result = verify_extraction(proposal(), SECTIONS, "oculto")
    assert result.status == "rechazada_politica_oculta"


def test_protected_policies_reject_a_preselected_option() -> None:
    for policy in ("proponer_opciones", "solo_evidencia"):
        result = verify_extraction(
            proposal(proposed_value=None, options=("oral",), selected_option="oral"),
            SECTIONS,
            policy,  # type: ignore[arg-type]
        )
        assert result.status == "rechazada_opciones_preseleccionadas"


def test_evidence_only_policy_rejects_a_proposed_value() -> None:
    result = verify_extraction(proposal(), SECTIONS, "solo_evidencia")
    assert result.status == "rechazada_valor_sin_soporte"


def test_evidence_only_policy_admits_a_citation_without_value() -> None:
    result = verify_extraction(proposal(proposed_value=None), SECTIONS, "solo_evidencia")
    assert result.admitted is True


def test_ambiguous_state_requires_options() -> None:
    result = verify_extraction(
        proposal(state="ambiguo", proposed_value=None),
        SECTIONS,
        "proponer_opciones",
    )
    assert result.status == "rechazada_valor_sin_soporte"


def test_options_policy_rejects_a_single_proposed_value() -> None:
    result = verify_extraction(
        proposal(state="ambiguo", options=("20 mg", "40 mg")),
        SECTIONS,
        "proponer_opciones",
    )
    assert result.status == "rechazada_valor_sin_soporte"


def test_duplicate_sections_are_a_usage_error() -> None:
    with pytest.raises(EvidenceVerificationError):
        verify_extraction(proposal(), (SECTION, SECTION), "proponer_valor")


def test_verification_is_deterministic() -> None:
    first = verify_extraction(proposal(), SECTIONS, "proponer_valor")
    second = verify_extraction(proposal(), SECTIONS, "proponer_valor")
    assert first == second


def test_grouping_section_without_text_is_distinguished_from_bad_offsets() -> None:
    # 1.464 de 13.907 secciones del corpus real son cabeceras sin `contenido`.
    sections = (*SECTIONS, DocumentSection("version-1", "4", ""))
    result = verify_extraction(
        proposal(
            evidence_section="4",
            evidence_text="DATOS CLINICOS",
            evidence_start=0,
            evidence_end=14,
        ),
        sections,
        "proponer_valor",
    )
    assert result.status == "rechazada_seccion_sin_texto"
    assert result.admitted is False
