import json

import pytest

from pharma_validator_api.gold_annotations import (
    GoldAnnotation,
    GoldAnnotationError,
    GoldEvidence,
    build_gold_artifacts,
    validate_annotation,
)

HASH = "a" * 64
SELECTION = {
    "run_id": "run-1",
    "items": [{"ordinal": 1, "nregistro": "123", "document_version_hash": HASH}],
}
SECTIONS = {(HASH, "4.2"): "<p>Dosis: 20 mg</p>"}
DEFAULT_EVIDENCE = GoldEvidence("4.2", 10, 15, "20 mg")


def annotation(
    *,
    annotator: str = "farmaceutico-1",
    state: str = "valued",
    value: str | None = "20 mg",
    evidence: GoldEvidence | None = DEFAULT_EVIDENCE,
    comment: str | None = None,
    occurrence: int = 1,
) -> GoldAnnotation:
    return GoldAnnotation(
        nregistro="123",
        document_version_hash=HASH,
        block_type="Posología",
        occurrence=occurrence,
        field_name="DOSIS",
        annotator_id=annotator,
        annotated_at="2026-09-03T12:00:00Z",
        state=state,  # type: ignore[arg-type]
        literal_value=value,
        evidence=evidence,
        comment=comment,
    )


def test_valued_requires_exact_literal_offsets() -> None:
    validate_annotation(annotation(), SECTIONS)
    with pytest.raises(GoldAnnotationError, match="no coincide literalmente"):
        validate_annotation(annotation(evidence=GoldEvidence("4.2", 10, 15, "20 MG")), SECTIONS)
    with pytest.raises(GoldAnnotationError, match="desplazamientos"):
        validate_annotation(annotation(evidence=GoldEvidence("4.2", 10, 99, "20 mg")), SECTIONS)


def test_evidence_is_not_checked_against_normalized_html() -> None:
    sections = {(HASH, "4.2"): "Dosis: 20&#xa0;mg"}
    with pytest.raises(GoldAnnotationError, match="no coincide literalmente"):
        validate_annotation(
            annotation(evidence=GoldEvidence("4.2", 7, 12, "20 mg")),
            sections,
        )


def test_states_remain_distinct_and_enforce_their_requirements() -> None:
    validate_annotation(annotation(state="source_absent", value=None, evidence=None), SECTIONS)
    validate_annotation(
        annotation(state="source_blank", value=None, evidence=GoldEvidence("4.2", 10, 10, "")),
        SECTIONS,
    )
    validate_annotation(
        annotation(state="no_consta", value=None, evidence=None, comment="Revisado"), SECTIONS
    )
    validate_annotation(
        annotation(state="not_applicable", value=None, evidence=None, comment="No corresponde"),
        SECTIONS,
    )
    with pytest.raises(GoldAnnotationError, match="exige comentario"):
        validate_annotation(annotation(state="no_consta", value=None, evidence=None), SECTIONS)
    with pytest.raises(GoldAnnotationError, match="Solo valued"):
        validate_annotation(
            annotation(state="source_absent", value="inventado", evidence=None), SECTIONS
        )


def test_occurrences_are_kept_as_separate_units() -> None:
    artifacts = build_gold_artifacts(
        SELECTION, (annotation(occurrence=1), annotation(occurrence=2)), SECTIONS
    )
    rows = [json.loads(line) for line in artifacts["gold-annotations.jsonl"].decode().splitlines()]
    assert [row["occurrence"] for row in rows] == [1, 2]


def test_pending_blocks_closure_but_is_valid_as_a_draft() -> None:
    pending = annotation(state="pending", value=None, evidence=None)
    build_gold_artifacts(SELECTION, (pending,), SECTIONS)
    with pytest.raises(GoldAnnotationError, match="pending"):
        build_gold_artifacts(SELECTION, (pending,), SECTIONS, require_complete=True)


def test_disagreement_is_preserved_open_without_resolution() -> None:
    first = annotation(annotator="farmaceutico-1")
    second = annotation(
        annotator="farmaceutico-2",
        value="20 MG",
        evidence=GoldEvidence("4.2", 10, 15, "20 mg"),
    )
    artifacts = build_gold_artifacts(SELECTION, (second, first), SECTIONS)
    csv_text = artifacts["gold-disagreements.csv"].decode()
    assert "farmaceutico-1,valued,20 mg" in csv_text
    assert "farmaceutico-2,valued,20 MG" in csv_text
    assert csv_text.rstrip().endswith(",open")
    assert "Desacuerdos abiertos: 1" in artifacts["summary.md"].decode()


def test_outputs_are_byte_identical_and_inputs_are_not_mutated() -> None:
    items = (annotation(annotator="b"), annotation(annotator="a"))
    selection_before = json.dumps(SELECTION, sort_keys=True)
    first = build_gold_artifacts(SELECTION, items, SECTIONS)
    second = build_gold_artifacts(SELECTION, tuple(reversed(items)), SECTIONS)
    assert first == second
    assert json.dumps(SELECTION, sort_keys=True) == selection_before
    assert set(first) == {
        "gold-selection.json",
        "gold-annotations.jsonl",
        "gold-disagreements.csv",
        "run-manifest.json",
        "summary.md",
    }


def test_rejects_annotations_outside_selection_and_duplicates() -> None:
    outside = GoldAnnotation(**{**annotation().__dict__, "nregistro": "999"})
    with pytest.raises(GoldAnnotationError, match="no pertenece"):
        build_gold_artifacts(SELECTION, (outside,), SECTIONS)
    with pytest.raises(GoldAnnotationError, match="más de una"):
        build_gold_artifacts(SELECTION, (annotation(), annotation()), SECTIONS)
