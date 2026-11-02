"""Deriva las acciones de las novedades CIMA ya guardadas (backfill reanudable).

    python -m pharma_validator_api.cli.maintenance_actions backfill [--origin REAL|DEMO] [--limit N]

Consulta CIMA (una petición por CN, con el límite de ritmo del cliente) y toma
el valor *actual*, no el del día del aviso: la acción cita la respuesta
capturada y su fecha. Es idempotente: relanzarlo no duplica acciones y, tras un
corte, continúa por los avisos que aún no tienen acciones.

Usa el mismo bloqueo que la pasada diaria; no lo ejecutes a la vez que ella.
"""

from __future__ import annotations

import argparse
import json
import sys

from pharma_validator_api.config import get_settings
from pharma_validator_api.data_origin import DataOrigin
from pharma_validator_api.database import create_database_engine, create_session_factory
from pharma_validator_api.maintenance_actions import backfill_actions
from pharma_validator_api.maintenance_actions_api import build_cima_client, maintenance_lock_for
from pharma_validator_api.maintenance_lock import MaintenanceAlreadyRunning


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    backfill = sub.add_parser("backfill", help="Deriva acciones de los avisos guardados.")
    backfill.add_argument(
        "--origin", choices=["REAL", "DEMO"], default=None,
        help="Debe coincidir con APP_DATA_MODE: REAL y DEMO no se mezclan nunca.",
    )
    backfill.add_argument("--limit", type=int, default=None, help="Máximo de avisos a procesar.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    origin = DataOrigin(settings.data_mode)
    if args.origin is not None and args.origin.lower() != origin.value:
        parser.error(f"--origin {args.origin} no coincide con APP_DATA_MODE={settings.data_mode}.")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit debe ser positivo.")
    engine = create_database_engine(settings)
    try:
        with (
            maintenance_lock_for(settings),
            build_cima_client(settings) as client,
            create_session_factory(engine)() as session,
        ):
            result = backfill_actions(
                session, client=client, origin=origin, limit=args.limit,
                on_progress=lambda count: print(f"{count} avisos procesados", file=sys.stderr),
            )
    except MaintenanceAlreadyRunning as error:
        parser.exit(2, f"{error}\n")
    finally:
        engine.dispose()
    print(
        json.dumps(
            {
                "events_seen": result.events_seen,
                "events_processed": result.events_processed,
                "actions_created": result.actions_created,
                "stopped_early": result.stopped_early,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
