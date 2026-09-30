"""Ejecuta una pasada recuperable de mantenimiento CIMA (DEV-704)."""

from __future__ import annotations

import argparse
import json
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from pharma_validator_api.cima_client import CimaClient
from pharma_validator_api.config import Settings
from pharma_validator_api.database import create_database_engine, create_session_factory
from pharma_validator_api.maintenance_job import run_pending_days
from sqlalchemy.engine import make_url

from scripts.maintenance_lock import MaintenanceAlreadyRunning, maintenance_lock


def day(value: str) -> date:
    try:
        return datetime.strptime(value, "%d/%m/%Y").replace(tzinfo=UTC).date()
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use una fecha dd/mm/yyyy.") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Mantenimiento incremental diario CIMA")
    parser.add_argument("--start-date", required=True, type=day)
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    parser.add_argument("--through-date", type=day, default=yesterday)
    args = parser.parse_args()
    settings = Settings()
    if settings.data_mode != "real":
        parser.error("Configure APP_DATA_MODE=real antes de ejecutar mantenimiento CIMA.")
    url = make_url(settings.database_url)
    database_path = url.database
    if (
        url.get_backend_name() == "sqlite"
        and database_path not in (None, ":memory:")
        and not Path(database_path).is_file()
    ):
        parser.error("La base SQLite REAL configurada no existe; cargue los maestros primero.")
    lock: AbstractContextManager[None] = (
        maintenance_lock(Path(database_path))
        if url.get_backend_name() == "sqlite" and database_path not in (None, ":memory:")
        else nullcontext()
    )
    try:
        with lock:
            engine = create_database_engine(settings)
            factory = create_session_factory(engine)
            try:
                with CimaClient(
                    base_url=settings.cima_base_url,
                    cache_dir=settings.cima_cache_dir,
                    timeout_seconds=settings.cima_timeout_seconds,
                    requests_per_second=settings.cima_requests_per_second,
                    max_retries=settings.cima_max_retries,
                    backoff_seconds=settings.cima_backoff_seconds,
                    max_retry_delay_seconds=settings.cima_max_retry_delay_seconds,
                ) as client, factory() as session:
                    runs = run_pending_days(
                        session,
                        client=client,
                        start_date=args.start_date,
                        through_date=args.through_date,
                    )
            finally:
                engine.dispose()
    except MaintenanceAlreadyRunning as error:
        parser.exit(2, f"{error}\n")
    print(
        json.dumps(
            {
                "runs": len(runs),
                "dates": [run.requested_date for run in runs],
                "events": sum(run.event_count for run in runs),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
