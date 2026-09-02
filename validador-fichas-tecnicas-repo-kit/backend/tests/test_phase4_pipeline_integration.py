"""Integración de las piezas de Fase 4 y los núcleos de Fase 5.

Cada módulo tiene sus pruebas unitarias. Esta suite comprueba lo que ninguna de
ellas puede: que encajan entre sí sin adaptadores, y que las barreras siguen en
pie cuando los datos atraviesan toda la cadena.
"""

from pharma_validator_api.evidence_verification import DocumentSection, ProposedExtraction
from pharma_validator_api.extraction_batches import (
    CompletedUnit,
    ExtractionConfiguration,
    WorkUnit,
    plan_batch,
)
from pharma_validator_api.extractor import (
    ExtractorIdentity,
    ExtractorLLM,
    NullExtractor,
    SectionRequest,
    run_extraction,
)
from pharma_validator_api.prefill_policy import (
    assert_no_protected_preselection,
    plan_field_presentation,
)
from pharma_validator_api.section_grouping import CatalogField, group_fields_by_section

SECTION_TEXT = "<p>La dosis recomendada es de 20 mg una vez al d&#237;a.</p>"
SECTIONS = (
    DocumentSection("v1", "4.2", SECTION_TEXT),
    DocumentSection("v1", "5.1", "<p>Propiedades farmacológicas.</p>"),
)
CATALOG = (
    CatalogField("ATC", "Código ATC", "CHAR(10)", "proponer_valor", "4.2"),
    CatalogField("ADUDOMAXDIA", "Dosis máxima diaria", "DECIMAL(10,3)", "solo_evidencia", "4.2"),
    CatalogField("FRECUENCIA", "Frecuencia", "CHAR(50)", "proponer_opciones", "5.1"),
    CatalogField("INTERNO", "Campo interno", "CHAR(10)", "oculto", "4.2"),
)


def grouped() -> tuple[SectionRequest, ...]:
    return group_fields_by_section(CATALOG, SECTIONS, "v1", "Omeprazol 20 mg").requests


def configuration(model: str = "modelo-7b") -> ExtractionConfiguration:
    return ExtractionConfiguration(
        ExtractorIdentity("extractor-v1", model), "prompt-v1", "guided-extraction-v1"
    )


def test_catalog_reaches_extraction_through_grouping_and_planning() -> None:
    requests = grouped()
    # El campo oculto no se pide; los otros tres caen en dos apartados.
    assert len(requests) == 2
    requested = {field.field_name for item in requests for field in item.fields}
    assert requested == {"ATC", "ADUDOMAXDIA", "FRECUENCIA"}

    plan = plan_batch(requests, configuration())
    assert len(plan.pending) == 2

    outcomes = [run_extraction(NullExtractor(), request) for request in plan.pending]
    assert all(item.incidents == () for item in outcomes)
    # El extractor nulo declara ausencia: admitido, pero sin ningún valor.
    proposals = [
        outcome.proposal
        for result in outcomes
        for outcome in result.admitted
        if outcome.proposal is not None
    ]
    assert proposals
    assert all(item.proposed_value is None for item in proposals)


def test_a_lying_extractor_is_stopped_before_presentation() -> None:
    """La cita inventada no llega a la pantalla aunque el extractor insista."""

    class LyingExtractor(ExtractorLLM):
        @property
        def identity(self) -> ExtractorIdentity:
            return ExtractorIdentity("mentiroso-v1", "modelo-x")

        def extract_section(self, request: SectionRequest) -> tuple[ProposedExtraction, ...]:
            return tuple(
                ProposedExtraction(
                    field_name=field.field_name,
                    state="encontrado",
                    proposed_value="99",
                    evidence_section=request.section.section,
                    evidence_text="cita que no aparece en el documento",
                    evidence_start=0,
                    evidence_end=36,
                )
                for field in request.fields
            )

    for request in grouped():
        result = run_extraction(LyingExtractor(), request)
        assert result.admitted == ()
        assert all(item.proposal is None for item in result.rejected)


def test_protected_fields_stay_empty_across_the_whole_screen() -> None:
    plans = tuple(
        plan_field_presentation(field.field_name, field.policy) for field in CATALOG
    )
    assert_no_protected_preselection(plans)
    presentation = {item.field_name: item.presentation for item in plans}
    assert presentation["ATC"] == "valor_precargado"
    assert presentation["ADUDOMAXDIA"] == "casilla_vacia"
    assert presentation["FRECUENCIA"] == "opciones_sin_marcar"
    assert presentation["INTERNO"] == "no_visible"


def test_resuming_after_an_interruption_skips_completed_work() -> None:
    requests = grouped()
    config = configuration()
    first = requests[0]
    done = CompletedUnit(
        WorkUnit(
            first.document_version_id,
            first.section.section,
            tuple(field.field_name for field in first.fields),
        ).key,
        config.fingerprint(),
        "completada",
    )
    plan = plan_batch(requests, config, (done,))
    assert len(plan.pending) == len(requests) - 1
    assert len(plan.reused) == 1


def test_changing_the_model_replans_everything_without_losing_history() -> None:
    requests = grouped()
    original = configuration()
    completed = tuple(
        CompletedUnit(
            WorkUnit(
                item.document_version_id,
                item.section.section,
                tuple(field.field_name for field in item.fields),
            ).key,
            original.fingerprint(),
            "completada",
        )
        for item in requests
    )
    plan = plan_batch(requests, configuration(model="modelo-30b"), completed)
    assert len(plan.pending) == len(requests)
    assert len(plan.superseded) == len(requests)
    assert plan.reused == ()
