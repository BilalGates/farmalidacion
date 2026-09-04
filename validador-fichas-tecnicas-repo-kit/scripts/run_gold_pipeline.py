"""Orquesta la secuencia posterior a la anotación del conjunto oro.

    anotaciones → verificación → comparación/conciliación → gold final
                → (extractor) → evaluación → métricas

Se detiene en la primera etapa que no pueda completarse honestamente. En
particular, **no evalúa un conjunto oro incompleto**: prefiere no producir
métricas antes que producir métricas que parecen válidas.

La etapa de extracción no se ejecuta aquí: exige un modelo aceptado (D-014) y
GPU. El orquestador consume las propuestas ya generadas si se le pasan, y si no
se detiene tras consolidar el conjunto oro, dejando claro qué falta.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pharma_validator_api.gold_annotations import (
    GoldAnnotation,
    GoldEvidence,
    build_gold_artifacts,
)
from pharma_validator_api.gold_completeness import (
    check_gold_completeness,
    render_report,
)
from pharma_validator_api.gold_evaluation import (
    ExtractorProposal,
    evaluate,
    render_evaluation,
)


def _read_annotations(paths: list[Path]) -> tuple[GoldAnnotation, ...]:
    annotations: list[GoldAnnotation] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload: dict[str, Any] = json.loads(line)
            evidence_payload = payload.pop("evidence", None)
            evidence = (
                GoldEvidence(**evidence_payload)
                if evidence_payload is not None
                else None
            )
            annotations.append(GoldAnnotation(evidence=evidence, **payload))
    return tuple(annotations)


def _read_sections(path: Path) -> dict[tuple[str, str], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        (str(item["document_version_hash"]), str(item["section_id"])): str(
            item["content"]
        )
        for item in payload["sections"]
    }


def _read_proposals(path: Path) -> tuple[ExtractorProposal, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        ExtractorProposal(
            unit_key=(
                str(item["nregistro"]),
                str(item["document_version_hash"]),
                str(item["block_type"]),
                int(item["occurrence"]),
                str(item["field_name"]),
            ),
            field_name=str(item["field_name"]),
            state=str(item["state"]),
            proposed_value=item.get("proposed_value"),
            evidence_admitted=bool(item["evidence_admitted"]),
            evidence_text=item.get("evidence_text"),
            parse_failed=bool(item.get("parse_failed", False)),
            latency_seconds=item.get("latency_seconds"),
        )
        for item in payload["proposals"]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--sections", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--proposals",
        type=Path,
        default=None,
        help="Propuestas del extractor ya verificadas. Sin ellas la evaluación no se ejecuta.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Modelo que produjo las propuestas. Obligatorio para evaluar.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Genera artefactos de un conjunto oro incompleto. Nunca evalúa.",
    )
    args = parser.parse_args()

    if args.output_dir.exists():
        parser.error(
            "El directorio de salida ya existe; nunca se sobrescribe una ejecución."
        )

    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    sections = _read_sections(args.sections)
    annotations = _read_annotations(list(args.annotations))

    # 1-2. Verificación y completitud.
    report = check_gold_completeness(selection, annotations, sections)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "gold-completeness.md").write_text(
        render_report(report), encoding="utf-8"
    )
    print(render_report(report))

    if not report.is_ready and not args.allow_incomplete:
        print(
            "\nEl conjunto oro no está listo. No se generan artefactos de cierre "
            "ni métricas. Use --allow-incomplete sólo para inspección."
        )
        return 1

    # 3-4. Artefactos contractuales del conjunto oro.
    artifacts = build_gold_artifacts(
        selection, annotations, sections, require_complete=not args.allow_incomplete
    )
    for name, content in artifacts.items():
        (args.output_dir / name).write_bytes(content)
    print(f"Artefactos del conjunto oro escritos en {args.output_dir}")

    # 5-7. Evaluación, sólo con conjunto oro cerrado y modelo atribuido.
    if args.proposals is None:
        print(
            "\nSin --proposals no hay evaluación. Falta ejecutar el extractor, "
            "que exige un modelo aceptado (D-014)."
        )
        return 0
    if not args.model:
        parser.error("--model es obligatorio para evaluar: la métrica debe ser atribuible.")
    if not report.is_ready:
        print("\nNo se evalúa un conjunto oro incompleto.")
        return 1

    evaluation = evaluate(
        _read_proposals(args.proposals), annotations, model=args.model
    )
    (args.output_dir / "evaluation.md").write_text(
        render_evaluation(evaluation), encoding="utf-8"
    )
    print(render_evaluation(evaluation))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
