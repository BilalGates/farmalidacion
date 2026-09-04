"""Carga los maestros Excel reales en la base de datos del modo REAL.

    python -m pharma_validator_api.cli.ingest_real_data

No implementa ninguna ingesta: aplica migraciones y después delega en
`master_ingestion.ingest_masters`, que ya orquesta los importadores de Fase 3 en
su orden de dependencia. Existe para que arrancar en modo REAL no exija conocer
ni la URL de la base ni el orden de los importadores.

Es idempotente por diseño heredado: cada importador reutiliza su lote cuando el
`sha256` del fichero no ha cambiado, así que repetir la ejecución no duplica
nada y termina en segundos. La carga completa (~25 minutos) sólo ocurre la
primera vez, o cuando un fichero maestro cambia de contenido.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.config import get_settings
from pharma_validator_api.master_ingestion import MasterIngestionError, ingest_masters
from pharma_validator_api.models import TargetRecord

#: Raíz del repositorio: este módulo vive en backend/src/<paquete>/cli/.
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RAW_DIRECTORY = REPOSITORY_ROOT / "data" / "reference" / "raw"
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"


def _upgrade_schema(database_url: str) -> None:
    """Deja el esquema al día antes de importar.

    Se hace aquí y no en un paso previo del script de arranque para que el
    comando sea utilizable por sí solo sobre una base que todavía no existe.
    """
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL SQLAlchemy destino. Por defecto, APP_DATABASE_URL.",
    )
    parser.add_argument(
        "--raw-directory",
        type=Path,
        default=DEFAULT_RAW_DIRECTORY,
        help="Directorio con los maestros .xlsx.",
    )
    parser.add_argument(
        "--source-version",
        default=None,
        help="Etiqueta de versión de la entrega, registrada en cada lote.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    database_url = arguments.database_url or get_settings().database_url

    if not arguments.raw_directory.is_dir():
        print(
            f"error: no existe el directorio de maestros {arguments.raw_directory}",
            file=sys.stderr,
        )
        return 2

    print(f"Destino: {database_url}")
    print("Aplicando migraciones ...", flush=True)
    _upgrade_schema(database_url)

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            report = ingest_masters(
                session,
                arguments.raw_directory,
                source_version=arguments.source_version,
            )
            total = session.scalar(select(func.count()).select_from(TargetRecord)) or 0
    except MasterIngestionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        engine.dispose()

    for item in report.sources:
        state = "reutilizado" if item.skipped_as_duplicate else "importado"
        print(f"[{item.status:>9}] {item.key} ({state}) — {item.filename}")

    if not report.ok:
        failed = ", ".join(item.key for item in report.failed)
        print(f"FALLO en: {failed}", file=sys.stderr)
        return 1

    print(f"\nRegistros en la base: {total:,}".replace(",", "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
