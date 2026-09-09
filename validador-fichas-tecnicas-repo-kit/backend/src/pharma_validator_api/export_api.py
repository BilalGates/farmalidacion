"""API de exportación, exclusiones y auditoría (DEV-604/605/609).

No contiene reglas: valida la petición, comprueba quién firma y delega en
`export_service`, que a su vez delega en el motor puro. Los perfiles llegan
como dato para que definir una salida no exija desplegar código.

La exportación queda detrás de `enable_export`, apagada por defecto: D-011
sigue pendiente y ningún perfil está aceptado por el proveedor. Encenderla es
una decisión de quien opera, no un efecto de haber programado el motor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from pharma_validator_api.audit_store import events_for, record_history
from pharma_validator_api.export_engine import ColumnSpec, ExportFormat, ExportProfile
from pharma_validator_api.export_service import (
    archived_runs,
    exclusion_report,
    run_export,
)
from pharma_validator_api.models import ExportRun, TargetRecord
from pharma_validator_api.queue_api import SettingsDependency
from pharma_validator_api.records import DirectoryDependency, SessionDependency
from pharma_validator_api.reviewer_identity import ReviewerIdentityError
from pharma_validator_api.risk_rules import SEED_RULES, assess

router = APIRouter(prefix="/exports", tags=["exportación"])


class ColumnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    source_field: str = Field(min_length=1)
    max_length: int | None = Field(default=None, ge=1)
    required: bool = False


class ExportRequest(BaseModel):
    """Petición de exportación. El perfil viaja completo y se archiva."""

    model_config = ConfigDict(extra="forbid")
    actor_id: str = Field(min_length=1)
    profile_name: str = Field(min_length=1)
    fmt: ExportFormat = "csv"
    columns: list[ColumnRequest] = Field(min_length=1)
    delimiter: str = ";"
    encoding: str = "utf-8"
    decimal_separator: str = ","
    include_header: bool = True
    state_rendering: dict[str, str] | None = None
    record_ids: list[str] | None = None


def _enabled(settings: Any) -> None:
    if not settings.enable_export:
        raise HTTPException(404, "La exportación está desactivada.")


def _profile(payload: ExportRequest) -> ExportProfile:
    extra: dict[str, Any] = {}
    if payload.state_rendering is not None:
        extra["state_rendering"] = payload.state_rendering
    try:
        return ExportProfile(
            name=payload.profile_name,
            fmt=payload.fmt,
            columns=tuple(
                ColumnSpec(
                    name=column.name,
                    source_field=column.source_field,
                    max_length=column.max_length,
                    required=column.required,
                )
                for column in payload.columns
            ),
            delimiter=payload.delimiter,
            encoding=payload.encoding,
            decimal_separator=payload.decimal_separator,
            include_header=payload.include_header,
            **extra,
        )
    except (ValueError, LookupError) as error:
        raise HTTPException(400, str(error)) from error


@router.post("", status_code=201)
def create_export(
    payload: ExportRequest,
    session: SessionDependency,
    directory: DirectoryDependency,
    settings: SettingsDependency,
) -> dict[str, Any]:
    """Ejecuta una exportación y devuelve su resumen, no el fichero.

    El artefacto se descarga aparte: devolverlo aquí mezclaría el resultado
    con su metadato y obligaría a cargarlo entero en memoria para consultarlo.
    """
    _enabled(settings)
    try:
        actor = directory.resolve(payload.actor_id)
    except ReviewerIdentityError as error:
        # Una firma no reconocida es una peticion invalida, no un fallo del
        # servidor: devolverla como 500 ocultaria el motivo a quien la hizo.
        raise HTTPException(400, str(error)) from error
    profile = _profile(payload)

    artifact_dir = Path(settings.export_artifact_dir)
    outcome = run_export(
        session,
        profile,
        actor_id=actor.identifier,
        actor_assurance=actor.assurance,
        record_ids=tuple(payload.record_ids) if payload.record_ids else None,
        artifact_dir=artifact_dir,
    )
    return {
        "run_id": outcome.run_id,
        "status": outcome.status,
        "delivered_rows": outcome.delivered_rows,
        "excluded_count": len(outcome.exclusions),
        "blocking_count": len(outcome.blocking_exclusions),
        "content_hash": outcome.result.checksum_sha256 if outcome.result else None,
        # Un perfil que produce fichero no es un contrato aceptado (D-011).
        "provider_accepted": profile.provider_accepted,
    }


@router.get("")
def list_exports(session: SessionDependency, settings: SettingsDependency) -> list[dict[str, Any]]:
    _enabled(settings)
    return [
        {
            "run_id": run.id,
            "profile_name": run.profile_name,
            "profile_version": run.profile_version,
            "format": run.export_format,
            "status": run.status,
            "actor_id": run.actor_id,
            "row_count": run.row_count,
            "excluded_count": run.excluded_count,
            "content_hash": run.content_hash,
            "byte_size": run.byte_size,
            "created_at": run.created_at.isoformat(),
        }
        for run in archived_runs(session)
    ]


@router.get("/{run_id}/exclusions")
def list_exclusions(
    run_id: str, session: SessionDependency, settings: SettingsDependency
) -> list[dict[str, Any]]:
    """Informe de exclusiones: qué no se entregó y por qué."""
    _enabled(settings)
    if session.get(ExportRun, run_id) is None:
        raise HTTPException(404, "Ejecución de exportación no encontrada.")
    return [
        {
            "target_record_id": item.target_record_id,
            "field_name": item.field_name,
            "severity": item.severity,
            "rule": item.rule,
            "detail": item.detail,
            "observed_state": item.observed_state,
        }
        for item in exclusion_report(session, run_id)
    ]


@router.get("/{run_id}/profile")
def read_profile(
    run_id: str, session: SessionDependency, settings: SettingsDependency
) -> dict[str, Any]:
    """Configuración archivada: lo que hace repetible una ejecución."""
    _enabled(settings)
    run = session.get(ExportRun, run_id)
    if run is None:
        raise HTTPException(404, "Ejecución de exportación no encontrada.")
    return {
        "run_id": run.id,
        "profile_version": run.profile_version,
        "profile": json.loads(run.profile_snapshot),
    }


@router.get("/{run_id}/artifact", response_class=FileResponse)
def download_artifact(
    run_id: str, session: SessionDependency, settings: SettingsDependency
) -> FileResponse:
    """Descarga el artefacto archivado tras verificar ruta e integridad."""
    from hashlib import sha256

    _enabled(settings)
    run = session.get(ExportRun, run_id)
    if run is None or run.artifact_path is None:
        raise HTTPException(404, "Artefacto de exportación no encontrado.")
    configured = Path(settings.export_artifact_dir).resolve()
    path = Path(run.artifact_path).resolve()
    if path.parent != configured or not path.is_file():
        raise HTTPException(404, "Artefacto de exportación no encontrado.")
    if run.content_hash is None or sha256(path.read_bytes()).hexdigest() != run.content_hash:
        raise HTTPException(409, "El artefacto archivado no supera la verificación de integridad.")
    media_types = {
        "csv": "text/csv",
        "txt": "text/plain",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return FileResponse(
        path,
        media_type=media_types.get(run.export_format, "application/octet-stream"),
        filename=f"{run.id}.{run.export_format}",
    )


audit_router = APIRouter(prefix="/audit", tags=["auditoría"])


@audit_router.get("/records/{record_id}")
def read_record_history(record_id: str, session: SessionDependency) -> list[dict[str, Any]]:
    """Historial completo de un registro: decisiones, bloques y diario."""
    if session.get(TargetRecord, record_id) is None:
        raise HTTPException(404, "Registro no encontrado.")
    return [
        {
            "occurred_at": entry.occurred_at.isoformat(),
            "source": entry.source,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "entity_id": entry.entity_id,
            "detail": entry.detail,
            "sequence": entry.sequence,
        }
        for entry in record_history(session, record_id)
    ]


@audit_router.get("/events")
def read_events(
    session: SessionDependency,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "action": item.action,
            "actor_id": item.actor_id,
            "actor_assurance": item.actor_assurance,
            "reason": item.reason,
            "recorded_at": item.recorded_at.isoformat(),
        }
        for item in events_for(session, entity_type=entity_type, entity_id=entity_id)
    ]


risk_router = APIRouter(prefix="/risk", tags=["riesgo"])


@risk_router.get("/rules")
def list_rules() -> dict[str, Any]:
    """Reglas de riesgo activas y su procedencia."""
    return {
        "rules": [
            {"atc_prefix": rule.atc_prefix, "reason": rule.reason, "active": rule.active}
            for rule in SEED_RULES
        ],
        "pending_decision": (
            "D-017: ampliar la lista de prefijos de riesgo es decisión "
            "exclusiva de farmacia. Sólo `L04` está acordado (especificación 11.1)."
        ),
    }


@risk_router.get("/assess")
def assess_code(atc: str | None = None) -> dict[str, Any]:
    """Evalúa un código ATC contra las reglas activas."""
    result = assess(atc)
    return {
        "atc": atc,
        "requires_double_review": result.requires_double_review,
        "undetermined": result.is_undetermined,
        "reason": result.reason,
        "matched": [rule.atc_prefix for rule in result.matched],
    }
