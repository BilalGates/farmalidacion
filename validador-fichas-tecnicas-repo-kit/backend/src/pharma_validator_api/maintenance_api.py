from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.maintenance_store import list_changes
from pharma_validator_api.models import MaintenanceChangeEvent, MaintenanceRun
from pharma_validator_api.records import SessionDependency

router = APIRouter(prefix="/maintenance", tags=["mantenimiento"])


def _summary(row: MaintenanceChangeEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "nregistro": row.nregistro,
        "occurred_at_epoch": row.occurred_at_epoch,
        "change_type": row.change_type,
        "areas": json.loads(row.areas_json),
        "old_version_id": row.old_version_id,
        "new_version_id": row.new_version_id,
        "affected_field_count": row.affected_field_count,
        "has_diff": row.diff_json is not None,
        "recorded_at": row.recorded_at.isoformat(),
    }


@router.get("/changes")
def changes(session: SessionDependency, limit: int = 100) -> list[dict[str, Any]]:
    if not 1 <= limit <= 500:
        raise ApplicationError("El límite debe estar entre 1 y 500.", status_code=400)
    return [_summary(row) for row in list_changes(session, limit=limit)]


@router.get("/changes/{event_id}")
def change_detail(event_id: str, session: SessionDependency) -> dict[str, Any]:
    row = session.get(MaintenanceChangeEvent, event_id)
    if row is None:
        raise ApplicationError("Novedad CIMA no encontrada.", status_code=404)
    return {
        **_summary(row),
        "source_sha256": row.source_sha256,
        "fetched_at": row.fetched_at,
        "diff": json.loads(row.diff_json) if row.diff_json else None,
    }


@router.get("/runs")
def runs(session: SessionDependency, limit: int = 30) -> list[dict[str, Any]]:
    if not 1 <= limit <= 200:
        raise ApplicationError("El límite debe estar entre 1 y 200.", status_code=400)
    rows = session.scalars(
        select(MaintenanceRun).order_by(MaintenanceRun.started_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "requested_date": row.requested_date,
            "attempt": row.attempt,
            "status": row.status,
            "event_count": row.event_count,
            "error_detail": row.error_detail,
            "started_at": row.started_at.isoformat(),
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        }
        for row in rows
    ]
