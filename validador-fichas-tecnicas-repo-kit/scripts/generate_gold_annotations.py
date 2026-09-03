"""Genera los artefactos offline de doble anotación de DEV-407."""

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


def _read_annotations(path: Path) -> tuple[GoldAnnotation, ...]:
    annotations: list[GoldAnnotation] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        payload: dict[str, Any] = json.loads(line)
        evidence_payload = payload.pop("evidence", None)
        evidence = (
            GoldEvidence(**evidence_payload) if evidence_payload is not None else None
        )
        try:
            annotations.append(GoldAnnotation(evidence=evidence, **payload))
        except TypeError as error:
            raise ValueError(
                f"Anotación inválida en línea {line_number}: {error}"
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
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--sections", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--close", action="store_true", help="Falla si existe alguna unidad pending."
    )
    args = parser.parse_args()

    if args.output_dir.exists():
        parser.error(
            "El directorio de salida ya existe; nunca se sobrescribe una ejecución."
        )
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    artifacts = build_gold_artifacts(
        selection,
        _read_annotations(args.annotations),
        _read_sections(args.sections),
        require_complete=args.close,
    )
    args.output_dir.mkdir(parents=True)
    for name, content in artifacts.items():
        (args.output_dir / name).write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
