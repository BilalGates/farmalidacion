from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_changes import CimaChange, CimaChangeReport
from pharma_validator_api.maintenance_refresh import (
    MaintenanceClient,
    RefreshResult,
    refresh_technical_sheet,
)
from pharma_validator_api.models import MaintenanceChangeEvent


def _event_id(source_sha256: str, change: CimaChange) -> str:
    identity = json.dumps(
        [source_sha256, change.nregistro, change.occurred_at, change.change_type, change.areas],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(identity).hexdigest()


def record_change(
    session: Session,
    *,
    report: CimaChangeReport,
    change: CimaChange,
    refresh: RefreshResult | None,
) -> MaintenanceChangeEvent:
    event_id = _event_id(report.source_sha256, change)
    existing = session.get(MaintenanceChangeEvent, event_id)
    if existing is not None:
        return existing
    event = MaintenanceChangeEvent(
        id=event_id,
        nregistro=change.nregistro,
        occurred_at_epoch=change.occurred_at,
        change_type=change.change_type,
        areas_json=json.dumps(change.areas, ensure_ascii=False, separators=(",", ":")),
        source_sha256=report.source_sha256,
        fetched_at=report.fetched_at,
        old_version_id=refresh.old_version_id if refresh else None,
        new_version_id=refresh.new_version_id if refresh else None,
        diff_json=(
            json.dumps(refresh.diff.as_dict(), ensure_ascii=False, sort_keys=True)
            if refresh and refresh.diff
            else None
        ),
        affected_field_count=len(refresh.marked_field_value_ids) if refresh else 0,
        recorded_at=datetime.now(UTC),
    )
    session.add(event)
    session.commit()
    return event


def process_change_report(
    session: Session,
    *,
    client: MaintenanceClient,
    report: CimaChangeReport,
) -> tuple[MaintenanceChangeEvent, ...]:
    events: list[MaintenanceChangeEvent] = []
    refreshed: dict[str, RefreshResult] = {}
    for change in report.changes:
        event_id = _event_id(report.source_sha256, change)
        existing = session.get(MaintenanceChangeEvent, event_id)
        if existing is not None:
            events.append(existing)
            continue
        refresh = None
        if change.affects_technical_sheet:
            refresh = refreshed.get(change.nregistro)
            if refresh is None:
                refresh = refresh_technical_sheet(
                    session, client=client, nregistro=change.nregistro
                )
                refreshed[change.nregistro] = refresh
        events.append(record_change(session, report=report, change=change, refresh=refresh))
    return tuple(events)


def list_changes(session: Session, *, limit: int = 100) -> Sequence[MaintenanceChangeEvent]:
    return session.scalars(
        select(MaintenanceChangeEvent)
        .order_by(
            MaintenanceChangeEvent.occurred_at_epoch.desc(), MaintenanceChangeEvent.id
        )
        .limit(limit)
    ).all()
