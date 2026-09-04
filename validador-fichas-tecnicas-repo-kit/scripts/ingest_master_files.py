#!/usr/bin/env python3
"""Carga los maestros Excel reales en la base de datos usando los importadores de Fase 3.

Este script no implementa lógica de importación: orquesta los importadores que
ya existen (`catalog_importer`, `active_ingredient_importer`,
`medication_importer`, `specialty_importer`) contra una base de datos real, que
es la pieza que faltaba para que la aplicación pudiera mostrar datos.

El orden importa: medicamentos resuelven principios activos y especialidades
resuelven medicamentos, de modo que invertirlo produciría huérfanos.

Los importadores son idempotentes por lote: repetir la ejecución sobre el mismo
fichero no duplica datos, devuelve el lote existente.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from pharma_validator_api.active_ingredient_importer import (  # noqa: E402
    SOURCE_FILENAME as ACTIVE_INGREDIENT_FILENAME,
)
from pharma_validator_api.active_ingredient_importer import (  # noqa: E402
    import_active_ingredients,
)
from pharma_validator_api.catalog_importer import CATALOG_FILENAME, import_catalog  # noqa: E402
from pharma_validator_api.medication_importer import (  # noqa: E402
    SOURCE_FILENAME as MEDICATION_FILENAME,
)
from pharma_validator_api.medication_importer import import_medications  # noqa: E402
from pharma_validator_api.models import Base  # noqa: E402
from pharma_validator_api.specialty_importer import (  # noqa: E402
    SOURCE_FILENAME as SPECIALTY_FILENAME,
)
from pharma_validator_api.specialty_importer import import_specialties  # noqa: E402

DEFAULT_DATABASE_URL = "sqlite:///./data/local/validator.db"
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "reference" / "raw"


@dataclass(frozen=True)
class Step:
    """Un importador y el fichero que consume."""

    key: str
    filename: str
    run: Callable[..., Any]


#: El orden es una dependencia real, no una preferencia: los medicamentos
#: enlazan con principios activos ya presentes y las especialidades con
#: medicamentos ya presentes.
STEPS: tuple[Step, ...] = (
    Step("catalogo", CATALOG_FILENAME, import_catalog),
    Step("principios_activos", ACTIVE_INGREDIENT_FILENAME, import_active_ingredients),
    Step("medicamentos", MEDICATION_FILENAME, import_medications),
    Step("especialidades", SPECIALTY_FILENAME, import_specialties),
)


def _describe(result: object) -> str:
    fields = (
        "status",
        "created",
        "imported_fields",
        "source_rows",
        "occurrences",
        "values",
        "quarantined_rows",
        "orphan_parent_identifiers",
        "diagnostics",
    )
    parts = [
        f"{name}={getattr(result, name)}" for name in fields if hasattr(result, name)
    ]
    return " ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument(
        "--source-version",
        default=None,
        help="Etiqueta de versión de la entrega de maestros, si se conoce.",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=[step.key for step in STEPS],
        help="Ejecuta sólo los pasos indicados (repetible).",
    )
    args = parser.parse_args(argv)

    engine = create_engine(args.database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    selected = [step for step in STEPS if not args.only or step.key in args.only]
    missing = [
        step.filename
        for step in selected
        if not (args.raw_dir / step.filename).is_file()
    ]
    if missing:
        # Se aborta antes de escribir nada: una carga parcial silenciosa dejaría
        # huérfanos que después parecerían incidencias de los datos.
        for name in missing:
            print(f"FALTA el fichero de origen: {name}", file=sys.stderr)
        return 1

    for step in selected:
        source_path = args.raw_dir / step.filename
        print(f"[{step.key}] importando {step.filename} ...", flush=True)
        with factory() as session:
            result = step.run(session, source_path, source_version=args.source_version)
            session.commit()
        print(f"[{step.key}] {_describe(result)}", flush=True)

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
