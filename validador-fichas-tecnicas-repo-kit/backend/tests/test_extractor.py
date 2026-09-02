import pytest

from pharma_validator_api.evidence_verification import DocumentSection, ProposedExtraction
from pharma_validator_api.extractor import (
    ExtractorError,
    ExtractorIdentity,
    ExtractorLLM,
    FieldRequest,
    NullExtractor,
    SectionRequest,
    run_extraction,
)

SECTION_TEXT = (
    '<div><p><span>La dosis recomendada es de 20 mg una vez al d&#237;a durante '
    "cuatro semanas.</span></p></div>"
)
SECTION = DocumentSection("version-1", "4.2", SECTION_TEXT)
QUOTE = "La dosis recomendada es de 20 mg una vez al d&#237;a"
START = SECTION_TEXT.index(QUOTE)
END = START + len(QUOTE)


def request(*fields: FieldRequest) -> SectionRequest:
    return SectionRequest("version-1", "Omeprazol 20 mg", SECTION, fields or (posologia(),))


def posologia(policy: str = "proponer_valor") -> FieldRequest:
    return FieldRequest("POSOLOGIA", "Dosis recomendada", "CHAR(100)", policy)  # type: ignore[arg-type]


class StubExtractor(ExtractorLLM):
    def __init__(self, *proposals: ProposedExtraction, fail: bool = False) -> None:
        self._proposals = proposals
        self._fail = fail
        self._identity = ExtractorIdentity("stub-v1", "modelo-prueba-7b")

    @property
    def identity(self) -> ExtractorIdentity:
        return self._identity

    def extract_section(self, request: SectionRequest) -> tuple[ProposedExtraction, ...]:
        if self._fail:
            raise ExtractorError("sin respuesta del servidor local")
        return self._proposals


def honest() -> ProposedExtraction:
    return ProposedExtraction(
        field_name="POSOLOGIA",
        state="encontrado",
        proposed_value="20 mg",
        evidence_section="4.2",
        evidence_text=QUOTE,
        evidence_start=START,
        evidence_end=END,
    )


def test_honest_proposal_is_admitted_with_attributable_identity() -> None:
    result = run_extraction(StubExtractor(honest()), request())
    assert len(result.admitted) == 1
    assert result.admitted[0].identity.model == "modelo-prueba-7b"
    assert result.incidents == ()


def test_invented_citation_cannot_be_admitted_by_the_extractor() -> None:
    liar = ProposedExtraction(
        field_name="POSOLOGIA",
        state="encontrado",
        proposed_value="40 mg",
        evidence_section="4.2",
        evidence_text="La dosis recomendada es de 40 mg cada ocho horas",
        evidence_start=START,
        evidence_end=END,
    )
    result = run_extraction(StubExtractor(liar), request())
    assert result.admitted == ()
    assert result.rejected[0].verification.status == "rechazada_texto_no_literal"
    assert result.rejected[0].proposal is None


def test_extractor_cannot_preselect_a_protected_field() -> None:
    preselected = ProposedExtraction(
        field_name="POSOLOGIA",
        state="ambiguo",
        options=("20 mg", "40 mg"),
        selected_option="20 mg",
        evidence_section="4.2",
        evidence_text=QUOTE,
        evidence_start=START,
        evidence_end=END,
    )
    result = run_extraction(
        StubExtractor(preselected), request(posologia("proponer_opciones"))
    )
    assert result.admitted == ()
    assert result.rejected[0].verification.status == "rechazada_opciones_preseleccionadas"


def test_extractor_failure_does_not_block_manual_review() -> None:
    result = run_extraction(StubExtractor(fail=True), request())
    assert result.admitted == ()
    assert result.outcomes == ()
    assert len(result.incidents) == 1
    assert "4.2" in result.incidents[0]


def test_unsolicited_field_is_an_incident_and_not_a_proposal() -> None:
    intruder = ProposedExtraction(field_name="ATC", state="no_encontrado")
    result = run_extraction(StubExtractor(honest(), intruder), request())
    assert [item.field_name for item in result.outcomes] == ["POSOLOGIA"]
    assert any("ATC" in incident for incident in result.incidents)


def test_missing_field_is_reported_as_an_incident() -> None:
    result = run_extraction(
        StubExtractor(honest()),
        request(posologia(), FieldRequest("ATC", "Código ATC", "CHAR(10)", "proponer_valor")),
    )
    assert any("ATC" in incident for incident in result.incidents)


def test_duplicate_field_proposal_is_rejected_once() -> None:
    result = run_extraction(StubExtractor(honest(), honest()), request())
    assert len(result.outcomes) == 1
    assert any("más de una vez" in incident for incident in result.incidents)


def test_null_extractor_proposes_no_value_and_raises_no_incident() -> None:
    result = run_extraction(NullExtractor(), request())
    assert result.incidents == ()
    assert len(result.outcomes) == 1
    outcome = result.outcomes[0]
    # Declarar ausencia es admisible; lo que nunca ocurre es que aporte valor.
    assert outcome.admitted is True
    assert outcome.verification.status == "admitida"
    assert outcome.verification.verified_text is None
    assert outcome.proposal is not None
    assert outcome.proposal.state == "no_encontrado"
    assert outcome.proposal.proposed_value is None
    assert outcome.proposal.options == ()


def test_section_request_requires_matching_version() -> None:
    with pytest.raises(ValueError):
        SectionRequest("otra-version", "Omeprazol", SECTION, (posologia(),))


def test_section_request_rejects_duplicate_fields() -> None:
    with pytest.raises(ValueError):
        SectionRequest("version-1", "Omeprazol", SECTION, (posologia(), posologia()))


def test_extraction_is_deterministic() -> None:
    first = run_extraction(StubExtractor(honest()), request())
    second = run_extraction(StubExtractor(honest()), request())
    assert first == second


def test_extractor_cannot_bypass_verification_by_asserting_its_own_validity() -> None:
    """La barrera no es opcional para la implementación.

    Un adaptador puede devolver lo que quiera; la admisión la decide
    `run_extraction` con el verificador de DEV-405, no el extractor.
    """

    class OverconfidentExtractor(ExtractorLLM):
        @property
        def identity(self) -> ExtractorIdentity:
            return ExtractorIdentity("overconfident-v1", "modelo-mentiroso")

        def extract_section(self, request: SectionRequest) -> tuple[ProposedExtraction, ...]:
            return (
                ProposedExtraction(
                    field_name="POSOLOGIA",
                    state="encontrado",
                    proposed_value="500 mg",
                    evidence_section="4.2",
                    evidence_text="cita que no existe en el documento",
                    evidence_start=0,
                    evidence_end=35,
                ),
            )

    result = run_extraction(OverconfidentExtractor(), request())
    assert result.admitted == ()
    assert result.rejected[0].verification.status == "rechazada_texto_no_literal"
    assert result.rejected[0].proposal is None
