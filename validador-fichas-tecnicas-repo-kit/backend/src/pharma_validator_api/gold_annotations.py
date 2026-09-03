"""Validación y artefactos deterministas para la doble anotación del conjunto oro.

El módulo es puro: no abre archivos ni red. Recibe la selección, el contenido
literal de secciones inmutables y anotaciones humanas ya realizadas. No inventa
anotadores, valores, evidencias ni conciliaciones.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

AnnotationState = Literal[
    "pending", "valued", "source_absent", "source_blank", "no_consta", "not_applicable"
]
FINISHED_STATES = frozenset(
    {"valued", "source_absent", "source_blank", "no_consta", "not_applicable"}
)
TOOL_VERSION = "gold-annotations-v1"


class GoldAnnotationError(ValueError):
    """La entrada incumple el contrato de anotación oro."""


@dataclass(frozen=True)
class GoldEvidence:
    section_id: str
    start: int
    end: int
    literal_text: str


@dataclass(frozen=True)
class GoldAnnotation:
    nregistro: str
    document_version_hash: str
    block_type: str
    occurrence: int
    field_name: str
    annotator_id: str
    annotated_at: str
    state: AnnotationState = "pending"
    literal_value: str | None = None
    evidence: GoldEvidence | None = None
    comment: str | None = None

    @property
    def unit_key(self) -> tuple[str, str, str, int, str]:
        return (
            self.nregistro,
            self.document_version_hash,
            self.block_type,
            self.occurrence,
            self.field_name,
        )


def validate_annotation(
    annotation: GoldAnnotation,
    section_contents: Mapping[tuple[str, str], str],
) -> None:
    """Valida una anotación contra el HTML literal de su versión inmutable."""
    if not all(
        value.strip()
        for value in (
            annotation.nregistro,
            annotation.document_version_hash,
            annotation.block_type,
            annotation.field_name,
            annotation.annotator_id,
            annotation.annotated_at,
        )
    ):
        raise GoldAnnotationError("La identidad completa y el anotador son obligatorios.")
    if annotation.occurrence < 1:
        raise GoldAnnotationError("La ocurrencia debe ser un entero positivo.")
    if annotation.state not in FINISHED_STATES | {"pending"}:
        raise GoldAnnotationError(f"Estado de anotación no admitido: {annotation.state}")

    evidence = annotation.evidence
    if evidence is not None:
        content = section_contents.get((annotation.document_version_hash, evidence.section_id))
        if content is None:
            raise GoldAnnotationError(
                "La evidencia no pertenece a una sección de la versión indicada."
            )
        if evidence.start < 0 or evidence.end < evidence.start or evidence.end > len(content):
            raise GoldAnnotationError("Los desplazamientos de evidencia están fuera de la sección.")
        if content[evidence.start : evidence.end] != evidence.literal_text:
            raise GoldAnnotationError(
                "La evidencia no coincide literalmente con sus desplazamientos."
            )

    if annotation.state == "valued":
        if annotation.literal_value is None or annotation.literal_value == "":
            raise GoldAnnotationError("valued exige un valor literal.")
        if evidence is None or evidence.literal_text == "":
            raise GoldAnnotationError("valued exige evidencia literal exacta.")
    elif annotation.literal_value is not None:
        raise GoldAnnotationError("Solo valued puede contener un valor literal.")

    if annotation.state == "source_blank" and evidence is None:
        raise GoldAnnotationError("source_blank exige localizar la posición vacía.")
    if annotation.state in {"no_consta", "not_applicable"} and not (
        annotation.comment and annotation.comment.strip()
    ):
        raise GoldAnnotationError(f"{annotation.state} exige comentario humano.")


def _annotation_dict(annotation: GoldAnnotation) -> dict[str, object]:
    payload = asdict(annotation)
    return payload


def _canonical_json(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_gold_artifacts(
    selection: Mapping[str, object],
    annotations: tuple[GoldAnnotation, ...],
    section_contents: Mapping[tuple[str, str], str],
    *,
    require_complete: bool = False,
) -> dict[str, bytes]:
    """Genera las cinco salidas contractuales sin escribir ni mutar entradas."""
    selected = {
        (str(item["nregistro"]), str(item["document_version_hash"]))
        for item in cast(list[dict[str, Any]], selection.get("items", []))
    }
    if not selected:
        raise GoldAnnotationError("La selección oro está vacía.")

    seen: set[tuple[tuple[str, str, str, int, str], str]] = set()
    for annotation in annotations:
        if (annotation.nregistro, annotation.document_version_hash) not in selected:
            raise GoldAnnotationError("La anotación no pertenece a la selección oro.")
        validate_annotation(annotation, section_contents)
        identity = (annotation.unit_key, annotation.annotator_id)
        if identity in seen:
            raise GoldAnnotationError(
                "Existe más de una anotación del mismo anotador para la unidad."
            )
        seen.add(identity)
    if require_complete and any(item.state == "pending" for item in annotations):
        raise GoldAnnotationError(
            "El conjunto oro no puede cerrarse mientras existan unidades pending."
        )

    ordered = tuple(sorted(annotations, key=lambda item: (item.unit_key, item.annotator_id)))
    annotation_bytes = b"".join(_canonical_json(_annotation_dict(item)) for item in ordered)

    grouped: dict[tuple[str, str, str, int, str], list[GoldAnnotation]] = defaultdict(list)
    for item in ordered:
        grouped[item.unit_key].append(item)
    disagreements = [
        (key, items)
        for key, items in grouped.items()
        if len(items) == 2
        and (items[0].state, items[0].literal_value) != (items[1].state, items[1].literal_value)
    ]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "nregistro",
            "document_version_hash",
            "block_type",
            "occurrence",
            "field_name",
            "annotator_1",
            "state_1",
            "value_1",
            "annotator_2",
            "state_2",
            "value_2",
            "conciliation_status",
        ]
    )
    for key, items in disagreements:
        writer.writerow(
            [
                *key,
                items[0].annotator_id,
                items[0].state,
                items[0].literal_value or "",
                items[1].annotator_id,
                items[1].state,
                items[1].literal_value or "",
                "open",
            ]
        )
    disagreement_bytes = output.getvalue().encode()

    states = Counter(item.state for item in ordered)
    annotators = Counter(item.annotator_id for item in ordered)
    comparable = sum(1 for items in grouped.values() if len(items) == 2)
    agreements = comparable - len(disagreements)
    agreement = "n/a" if comparable == 0 else f"{agreements / comparable:.4f}"
    summary_lines = [
        "# Resumen del conjunto oro",
        "",
        f"- Versión de herramienta: `{TOOL_VERSION}`",
        f"- Anotaciones: {len(ordered)}",
        f"- Unidades comparables: {comparable}",
        f"- Desacuerdos abiertos: {len(disagreements)}",
        f"- Tasa de acuerdo exacto: {agreement}",
        "",
        "## Estados",
        "",
        *(f"- `{key}`: {states[key]}" for key in sorted(states)),
        "",
        "## Anotadores",
        "",
        *(f"- `{key}`: {annotators[key]}" for key in sorted(annotators)),
        "",
    ]
    summary_bytes = "\n".join(summary_lines).encode()
    selection_bytes = _canonical_json(selection)
    outputs = {
        "gold-selection.json": selection_bytes,
        "gold-annotations.jsonl": annotation_bytes,
        "gold-disagreements.csv": disagreement_bytes,
        "summary.md": summary_bytes,
    }
    manifest = {
        "counts": {
            "annotations": len(ordered),
            "disagreements": len(disagreements),
            "pending": states["pending"],
        },
        "outputs": {name: _sha256(payload) for name, payload in sorted(outputs.items())},
        "selection_run_id": selection.get("run_id"),
        "tool_version": TOOL_VERSION,
    }
    outputs["run-manifest.json"] = _canonical_json(manifest)
    return outputs
