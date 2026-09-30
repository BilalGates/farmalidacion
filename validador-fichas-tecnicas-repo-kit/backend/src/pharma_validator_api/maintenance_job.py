from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_changes import query_cima_changes
from pharma_validator_api.maintenance_refresh import MaintenanceClient, MaintenanceRefreshError
from pharma_validator_api.maintenance_store import process_change_report
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
    return {_parse(item) for item in completed}


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


def _catalog_targets_for_change(
    session: Session,
    *,
    client: MaintenanceClient,
    nregistro: str,
    master_by_cn: dict[str, tuple[str, ...]],
) -> tuple[tuple[str, str], ...]:
    """Resolve a notice only when CIMA confirms a unique literal CN match."""
    try:
        payload = client.medication(nregistro=nregistro, use_cache=False).json()
    except (ValueError, json.JSONDecodeError) as error:
        raise MaintenanceRefreshError(
            f"{nregistro}: los metadatos CIMA no contienen JSON válido."
        ) from error
    presentations = payload.get("presentaciones") if isinstance(payload, dict) else None
    if not isinstance(presentations, list):
        raise MaintenanceRefreshError(f"{nregistro}: presentaciones CIMA incompatibles.")

    cns: list[str] = []
    for row in presentations:
        if isinstance(row, dict):
            cn = row.get("cn")
            if isinstance(cn, str) and cn:
                cns.append(cn)
    targets: set[tuple[str, str]] = set()
    for cn in set(cns):
        master_candidates = master_by_cn.get(cn, ())
        if len(master_candidates) != 1 or cns.count(cn) != 1:
            continue
        try:
            exact = client.presentation(cn=cn, use_cache=False).json()
        except (ValueError, json.JSONDecodeError) as error:
            raise MaintenanceRefreshError(
                f"{nregistro}/{cn}: la respuesta de presentación no es JSON válido."
            ) from error
        if (
            isinstance(exact, dict)
            and exact.get("cn") == cn
            and exact.get("nregistro") == nregistro
        ):
            targets.add((master_candidates[0], cn))
    return tuple(sorted(targets))


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
        master_by_cn = _master_cn_index(session)
        targets_by_registration: dict[str, tuple[tuple[str, str], ...]] = {}
        relevant_changes = []
        # Sin ningún CN maestro no puede existir un destino exacto. Evita
        # consultas CIMA adicionales y registra igualmente la pasada del día.
        if master_by_cn:
            for change in report.changes:
                matches = _catalog_targets_for_change(
                    session,
                    client=client,
                    nregistro=change.nregistro,
                    master_by_cn=master_by_cn,
                )
                if matches:
                    relevant_changes.append(change)
                    targets_by_registration[change.nregistro] = matches
        report = replace(report, changes=tuple(relevant_changes))
        events = process_change_report(
            session,
            client=client,
            report=report,
            targets_by_registration=targets_by_registration,
        )
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
    completed_days = _completed_days(session)
    pending = start_date
    runs: list[MaintenanceRun] = []
    while pending <= through_date:
        if pending not in completed_days:
            runs.append(run_one_day(session, client=client, day=pending))
        pending += timedelta(days=1)
    return tuple(runs)
