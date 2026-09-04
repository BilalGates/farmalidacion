"""Evaluación del extractor contra el conjunto oro (DEV-408).

Las pruebas fijan las reglas que hacen honesta a la métrica: el desacuerdo
humano no puntúa, la evidencia inválida pesa más que el acierto casual y la
coincidencia normalizada nunca se cuenta como literal.
"""

import pytest

from pharma_validator_api.gold_annotations import GoldAnnotation, GoldEvidence
from pharma_validator_api.gold_evaluation import (
    ExtractorProposal,
    classify,
    consolidate_gold,
    evaluate,
    normalize_for_comparison,
    render_evaluation,
)

HASH = "a" * 64
UNIT = ("123", HASH, "Posología", 1, "DOSIS")
EVIDENCE = GoldEvidence("4.2", 10, 15, "20 mg")


def gold(
    *,
    annotator: str,
    state: str = "valued",
    value: str | None = "20 mg",
    comment: str | None = None,
    field_name: str = "DOSIS",
) -> GoldAnnotation:
    return GoldAnnotation(
        nregistro="123",
        document_version_hash=HASH,
        block_type="Posología",
        occurrence=1,
        field_name=field_name,
        annotator_id=annotator,
        annotated_at="2026-09-04T10:00:00Z",
        state=state,  # type: ignore[arg-type]
        literal_value=value,
        evidence=EVIDENCE if state in {"valued", "source_blank"} else None,
        comment=comment,
    )


def proposal(
    *,
    value: str | None = "20 mg",
    state: str = "valued",
    evidence_admitted: bool = True,
    parse_failed: bool = False,
    latency: float | None = None,
) -> ExtractorProposal:
    return ExtractorProposal(
        unit_key=UNIT,
        field_name="DOSIS",
        state=state,
        proposed_value=value,
        evidence_admitted=evidence_admitted,
        parse_failed=parse_failed,
        latency_seconds=latency,
    )


def test_agreed_annotations_become_the_reference_truth() -> None:
    truth, disagreements, pending = consolidate_gold(
        (gold(annotator="f1"), gold(annotator="f2"))
    )

    assert set(truth) == {UNIT}
    assert truth[UNIT].literal_value == "20 mg"
    assert not disagreements and not pending


def test_a_disagreement_is_excluded_from_scoring() -> None:
    """Medir contra una verdad en disputa produce un número, no una métrica."""
    truth, disagreements, _ = consolidate_gold(
        (gold(annotator="f1", value="20 mg"), gold(annotator="f2", value="20mg"))
    )

    assert truth == {}
    assert disagreements == {UNIT}


def test_a_single_annotation_never_scores() -> None:
    truth, _, pending = consolidate_gold((gold(annotator="f1"),))

    assert truth == {}
    assert pending == {UNIT}


def test_an_exact_literal_match_is_correct() -> None:
    truth, _, _ = consolidate_gold((gold(annotator="f1"), gold(annotator="f2")))

    assert classify(proposal(), truth[UNIT]) == "correcta"


def test_a_format_only_match_is_partial_not_correct() -> None:
    """El contrato exige literalidad; coincidir salvo formato no es acertar."""
    truth, _, _ = consolidate_gold((gold(annotator="f1"), gold(annotator="f2")))

    assert classify(proposal(value="20  MG"), truth[UNIT]) == "parcial"


def test_invalid_evidence_outweighs_a_correct_value() -> None:
    """Un valor correcto con cita inventada es un fallo, no un acierto."""
    truth, _, _ = consolidate_gold((gold(annotator="f1"), gold(annotator="f2")))

    assert (
        classify(proposal(evidence_admitted=False), truth[UNIT]) == "evidencia_invalida"
    )


def test_proposing_a_value_where_gold_says_none_is_a_hallucination() -> None:
    truth, _, _ = consolidate_gold(
        (
            gold(annotator="f1", state="no_consta", value=None, comment="no aparece"),
            gold(annotator="f2", state="no_consta", value=None, comment="no aparece"),
        )
    )

    assert classify(proposal(value="20 mg"), truth[UNIT]) == "alucinacion"


def test_a_missing_proposal_is_not_found() -> None:
    truth, _, _ = consolidate_gold((gold(annotator="f1"), gold(annotator="f2")))

    assert classify(None, truth[UNIT]) == "no_localizada"


def test_an_unparseable_response_is_its_own_category() -> None:
    truth, _, _ = consolidate_gold((gold(annotator="f1"), gold(annotator="f2")))

    assert classify(proposal(parse_failed=True), truth[UNIT]) == "no_parseable"


def test_evaluation_reports_metrics_and_exclusions() -> None:
    annotations = (
        gold(annotator="f1"),
        gold(annotator="f2"),
        gold(annotator="f1", field_name="VIA", value="oral"),
    )
    report = evaluate((proposal(latency=1.5),), annotations, model="modelo-x")

    assert report.model == "modelo-x"
    assert report.scored_units == 1
    # La unidad con una sola anotación queda fuera y se informa.
    assert report.excluded_pending == 1
    assert report.overall.accuracy == 1.0
    assert report.mean_latency == pytest.approx(1.5)


def test_evaluation_requires_an_attributed_model() -> None:
    with pytest.raises(ValueError, match="modelo"):
        evaluate((), (), model="  ")


def test_normalization_is_explicit_and_only_secondary() -> None:
    assert normalize_for_comparison("20  MG") == normalize_for_comparison("20 mg")


def test_rendered_report_always_shows_exclusions() -> None:
    report = evaluate(
        (proposal(),),
        (gold(annotator="f1"), gold(annotator="f2")),
        model="modelo-x",
    )
    text = render_evaluation(report)

    assert "Excluidas por desacuerdo humano" in text
    assert "modelo-x" in text
