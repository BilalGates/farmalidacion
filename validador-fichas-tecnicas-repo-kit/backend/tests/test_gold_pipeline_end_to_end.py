"""Recorrido completo del conjunto oro con fixtures, sin red ni GPU.

    anotaciones → checker → conciliación → gold final → evaluación → métricas

Estas pruebas existen porque cada etapa por separado ya está cubierta, pero
nada garantizaba que **encajasen**: que el JSONL que escribe un anotador lo lea
el checker, que las mismas anotaciones alimenten los artefactos contractuales y
que el resultado sea evaluable. Un fallo de encaje sólo aparecería el día de la
anotación real, que es exactamente cuando no puede aparecer.

No se usa el corpus real: el objetivo es el encaje entre etapas, no el
contenido. La verificación sobre corpus real vive en `test_gold_selection`.
"""

import csv
import json

from pharma_validator_api.gold_annotations import (
    GoldAnnotation,
    GoldEvidence,
    build_gold_artifacts,
)
from pharma_validator_api.gold_completeness import check_gold_completeness
from pharma_validator_api.gold_evaluation import (
    ExtractorProposal,
    evaluate,
    render_evaluation,
)
from pharma_validator_api.reviewer_identity import ReviewerDirectory

HASH = "b" * 64
# HTML literal con entidades, como el corpus real: la evidencia se cita sobre
# esta cadena tal cual, sin desescapar.
SECTION = "<p>Dosis habitual: 20 mg cada 24&#160;horas</p>"
SECTIONS = {(HASH, "4.2"): SECTION}
SELECTION = {
    "run_id": "run-e2e",
    "algorithm_version": "gold-selection-v1",
    "seed": 407,
    "items": [{"ordinal": 1, "nregistro": "12345", "document_version_hash": HASH}],
}
DIRECTORY = ReviewerDirectory.from_configuration(
    ("f1:Farmacéutica Uno", "f2:Farmacéutico Dos")
)

DOSIS_START = SECTION.index("20 mg")
DOSIS_END = DOSIS_START + len("20 mg")


def annotation(
    *,
    annotator: str,
    field_name: str = "DOSIS",
    state: str = "valued",
    value: str | None = "20 mg",
    evidence: GoldEvidence | None = None,
    comment: str | None = None,
) -> GoldAnnotation:
    if evidence is None and state == "valued":
        evidence = GoldEvidence("4.2", DOSIS_START, DOSIS_END, "20 mg")
    return GoldAnnotation(
        nregistro="12345",
        document_version_hash=HASH,
        block_type="Posología",
        occurrence=1,
        field_name=field_name,
        annotator_id=annotator,
        annotated_at="2026-09-04T09:00:00Z",
        state=state,  # type: ignore[arg-type]
        literal_value=value,
        evidence=evidence,
        comment=comment,
    )


def round_trip(annotations: tuple[GoldAnnotation, ...]) -> tuple[GoldAnnotation, ...]:
    """Serializa a JSONL y vuelve, como hacen las CLI reales.

    Es la parte del encaje que más fácilmente se rompe: el núcleo puede estar
    perfecto y aun así el fichero que escribe un anotador no reconstruirse.
    """
    lines = [
        json.dumps(
            {
                "nregistro": item.nregistro,
                "document_version_hash": item.document_version_hash,
                "block_type": item.block_type,
                "occurrence": item.occurrence,
                "field_name": item.field_name,
                "annotator_id": item.annotator_id,
                "annotated_at": item.annotated_at,
                "state": item.state,
                "literal_value": item.literal_value,
                "evidence": (
                    {
                        "section_id": item.evidence.section_id,
                        "start": item.evidence.start,
                        "end": item.evidence.end,
                        "literal_text": item.evidence.literal_text,
                    }
                    if item.evidence
                    else None
                ),
                "comment": item.comment,
            },
            ensure_ascii=False,
        )
        for item in annotations
    ]
    restored = []
    for line in lines:
        payload = json.loads(line)
        evidence_payload = payload.pop("evidence", None)
        evidence = GoldEvidence(**evidence_payload) if evidence_payload else None
        restored.append(GoldAnnotation(evidence=evidence, **payload))
    return tuple(restored)


def test_full_pipeline_from_annotations_to_metrics() -> None:
    """El camino feliz completo, etapa por etapa, sobre los mismos datos."""
    annotations = round_trip(
        (annotation(annotator="f1"), annotation(annotator="f2"))
    )

    # 1. Checker: identidades registradas y conjunto oro cerrado.
    report = check_gold_completeness(
        SELECTION, annotations, SECTIONS, directory=DIRECTORY
    )
    assert report.is_ready
    assert report.open_disagreements == 0

    # 2. Artefactos contractuales, exigiendo cierre.
    artifacts = build_gold_artifacts(
        SELECTION, annotations, SECTIONS, require_complete=True
    )
    assert set(artifacts) == {
        "gold-selection.json",
        "gold-annotations.jsonl",
        "gold-disagreements.csv",
        "run-manifest.json",
        "summary.md",
    }
    # Sin desacuerdos, el CSV sólo tiene cabecera.
    rows = list(csv.reader(artifacts["gold-disagreements.csv"].decode().splitlines()))
    assert len(rows) == 1

    # 3. Evaluación contra una propuesta que acierta con cita admitida.
    proposal = ExtractorProposal(
        unit_key=annotations[0].unit_key,
        field_name="DOSIS",
        state="valued",
        proposed_value="20 mg",
        evidence_admitted=True,
        latency_seconds=0.5,
    )
    evaluation = evaluate((proposal,), annotations, model="modelo-fixture")

    assert evaluation.scored_units == 1
    assert evaluation.overall.accuracy == 1.0
    assert evaluation.overall.valid_evidence_rate == 1.0
    assert evaluation.outcomes == {"correcta": 1}
    assert "modelo-fixture" in render_evaluation(evaluation)


def test_a_disagreement_travels_through_the_pipeline_and_blocks_metrics() -> None:
    """Un desacuerdo debe sobrevivir hasta el CSV y no puntuar en las métricas."""
    annotations = round_trip(
        (
            annotation(annotator="f1", value="20 mg"),
            annotation(
                annotator="f2",
                value="Dosis",
                evidence=GoldEvidence("4.2", 3, 8, "Dosis"),
            ),
        )
    )

    report = check_gold_completeness(
        SELECTION, annotations, SECTIONS, directory=DIRECTORY
    )
    assert not report.is_ready
    assert report.open_disagreements == 1

    # El conjunto oro no puede cerrarse, pero el desacuerdo se conserva.
    artifacts = build_gold_artifacts(SELECTION, annotations, SECTIONS)
    rows = list(csv.reader(artifacts["gold-disagreements.csv"].decode().splitlines()))
    assert len(rows) == 2
    assert rows[1][-1] == "open"
    # Ambas anotaciones originales sobreviven, ninguna se sobrescribe.
    assert "20 mg" in rows[1] and "Dosis" in rows[1]

    # La unidad en disputa no puntúa y se informa aparte.
    evaluation = evaluate((), annotations, model="modelo-fixture")
    assert evaluation.scored_units == 0
    assert evaluation.excluded_disagreements == 1


def test_pipeline_refuses_to_close_with_a_pending_unit() -> None:
    """`pending` significa trabajo sin terminar y bloquea el cierre."""
    annotations = round_trip(
        (
            annotation(annotator="f1"),
            annotation(annotator="f2", state="pending", value=None),
        )
    )

    report = check_gold_completeness(
        SELECTION, annotations, SECTIONS, directory=DIRECTORY
    )
    assert not report.is_ready
    assert report.pending_units == 1

    try:
        build_gold_artifacts(SELECTION, annotations, SECTIONS, require_complete=True)
    except Exception as error:  # noqa: BLE001 - se comprueba el mensaje
        assert "pending" in str(error)
    else:  # pragma: no cover
        raise AssertionError("Un conjunto oro con pending no puede cerrarse.")


def test_artifacts_are_byte_identical_across_runs() -> None:
    """Criterio 8 del contrato, verificado extremo a extremo."""
    annotations = round_trip(
        (annotation(annotator="f1"), annotation(annotator="f2"))
    )

    first = build_gold_artifacts(SELECTION, annotations, SECTIONS)
    second = build_gold_artifacts(SELECTION, annotations, SECTIONS)

    assert first == second


def test_hallucination_survives_the_round_trip_and_is_penalised() -> None:
    """Proponer donde el oro dice que no hay dato es alucinación, no error menor."""
    annotations = round_trip(
        (
            annotation(
                annotator="f1",
                state="no_consta",
                value=None,
                comment="revisados 4.1 y 4.2",
            ),
            annotation(
                annotator="f2",
                state="no_consta",
                value=None,
                comment="revisados 4.1 y 4.2",
            ),
        )
    )

    report = check_gold_completeness(
        SELECTION, annotations, SECTIONS, directory=DIRECTORY
    )
    assert report.is_ready

    invented = ExtractorProposal(
        unit_key=annotations[0].unit_key,
        field_name="DOSIS",
        state="valued",
        proposed_value="20 mg",
        evidence_admitted=True,
    )
    evaluation = evaluate((invented,), annotations, model="modelo-fixture")

    assert evaluation.outcomes == {"alucinacion": 1}
    assert evaluation.overall.accuracy == 0.0
    assert evaluation.overall.hallucinations == 1
