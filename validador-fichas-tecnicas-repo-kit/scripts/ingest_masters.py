#!/usr/bin/env python3
"""Importa los maestros Excel existentes a la base de datos configurada.

Punto de entrada ejecutable de la Fase 3: aplica los importadores ya existentes
en orden de dependencia sobre una base migrada, y emite un informe. No
reimplementa ninguna ingesta.

Uso típico:

    python scripts/ingest_masters.py --database-url postgresql+psycopg://...
    python scripts/ingest_masters.py --only catalog --only active_ingredients
    python scripts/ingest_masters.py --json > artifacts/ingesta.json

La reejecución es segura: cada importador reutiliza su lote cuando el contenido
del fichero no ha cambiado, así que no duplica datos.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIRECTORY = ROOT / "data" / "reference" / "raw"

# El backend se importa desde `backend/src`, que no está en la ruta cuando el
# script se ejecuta directamente y el paquete no está instalado. Los imports van
# dentro de las funciones a propósito: en el nivel de módulo, el ordenador de
# imports los subiría por encima de esta preparación de `sys.path` y el script
# dejaría de arrancar sin instalación editable.
def _prepare_import_path() -> None:
    source = str(ROOT / "backend" / "src")
    if source not in sys.path:
        sys.path.insert(0, source)


def _master_keys() -> list[str]:
    _prepare_import_path()
    from pharma_validator_api.master_ingestion import MASTER_SOURCES

    return [source.key for source in MASTER_SOURCES]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL SQLAlchemy destino. Por defecto, la de la configuración (APP_DATABASE_URL).",
    )
    parser.add_argument(
        "--raw-directory",
        type=Path,
        default=DEFAULT_RAW_DIRECTORY,
        help="Directorio con los ficheros maestros .xlsx.",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=_master_keys(),
        help="Importa sólo el maestro indicado. Repetible. El orden de dependencia se respeta.",
    )
    parser.add_argument(
        "--source-version",
        default=None,
        help="Etiqueta de versión de los ficheros de origen, registrada en el lote.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emite el informe como JSON en lugar de texto legible.",
    )
    return parser


def render_text(report: object, database_url: str) -> str:
    lines = [f"Destino: {database_url}", ""]
    for item in report.sources:  # type: ignore[attr-defined]
        state = "reutilizado" if item.skipped_as_duplicate else "importado"
        lines.append(f"[{item.status:>9}] {item.key} ({state}) — {item.filename}")
        lines.append(f"             lote {item.batch_id}  sha256 {item.content_hash[:16]}…")
        if item.metrics:
            rendered = ", ".join(f"{name}={value}" for name, value in sorted(item.metrics.items()))
            lines.append(f"             {rendered}")
    failed = report.failed  # type: ignore[attr-defined]
    lines.append("")
    if failed:
        lines.append(f"FALLO en: {', '.join(item.key for item in failed)}")
    else:
        lines.append("Todos los maestros se han importado correctamente.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    _prepare_import_path()
    from pharma_validator_api.config import get_settings
    from pharma_validator_api.master_ingestion import (
        MasterIngestionError,
        ingest_masters,
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    database_url = arguments.database_url or get_settings().database_url
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            report = ingest_masters(
                session,
                arguments.raw_directory,
                only=arguments.only,
                source_version=arguments.source_version,
            )
    except MasterIngestionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        engine.dispose()

    if arguments.json:
        payload = {
            "database_url": database_url,
            "sources": [asdict(item) for item in report.sources],
            "ok": report.ok,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_text(report, database_url))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
