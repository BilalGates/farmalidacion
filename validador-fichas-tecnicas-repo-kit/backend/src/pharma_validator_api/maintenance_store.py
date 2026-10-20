from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_changes import CimaChange, CimaChangeReport
from pharma_validator_api.maintenance_refresh import (
    MaintenanceClient,
    RefreshResult,
    refresh_technical_sheet,
)
from pharma_validator_api.models import (
    DocumentRecordLink,
    MaintenanceChangeEvent,
    MaintenanceChangeEventTarget,
)


def _event_id(change: CimaChange) -> str:
    identity = json.dumps(
        [change.nregistro, change.occurred_at, change.change_type, change.areas],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(identity).hexdigest()


def _existing_event(session: Session, change: CimaChange) -> MaintenanceChangeEvent | None:
    """Reconoce también los IDs antiguos, que incluían el hash de la respuesta.

    registroCambios devuelve cambios *desde* la fecha pedida; el mismo aviso
    puede aparecer en respuestas distintas y sus hashes no tienen por qué ser
    iguales. La identidad del aviso depende de su contenido, no de la página.
    """
    current = session.get(MaintenanceChangeEvent, _event_id(change))
    if current is not None:
        return current
    return session.scalar(select(MaintenanceChangeEvent).where(
        MaintenanceChangeEvent.nregistro == change.nregistro,
        MaintenanceChangeEvent.occurred_at_epoch == change.occurred_at,
        MaintenanceChangeEvent.change_type == change.change_type,
        MaintenanceChangeEvent.areas_json == json.dumps(
            change.areas, ensure_ascii=False, separators=(",", ":")
        ),
    ).limit(1))


def change_is_recorded(session: Session, change: CimaChange) -> bool:
    return _existing_event(session, change) is not None


def record_change(
    session: Session,
    *,
    report: CimaChangeReport,
    change: CimaChange,
    refresh: RefreshResult | None,
    catalog_targets: Sequence[tuple[str, str]] = (),
) -> MaintenanceChangeEvent:
    existing = _existing_event(session, change)
    event_id = existing.id if existing else _event_id(change)
    event = existing or MaintenanceChangeEvent(
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
    if existing is None:
        session.add(event)
        session.flush()
    for target_record_id, cn in catalog_targets:
        identity = f"maintenance-target:{event_id}:{target_record_id}:{cn}"
        link_id = str(uuid5(NAMESPACE_URL, identity))
        if session.get(MaintenanceChangeEventTarget, link_id) is None:
            session.add(
                MaintenanceChangeEventTarget(
                    id=link_id,
                    event_id=event_id,
                    target_record_id=target_record_id,
                    national_code=cn,
                )
            )
        if event.new_version_id:
            cima_link_identity = f"cima-exact-cn-v1:{event.new_version_id}:{target_record_id}:{cn}"
            cima_link_id = str(uuid5(NAMESPACE_URL, cima_link_identity))
            if session.get(DocumentRecordLink, cima_link_id) is None:
                session.add(
                    DocumentRecordLink(
                        id=cima_link_id,
                        document_version_id=event.new_version_id,
                        target_record_id=target_record_id,
                        link_type="exact_national_code_v1",
                    )
                )
    session.commit()
    return event


def process_change_report(
    session: Session,
    *,
    client: MaintenanceClient,
    report: CimaChangeReport,
    targets_by_registration: dict[str, tuple[tuple[str, str], ...]] | None = None,
) -> tuple[MaintenanceChangeEvent, ...]:
    events: list[MaintenanceChangeEvent] = []
    refreshed: dict[str, RefreshResult] = {}
    targets_by_registration = targets_by_registration or {}
    for change in report.changes:
        existing = _existing_event(session, change)
        if existing is not None:
            record_change(
                session,
                report=report,
                change=change,
                refresh=None,
                catalog_targets=targets_by_registration.get(change.nregistro, ()),
            )
            continue
        refresh = None
        if change.affects_technical_sheet:
            refresh = refreshed.get(change.nregistro)
            if refresh is None:
                refresh = refresh_technical_sheet(
                    session, client=client, nregistro=change.nregistro
                )
                refreshed[change.nregistro] = refresh
        events.append(
            record_change(
                session,
                report=report,
                change=change,
                refresh=refresh,
                catalog_targets=targets_by_registration.get(change.nregistro, ()),
            )
        )
    return tuple(events)


def list_changes(session: Session, *, limit: int = 100) -> Sequence[MaintenanceChangeEvent]:
    return session.scalars(
        select(MaintenanceChangeEvent)
        .order_by(MaintenanceChangeEvent.occurred_at_epoch.desc(), MaintenanceChangeEvent.id)
        .limit(limit)
    ).all()
