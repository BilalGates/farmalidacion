"""Completitud estructural del conjunto oro.

Estas pruebas fijan una idea central: el comprobador debe declarar "no listo"
ante cualquier duda. Un conjunto oro parcial que se declara completo produce
métricas que parecen válidas y no lo son.
"""

from pharma_validator_api.gold_annotations import GoldAnnotation, GoldEvidence
from pharma_validator_api.gold_completeness import (
    check_gold_completeness,
    render_report,
)

HASH = "a" * 64
SELECTION = {
    "run_id": "run-1",
    "items": [{"ordinal": 1, "nregistro": "123", "document_version_hash": HASH}],
}
SECTIONS = {(HASH, "4.2"): "<p>Dosis: 20 mg</p>"}
EVIDENCE = GoldEvidence("4.2", 10, 15, "20 mg")


def annotation(
    *,
    annotator: str,
    state: str = "valued",
    value: str | None = "20 mg",
    evidence: GoldEvidence | None = EVIDENCE,
    comment: str | None = None,
    field_name: str = "DOSIS",
    occurrence: int = 1,
) -> GoldAnnotation:
    return GoldAnnotation(
        nregistro="123",
        document_version_hash=HASH,
        block_type="Posología",
        occurrence=occurrence,
        field_name=field_name,
        annotator_id=annotator,
        annotated_at="2026-09-03T12:00:00Z",
        state=state,  # type: ignore[arg-type]
        literal_value=value,
        evidence=evidence,
        comment=comment,
    )


def test_an_empty_gold_set_is_never_ready() -> None:
    """Sin anotación real no hay conjunto oro, por muy válida que sea la selección."""
    report = check_gold_completeness(SELECTION, (), SECTIONS)

    assert not report.is_ready
    assert report.expected_documents == 1
    assert report.annotated_documents == 0
    assert report.documents_without_annotations == ("123",)
    assert report.progress == 0.0


def test_double_annotation_in_agreement_is_ready() -> None:
    report = check_gold_completeness(
        SELECTION,
        (annotation(annotator="f1"), annotation(annotator="f2")),
        SECTIONS,
    )

    assert report.is_ready
    assert report.comparable_units == 1
    assert report.completed_units == 1
    assert report.open_disagreements == 0
    assert report.progress == 1.0


def test_a_single_annotator_is_not_a_gold_set() -> None:
    """Una sola anotación no es doble anotación aunque esté terminada."""
    report = check_gold_completeness(SELECTION, (annotation(annotator="f1"),), SECTIONS)

    assert not report.is_ready
    assert report.single_annotator_units == 1
    # El contrato exige exactamente dos anotadores.
    assert any("dos anotadores" in error for error in report.structural_errors)


def test_open_disagreements_block_readiness() -> None:
    """Un desacuerdo sin conciliar no puede entrar en el cálculo de métricas."""
    report = check_gold_completeness(
        SELECTION,
        (
            annotation(annotator="f1", value="20 mg"),
            annotation(
                annotator="f2",
                value="Dosis",
                evidence=GoldEvidence("4.2", 3, 8, "Dosis"),
            ),
        ),
        SECTIONS,
    )

    assert not report.is_ready
    assert report.open_disagreements == 1


def test_pending_units_block_readiness() -> None:
    report = check_gold_completeness(
        SELECTION,
        (
            annotation(annotator="f1"),
            annotation(annotator="f2", state="pending", value=None, evidence=None),
        ),
        SECTIONS,
    )

    assert not report.is_ready
    assert report.pending_units == 1
    assert report.completed_units == 0


def test_evidence_that_does_not_reproduce_its_offsets_is_a_structural_error() -> None:
    """La cita se verifica por igualdad exacta, nunca por parecido."""
    report = check_gold_completeness(
        SELECTION,
        (
            annotation(annotator="f1"),
            annotation(
                annotator="f2",
                evidence=GoldEvidence("4.2", 10, 15, "40 mg"),
            ),
        ),
        SECTIONS,
    )

    assert not report.is_ready
    assert report.structural_errors


def test_an_annotation_outside_the_selection_is_reported() -> None:
    outsider = GoldAnnotation(
        nregistro="999",
        document_version_hash=HASH,
        block_type="Posología",
        occurrence=1,
        field_name="DOSIS",
        annotator_id="f1",
        annotated_at="2026-09-03T12:00:00Z",
        state="valued",
        literal_value="20 mg",
        evidence=EVIDENCE,
    )
    report = check_gold_completeness(SELECTION, (outsider,), SECTIONS)

    assert not report.is_ready
    assert any("selección oro" in error for error in report.structural_errors)


def test_expected_scope_detects_a_field_nobody_annotated() -> None:
    """Sin alcance declarado no puede detectarse un campo que nadie tocó."""
    report = check_gold_completeness(
        SELECTION,
        (annotation(annotator="f1"), annotation(annotator="f2")),
        SECTIONS,
        expected_units_per_document=2,
    )

    assert not report.is_ready
    assert any("Se esperaban 2 unidades" in error for error in report.structural_errors)


def test_duplicate_annotation_from_the_same_annotator_is_rejected() -> None:
    report = check_gold_completeness(
        SELECTION,
        (
            annotation(annotator="f1"),
            annotation(annotator="f1"),
            annotation(annotator="f2"),
        ),
        SECTIONS,
    )

    assert not report.is_ready
    assert any("duplicada" in error for error in report.structural_errors)


def test_report_states_the_verdict_explicitly() -> None:
    """El informe se lee en operación diaria; el veredicto no puede ser implícito."""
    text = render_report(check_gold_completeness(SELECTION, (), SECTIONS))

    assert "GOLD NO LISTO" in text
    assert "Fichas esperadas: 1" in text
