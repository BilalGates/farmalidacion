"""Materializa las entradas del conjunto oro desde el corpus de DEV-208.

Produce dos ficheros que la anotación humana necesita y que hoy había que
construir a mano:

- `gold-selection.json`: la selección reproducible de 20 fichas
  (`gold-selection-v1`, semilla GOLD-001), en el formato canónico que consume
  `scripts/generate_gold_annotations.py`.
- `gold-sections.json`: el contenido literal de cada sección de esas 20 fichas,
  tal cual se almacenó, para que la evidencia se cite por desplazamientos sobre
  la cadena canónica exigida por el contrato.

El corpus se abre en solo lectura. Este script no descarga nada, no modifica el
corpus y no crea anotaciones: no decide nada clínico.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pharma_validator_api.gold_selection import GoldCandidate, select_gold_set


def _load_universe(manifest_path: Path) -> tuple[GoldCandidate, ...]:
    """Construye el universo elegible desde el manifiesto del corpus.

    La versión documental es el `content_sha256` del artefacto `metadata`, la
    misma convención ya verificada para el `run_id` estable del contrato. Usar
    otro artefacto produciría un universo distinto y, con él, otra selección.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates: list[GoldCandidate] = []
    for document in manifest["documents"]:
        version = next(
            artifact["content_sha256"]
            for artifact in document["artifacts"]
            if artifact["artifact_role"] == "metadata"
        )
        candidates.append(
            GoldCandidate(
                nregistro=str(document["nregistro"]),
                document_version_hash=str(version),
            )
        )
    return tuple(candidates)


def _load_sections(
    corpus_dir: Path, nregistro: str, document_version_hash: str
) -> list[dict[str, Any]]:
    """Lee las secciones literales de una ficha técnica del corpus.

    `contenido` se conserva exactamente como se almacenó: es HTML con entidades
    y espacios originales. No se desescapa, no se normaliza y no se extrae
    texto, porque los desplazamientos de evidencia se verifican contra esta
    misma cadena.
    """
    path = corpus_dir / "artifacts" / f"{nregistro}-ft.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        # CIMA responde con `{"error": ...}` cuando no publica secciones para
        # ese registro. Es un hecho del corpus, no una sección vacía: se
        # devuelve sin secciones y el anotador lo verá como ficha sin contenido.
        return []
    sections: list[dict[str, Any]] = []
    for section in payload:
        # Los encabezados de bloque ("4. DATOS CLÍNICOS") existen sin
        # `contenido`. No se inventa una cadena vacía indistinguible de una
        # sección realmente vacía: se marca la ausencia y no se ofrece como
        # superficie citable.
        content = section.get("contenido")
        sections.append(
            {
                "document_version_hash": document_version_hash,
                "nregistro": nregistro,
                "section_id": str(section["seccion"]),
                "title": str(section.get("titulo", "")),
                "content": str(content) if content is not None else None,
                "has_content": content is not None,
            }
        )
    return sections


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="Directorio del corpus DEV-208 (contiene manifest.json y artifacts/).",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.output_dir.exists():
        parser.error(
            "El directorio de salida ya existe; nunca se sobrescribe una ejecución."
        )

    universe = _load_universe(args.corpus / "manifest.json")
    selection = select_gold_set(universe)

    sections: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in selection.items:
        found = _load_sections(args.corpus, item.nregistro, item.document_version_hash)
        if not found:
            missing.append(item.nregistro)
        sections.extend(found)

    args.output_dir.mkdir(parents=True)
    (args.output_dir / "gold-selection.json").write_text(
        json.dumps(selection.as_dict(), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    # `generate_gold_annotations.py` sólo verifica evidencia contra secciones
    # con contenido literal. Las secciones sin `contenido` se conservan en un
    # listado aparte para que el anotador sepa que existen, sin convertirlas en
    # superficie citable con una cadena vacía inventada.
    citable = [item for item in sections if item["has_content"]]
    headers = [
        {key: value for key, value in item.items() if key != "content"}
        for item in sections
        if not item["has_content"]
    ]
    (args.output_dir / "gold-sections.json").write_text(
        json.dumps(
            {"sections": citable, "sections_without_content": headers},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"run_id: {selection.run_id}")
    print(f"fichas seleccionadas: {len(selection.items)}")
    print(f"secciones citables: {len(citable)}")
    print(f"secciones sin contenido: {len(headers)}")
    if missing:
        # Una ficha sin artefacto de FT es un defecto del corpus, no algo que
        # se pueda suplir aquí. Se informa y no se sustituye por otra ficha:
        # sustituirla rompería la reproducibilidad de la selección.
        print(f"AVISO: sin artefacto de ficha técnica: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
