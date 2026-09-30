from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from pharma_validator_api.cima_client import CimaClient
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.maintenance_job import MaintenanceJobError, run_one_day
from pharma_validator_api.maintenance_store import list_changes
from pharma_validator_api.models import (
    MaintenanceChangeEvent,
    MaintenanceChangeEventTarget,
    MaintenanceRun,
    MedicationCatalogIdentity,
)
from pharma_validator_api.records import SessionDependency

router = APIRouter(prefix="/maintenance", tags=["mantenimiento"])


class RunRead(BaseModel):
    id: str
    requested_date: str
    attempt: int
    status: str
    event_count: int
    error_detail: str | None
    started_at: str
    finished_at: str | None


def _summary(session: SessionDependency, row: MaintenanceChangeEvent) -> dict[str, Any]:
    targets = session.execute(
        select(
            MedicationCatalogIdentity.id,
            MedicationCatalogIdentity.display_name,
            MedicationCatalogIdentity.identity_type,
            MaintenanceChangeEventTarget.national_code,
        )
        .join(
            MaintenanceChangeEventTarget,
            MaintenanceChangeEventTarget.target_record_id
            == MedicationCatalogIdentity.target_record_id,
        )
        .where(MaintenanceChangeEventTarget.event_id == row.id)
        .order_by(MedicationCatalogIdentity.display_name, MedicationCatalogIdentity.id)
    ).all()
    return {
        "id": row.id,
        "nregistro": row.nregistro,
        "occurred_at_epoch": row.occurred_at_epoch,
        "change_type": row.change_type,
        "areas": json.loads(row.areas_json),
        "old_version_id": row.old_version_id,
        "new_version_id": row.new_version_id,
        "affected_field_count": row.affected_field_count,
        "catalog_targets": [
            {
                "identity_id": identity_id,
                "display_name": display_name,
                "identity_type": identity_type,
                "national_code": national_code,
            }
            for identity_id, display_name, identity_type, national_code in targets
        ],
        "has_diff": row.diff_json is not None,
        "recorded_at": row.recorded_at.isoformat(),
    }


@router.get("/changes")
def changes(session: SessionDependency, limit: int = 100) -> list[dict[str, Any]]:
    if not 1 <= limit <= 500:
        raise ApplicationError("El límite debe estar entre 1 y 500.", status_code=400)
    return [_summary(session, row) for row in list_changes(session, limit=limit)]


@router.get("/changes/{event_id}")
def change_detail(event_id: str, session: SessionDependency) -> dict[str, Any]:
    row = session.get(MaintenanceChangeEvent, event_id)
    if row is None:
        raise ApplicationError("Novedad CIMA no encontrada.", status_code=404)
    return {
        **_summary(session, row),
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


@router.post("/run", response_model=RunRead)
def run_yesterday(request: Request, session: SessionDependency) -> dict[str, Any]:
    """Consulta el último día cerrado de CIMA y guarda sólo cambios del catálogo."""
    settings = request.app.state.settings
    day = date.today() - timedelta(days=1)
    try:
        with CimaClient(
            base_url=settings.cima_base_url,
            cache_dir=settings.cima_cache_dir,
            timeout_seconds=settings.cima_timeout_seconds,
            requests_per_second=settings.cima_requests_per_second,
            max_retries=settings.cima_max_retries,
            backoff_seconds=settings.cima_backoff_seconds,
            max_retry_delay_seconds=settings.cima_max_retry_delay_seconds,
        ) as client:
            row = run_one_day(session, client=client, day=day)
    except MaintenanceJobError as error:
        raise ApplicationError(str(error), status_code=503) from error
    return {
        "id": row.id,
        "requested_date": row.requested_date,
        "attempt": row.attempt,
        "status": row.status,
        "event_count": row.event_count,
        "error_detail": row.error_detail,
        "started_at": row.started_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }
