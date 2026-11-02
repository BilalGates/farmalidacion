from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_changes import query_cima_changes
from pharma_validator_api.data_origin import DataOrigin
from pharma_validator_api.maintenance_actions import CimaCapture, derive_for_events
from pharma_validator_api.maintenance_refresh import MaintenanceClient
from pharma_validator_api.maintenance_store import change_is_recorded, process_change_report
from pharma_validator_api.models import (
    BlockInstance,
    FieldValue,
    MaintenanceRun,
    TargetRecord,
)


class MaintenanceJobError(RuntimeError):
    pass


def _literal(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def _parse(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def _completed_days(session: Session) -> set[date]:
    completed = session.scalars(
        select(MaintenanceRun.requested_date).where(MaintenanceRun.status == "completed")
    ).all()
    days: set[date] = set()
    for item in completed:
        try:
            days.add(_parse(item))
        except ValueError:
            continue  # pasadas que no son un día, como el backfill de acciones
    return days


def next_pending_date(session: Session, *, start_date: date) -> date:
    completed_days = _completed_days(session)
    pending = start_date
    while pending in completed_days:
        pending += timedelta(days=1)
    return pending


def _attempt(session: Session, requested_date: str) -> int:
    return (
        session.scalar(
            select(func.max(MaintenanceRun.attempt)).where(
                MaintenanceRun.requested_date == requested_date
            )
        )
        or 0
    ) + 1


def _master_cn_index(session: Session) -> dict[str, tuple[str, ...]]:
    rows = session.execute(
        select(FieldValue.literal_value, BlockInstance.target_record_id)
        .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
        .join(TargetRecord, BlockInstance.target_record_id == TargetRecord.id)
        .where(
            FieldValue.field_name == "CODIGO_NACIONAL",
            FieldValue.literal_value.is_not(None),
            FieldValue.literal_value != "",
        )
    )
    candidates: dict[str, set[str]] = {}
    for cn, target_id in rows:
        candidates.setdefault(str(cn), set()).add(str(target_id))
    return {cn: tuple(sorted(target_ids)) for cn, target_ids in candidates.items()}


def _catalog_targets_by_registration(
    client: MaintenanceClient, master_by_cn: dict[str, tuple[str, ...]]
) -> dict[str, tuple[tuple[str, str], ...]]:
    """Match literal CN only when it is unique in both complete inventories."""
    cima_by_cn: dict[str, list[str]] = {}
    for row in client.all_presentations():
        cn, nregistro = row.get("cn"), row.get("nregistro")
        if isinstance(cn, str) and cn and isinstance(nregistro, str) and nregistro:
            cima_by_cn.setdefault(cn, []).append(nregistro)
    targets: dict[str, set[tuple[str, str]]] = {}
    for cn, registrations in cima_by_cn.items():
        master_candidates = master_by_cn.get(cn, ())
        if len(registrations) == 1 and len(master_candidates) == 1:
            targets.setdefault(registrations[0], set()).add((master_candidates[0], cn))
    return {registration: tuple(sorted(matches)) for registration, matches in targets.items()}


def run_one_day(
    session: Session,
    *,
    client: MaintenanceClient,
    day: date,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    data_origin: DataOrigin = DataOrigin.REAL,
) -> MaintenanceRun:
    requested = _literal(day)
    # A new invocation can only start after the shared maintenance lock is
    # released. Any older running attempt was interrupted by a worker restart.
    interrupted = session.scalars(
        select(MaintenanceRun).where(
            MaintenanceRun.requested_date == requested,
            MaintenanceRun.status == "running",
        )
    ).all()
    for previous in interrupted:
        previous.status = "failed"
        previous.error_detail = (
            "La consulta se interrumpió; el siguiente intento continúa "
            "con los avisos ya guardados."
        )
        previous.finished_at = now()
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
        master_by_cn = _master_cn_index(session)
        targets_by_registration: dict[str, tuple[tuple[str, str], ...]] = {}
        # Sin ningún CN maestro no puede existir un destino exacto. Evita
        # consultas CIMA adicionales; los avisos se guardan igualmente (D-040).
        if master_by_cn:
            targets_by_registration = _catalog_targets_by_registration(client, master_by_cn)
        new_changes = tuple(
            change for change in report.changes if not change_is_recorded(session, change)
        )
        report = replace(report, changes=new_changes)

        def save_progress(count: int) -> None:
            run.event_count = count
            session.commit()

        events = process_change_report(
            session,
            client=client,
            report=report,
            targets_by_registration=targets_by_registration,
            on_progress=save_progress,
        )
        underived = 0
        for event in events:
            # Captura nueva por evento: tras un rollback, las versiones que la
            # anterior recordaba ya no existen y no deben reutilizarse.
            capture = CimaCapture(session, client)
            try:
                derive_for_events(
                    session, events=[event], client=client, default_origin=data_origin,
                    capture=capture,
                )
                session.commit()
            except Exception:
                session.rollback()
                underived += 1
        run.status = "completed"
        run.event_count = len(events)
        unavailable = sum(
            "ft" in change.areas
            and change.nregistro in targets_by_registration
            and event.new_version_id is None
            for change, event in zip(report.changes, events, strict=True)
        )
        if unavailable:
            run.error_detail = (
                f"{unavailable} {'aviso' if unavailable == 1 else 'avisos'} de ficha técnica "
                "sin secciones disponibles en CIMA. "
                "Se conservaron los avisos, sin crear versiones ni alterar campos."
            )
        if underived:
            run.error_detail = (
                (run.error_detail + " " if run.error_detail else "")
                + f"{underived} {'aviso' if underived == 1 else 'avisos'} sin acciones derivadas; "
                "se completarán con el backfill de acciones."
            )
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
    data_origin: DataOrigin = DataOrigin.REAL,
) -> tuple[MaintenanceRun, ...]:
    completed_days = _completed_days(session)
    pending_days: list[date] = []
    day = start_date
    while day <= through_date:
        if day not in completed_days:
            pending_days.append(day)
        day += timedelta(days=1)
    if not pending_days:
        return ()
    # registroCambios(fecha) is cumulative through the moment of the request.
    # The earliest pending date therefore covers every later pending date.
    first = run_one_day(
        session, client=client, day=pending_days[0], data_origin=data_origin
    )
    runs = [first]
    coverage_started_at = datetime.now(UTC)
    for day in pending_days[1:]:
        requested = _literal(day)
        covered_at = coverage_started_at + timedelta(microseconds=len(runs))
        covered = MaintenanceRun(
            requested_date=requested,
            attempt=_attempt(session, requested),
            status="completed",
            event_count=0,
            source_sha256=first.source_sha256,
            error_detail=first.error_detail,
            started_at=covered_at,
            finished_at=covered_at,
        )
        session.add(covered)
        runs.append(covered)
    session.commit()
    return tuple(runs)
