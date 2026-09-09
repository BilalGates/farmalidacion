from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_changes import query_cima_changes
from pharma_validator_api.maintenance_refresh import MaintenanceClient
from pharma_validator_api.maintenance_store import process_change_report
from pharma_validator_api.models import MaintenanceRun, SourceDocument


class MaintenanceJobError(RuntimeError):
    pass


def _literal(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def _parse(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def next_pending_date(session: Session, *, start_date: date) -> date:
    completed = session.scalars(
        select(MaintenanceRun.requested_date).where(MaintenanceRun.status == "completed")
    ).all()
    if not completed:
        return start_date
    return max(_parse(item) for item in completed) + timedelta(days=1)


def _attempt(session: Session, requested_date: str) -> int:
    return (
        session.scalar(
            select(func.max(MaintenanceRun.attempt)).where(
                MaintenanceRun.requested_date == requested_date
            )
        )
        or 0
    ) + 1


def run_one_day(
    session: Session,
    *,
    client: MaintenanceClient,
    day: date,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> MaintenanceRun:
    requested = _literal(day)
    run = MaintenanceRun(
        requested_date=requested,
        attempt=_attempt(session, requested),
        status="running",
        event_count=0,
        source_sha256=None,
        error_detail=None,
        started_at=now(),
        finished_at=None,
    )
    session.add(run)
    session.commit()
    try:
        report = query_cima_changes(client, date=requested)
        tracked = set(
            session.scalars(
                select(SourceDocument.name).where(
                    SourceDocument.source_type == "cima_document_type_1"
                )
            ).all()
        )
        if tracked:
            # El piloto mantiene su corpus, no descarga silenciosamente todo el
            # inventario CIMA cuando registroCambios devuelve cambios globales.
            report = replace(
                report,
                changes=tuple(item for item in report.changes if item.nregistro in tracked),
            )
        events = process_change_report(session, client=client, report=report)
        run.status = "completed"
        run.event_count = len(events)
        run.source_sha256 = report.source_sha256
        run.finished_at = now()
        session.commit()
        return run
    except Exception as error:
        session.rollback()
        stored = session.get(MaintenanceRun, run.id)
        assert stored is not None
        stored.status = "failed"
        stored.error_detail = f"{type(error).__name__}: {error}"[:2000]
        stored.finished_at = now()
        session.commit()
        raise MaintenanceJobError(
            f"Mantenimiento CIMA fallido para {requested}; intento {stored.attempt}."
        ) from error


def run_pending_days(
    session: Session,
    *,
    client: MaintenanceClient,
    start_date: date,
    through_date: date,
) -> tuple[MaintenanceRun, ...]:
    pending = next_pending_date(session, start_date=start_date)
    if through_date < pending:
        return ()
    runs: list[MaintenanceRun] = []
    while pending <= through_date:
        runs.append(run_one_day(session, client=client, day=pending))
        pending += timedelta(days=1)
    return tuple(runs)
