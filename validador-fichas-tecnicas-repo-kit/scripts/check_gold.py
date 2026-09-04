"""Comprueba la completitud estructural del conjunto oro.

Uso previsto durante la campaña de anotación: responde en cualquier momento
cuánto falta y si el conjunto oro puede ya alimentar la evaluación del
extractor. No evalúa calidad clínica.

Código de salida 0 si el conjunto oro está listo, 1 si no lo está. Así puede
usarse como puerta en CI o antes de lanzar la evaluación.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pharma_validator_api.gold_annotations import GoldAnnotation, GoldEvidence
from pharma_validator_api.gold_completeness import (
    check_gold_completeness,
    render_report,
)


def _read_annotations(paths: list[Path]) -> tuple[GoldAnnotation, ...]:
    """Lee uno o varios JSONL. Cada anotador entrega el suyo por separado."""
    annotations: list[GoldAnnotation] = []
    for path in paths:
        if not path.exists():
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            payload: dict[str, Any] = json.loads(line)
            evidence_payload = payload.pop("evidence", None)
            evidence = (
                GoldEvidence(**evidence_payload)
                if evidence_payload is not None
                else None
            )
            try:
                annotations.append(GoldAnnotation(evidence=evidence, **payload))
            except TypeError as error:
                raise ValueError(
                    f"{path.name} línea {line_number}: anotación inválida: {error}"
                ) from error
    return tuple(annotations)


def _read_sections(path: Path) -> dict[tuple[str, str], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        (str(item["document_version_hash"]), str(item["section_id"])): str(
            item["content"]
        )
        for item in payload["sections"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--sections", type=Path, required=True)
    parser.add_argument(
        "--annotations",
        type=Path,
        nargs="*",
        default=[],
        help="Ficheros JSONL de anotación (uno por anotador).",
    )
    parser.add_argument(
        "--expected-units-per-document",
        type=int,
        default=None,
        help="Alcance de campos acordado por ficha. Sin él no se detecta un campo que nadie anotó.",
    )
    parser.add_argument("--json", action="store_true", help="Salida en JSON.")
    args = parser.parse_args()

    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    report = check_gold_completeness(
        selection,
        _read_annotations(list(args.annotations)),
        _read_sections(args.sections),
        expected_units_per_document=args.expected_units_per_document,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "expected_documents": report.expected_documents,
                    "annotated_documents": report.annotated_documents,
                    "expected_units": report.expected_units,
                    "completed_units": report.completed_units,
                    "pending_units": report.pending_units,
                    "single_annotator_units": report.single_annotator_units,
                    "open_disagreements": report.open_disagreements,
                    "progress": report.progress,
                    "annotators": [
                        {
                            "annotator_id": item.annotator_id,
                            "finished_units": item.finished_units,
                            "pending_units": item.pending_units,
                            "documents_touched": item.documents_touched,
                        }
                        for item in report.annotators
                    ],
                    "structural_errors": list(report.structural_errors),
                    "missing_evidence": list(report.missing_evidence),
                    "documents_without_annotations": list(
                        report.documents_without_annotations
                    ),
                    "is_ready": report.is_ready,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(render_report(report))
    return 0 if report.is_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
