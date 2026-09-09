"""Ejecuta una pasada recuperable de mantenimiento CIMA (DEV-704)."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta

from pharma_validator_api.cima_client import CimaClient
from pharma_validator_api.config import Settings
from pharma_validator_api.database import create_database_engine, create_session_factory
from pharma_validator_api.maintenance_job import run_pending_days


def day(value: str) -> date:
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use una fecha dd/mm/yyyy.") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Mantenimiento incremental diario CIMA")
    parser.add_argument("--start-date", required=True, type=day)
    parser.add_argument("--through-date", type=day, default=date.today() - timedelta(days=1))
    args = parser.parse_args()
    settings = Settings()
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
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
