"""Comparación trazable con una instantánea local de dbo.nomenclatur."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import (
    BlockInstance,
    FieldMaintenanceRevision,
    FieldValue,
    MedicationCatalogIdentity,
    NomenclatorReviewDecision,
    NomenclatorUserSnapshot,
)
from pharma_validator_api.nomenclator_snapshot import (
    FIELD_BY_NAME,
    FIELDS,
    NomenclatorSnapshot,
    load_snapshot,
    source_value,
)
from pharma_validator_api.records import DirectoryDependency, SessionDependency
from pharma_validator_api.reviewer_identity import ReviewerIdentityError

router = APIRouter(prefix="/nomenclator", tags=["Nomenclátor"])


class SnapshotRead(BaseModel):
    available: bool
    sha256: str | None = None
    row_count: int = 0
    latest_source_date: str | None = None


class SnapshotImportRead(SnapshotRead):
    changed: bool


class DecisionRead(BaseModel):
    sequence: int
    action: str
    actor_id: str
    actor_assurance: str
    reason: str
    recorded_at: str
    snapshot_sha256: str


class ComparisonFieldRead(BaseModel):
    field_name: str
    label: str
    level: str
    source_value: str
    master_field: str | None
    master_value: str | None
    status: Literal["coincide", "difiere", "complemento", "sin_comparacion"]
    latest_decision: DecisionRead | None
    decision_history: list[DecisionRead]


class ComparisonRead(BaseModel):
    available: bool
    code: str | None = None
    source_row_id: str | None = None
    source_line: int | None = None
    snapshot_sha256: str | None = None
    latest_source_date: str | None = None
    fields: list[ComparisonFieldRead] = Field(default_factory=list)


class DecisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_name: str
    snapshot_sha256: str = Field(min_length=64, max_length=64)
    expected_sequence: int = Field(ge=0)
    action: Literal["aceptar", "descartar", "pendiente"]
    actor_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=2000)


def _owner(request: Request) -> str:
    principal = getattr(request.state, "principal", None)
    return principal.subject_id if principal is not None else "pilot"


def _snapshot(request: Request, session: Session) -> NomenclatorSnapshot | None:
    owner = _owner(request)
    latest = session.scalar(
        select(NomenclatorUserSnapshot)
        .where(NomenclatorUserSnapshot.owner_subject_id == owner)
        .order_by(NomenclatorUserSnapshot.id.desc()).limit(1)
    )
    path = Path(latest.snapshot_path) if latest else (
        request.app.state.settings.nomenclator_snapshot_path if owner == "pilot" else None
    )
    if path is None:
        return None
    try:
        return load_snapshot(path)
    except (OSError, ValueError) as error:
        raise ApplicationError(
            "La instantánea Nomenclátor configurada no se puede leer.", status_code=503
        ) from error


def _record_field(session: Session, record_id: str, name: str) -> str | None:
    values = list(session.scalars(
        select(FieldValue)
        .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
        .where(BlockInstance.target_record_id == record_id, FieldValue.field_name == name)
        .limit(2)
    ).all())
    if len(values) != 1:
        return None
    value = values[0]
    revision = session.scalar(
        select(FieldMaintenanceRevision)
        .where(FieldMaintenanceRevision.field_value_id == value.id)
        .order_by(FieldMaintenanceRevision.sequence.desc())
        .limit(1)
    )
    return revision.after_value if revision else value.literal_value


def _medication_record(session: Session, specialty_record_id: str) -> str | None:
    external_id = _record_field(session, specialty_record_id, "ME_IDEXTERNO")
    if not external_id:
        return None
    record_ids = list(session.scalars(
        select(BlockInstance.target_record_id)
        .join(FieldValue, FieldValue.block_instance_id == BlockInstance.id)
        .where(FieldValue.field_name == "MED_IDEXTERNO", FieldValue.literal_value == external_id)
        .distinct().limit(2)
    ).all())
    return record_ids[0] if len(record_ids) == 1 else None


def _read_decision(row: NomenclatorReviewDecision) -> DecisionRead:
    return DecisionRead(
        sequence=row.sequence, action=row.action, actor_id=row.actor_id,
        actor_assurance=row.actor_assurance, reason=row.reason,
        recorded_at=row.recorded_at.isoformat(), snapshot_sha256=row.snapshot_sha256,
    )


def _comparison(
    session: Session, identity_id: str, snapshot: NomenclatorSnapshot | None,
    owner: str,
) -> ComparisonRead:
    identity = session.get(MedicationCatalogIdentity, identity_id)
    if identity is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    if identity.identity_type != "presentation" or not identity.target_record_id:
        return ComparisonRead(available=False)
    if snapshot is None:
        return ComparisonRead(available=False, code=identity.code)
    cn = (identity.code or "").strip()
    row = snapshot.rows.get(cn)
    if row is None:
        return ComparisonRead(
            available=True, code=cn, snapshot_sha256=snapshot.sha256,
            latest_source_date=snapshot.latest_source_date,
        )
    medication_record_id = _medication_record(session, identity.target_record_id)
    previous = list(session.scalars(
        select(NomenclatorReviewDecision)
        .where(
            NomenclatorReviewDecision.identity_id == identity_id,
            NomenclatorReviewDecision.owner_subject_id == owner,
        )
        .order_by(NomenclatorReviewDecision.field_name, NomenclatorReviewDecision.sequence)
    ).all())
    history: dict[str, list[NomenclatorReviewDecision]] = {}
    for decision in previous:
        history.setdefault(decision.field_name, []).append(decision)
    fields: list[ComparisonFieldRead] = []
    for spec in FIELDS:
        candidate = source_value(row.columns, spec)
        if candidate is None:
            continue
        master: str | None = None
        if spec.master_field:
            record_owner = (
                medication_record_id if spec.level == "medicamento" else identity.target_record_id
            )
            if record_owner:
                master = _record_field(session, record_owner, spec.master_field)
        if spec.master_field and master is None:
            status: Literal["coincide", "difiere", "complemento", "sin_comparacion"] = (
                "sin_comparacion"
            )
        elif spec.master_field is None:
            status = "complemento"
        else:
            # Equivalencia de representación únicamente para comparar. El valor
            # original S/N y el 0/1 de Nomenclátor siguen intactos.
            comparable = master
            if spec.name == "sw_uso_hospitalario":
                comparable = {"S": "1", "N": "0"}.get(master or "", master)
            status = "coincide" if comparable == candidate else "difiere"
        decisions = history.get(spec.name, [])
        current = next(
            (decision for decision in reversed(decisions)
             if decision.snapshot_sha256 == snapshot.sha256 and decision.source_value == candidate),
            None,
        )
        fields.append(ComparisonFieldRead(
            field_name=spec.name, label=spec.label, level=spec.level,
            source_value=candidate, master_field=spec.master_field,
            master_value=master, status=status,
            latest_decision=_read_decision(current) if current else None,
            decision_history=[_read_decision(item) for item in decisions],
        ))
    return ComparisonRead(
        available=True, code=cn, source_row_id=row.columns[0],
        source_line=row.line_number, snapshot_sha256=snapshot.sha256,
        latest_source_date=snapshot.latest_source_date, fields=fields,
    )


@router.get("/snapshot", response_model=SnapshotRead)
def snapshot_info(request: Request, session: SessionDependency) -> SnapshotRead:
    snapshot = _snapshot(request, session)
    if snapshot is None:
        return SnapshotRead(available=False)
    return SnapshotRead(
        available=True, sha256=snapshot.sha256, row_count=snapshot.row_count,
        latest_source_date=snapshot.latest_source_date,
    )


@router.post("/snapshots", response_model=SnapshotImportRead, status_code=201)
async def import_personal_snapshot(
    request: Request, session: SessionDependency,
) -> SnapshotImportRead:
    """Recibe exclusivamente la copia producida por el conector local del usuario."""
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise ApplicationError(
            "La sincronización personal requiere sesión corporativa.", status_code=409
        )
    base: Path | None = request.app.state.settings.nomenclator_snapshot_dir
    if base is None:
        raise ApplicationError(
            "El servidor no tiene almacenamiento Nomenclátor configurado.", status_code=503
        )
    owner = principal.subject_id
    directory = base / hashlib.sha256(owner.encode("utf-8")).hexdigest()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ApplicationError(
            "No se puede guardar la instantánea Nomenclátor.", status_code=503
        ) from error
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix="recepcion-", suffix=".tsv", dir=directory, delete=False,
        ) as output:
            temporary = Path(output.name)
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 100_000_000:
                    raise ApplicationError("La instantánea supera 100 MB.", status_code=413)
                output.write(chunk)
        try:
            snapshot = load_snapshot(temporary)
        except ValueError as error:
            raise ApplicationError(
                f"Instantánea Nomenclátor inválida: {error}", status_code=422
            ) from error
        destination = directory / f"nomenclatur-{snapshot.sha256}.tsv"
        if destination.exists():
            load_snapshot(destination)
        else:
            os.replace(temporary, destination)
            temporary = None
        last = session.scalar(
            select(NomenclatorUserSnapshot)
            .where(NomenclatorUserSnapshot.owner_subject_id == owner)
            .order_by(NomenclatorUserSnapshot.id.desc()).limit(1)
        )
        changed = last is None or last.snapshot_sha256 != snapshot.sha256
        session.add(NomenclatorUserSnapshot(
            owner_subject_id=owner, snapshot_sha256=snapshot.sha256,
            snapshot_path=str(destination), row_count=snapshot.row_count,
            latest_source_date=snapshot.latest_source_date, created_at=datetime.now(UTC),
        ))
        session.commit()
        return SnapshotImportRead(
            available=True, sha256=snapshot.sha256, row_count=snapshot.row_count,
            latest_source_date=snapshot.latest_source_date, changed=changed,
        )
    except OSError as error:
        raise ApplicationError(
            "No se puede guardar la instantánea Nomenclátor.", status_code=503
        ) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@router.get("/identities/{identity_id}/comparison", response_model=ComparisonRead)
def identity_comparison(
    identity_id: str, request: Request, session: SessionDependency
) -> ComparisonRead:
    return _comparison(session, identity_id, _snapshot(request, session), _owner(request))


@router.post(
    "/identities/{identity_id}/decisions", response_model=DecisionRead, status_code=201
)
def decide(
    identity_id: str, payload: DecisionWrite, request: Request,
    session: SessionDependency, directory: DirectoryDependency,
) -> DecisionRead:
    owner = _owner(request)
    snapshot = _snapshot(request, session)
    if snapshot is None or snapshot.sha256 != payload.snapshot_sha256:
        raise ApplicationError("La instantánea cambió; recargue la comparación.", status_code=409)
    if payload.field_name not in FIELD_BY_NAME:
        raise ApplicationError("Campo Nomenclátor no reconocido.", status_code=422)
    comparison = _comparison(session, identity_id, snapshot, owner)
    field = next(
        (item for item in comparison.fields if item.field_name == payload.field_name), None
    )
    if field is None or field.status == "coincide":
        raise ApplicationError("Este campo no tiene una propuesta pendiente.", status_code=422)
    try:
        reviewer = directory.resolve(payload.actor_id)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error
    if payload.action == "aceptar" and reviewer.role != "farmaceutico":
        raise ApplicationError(
            "Aceptar un dato Nomenclátor exige rol farmacéutico.", status_code=403
        )
    if not payload.reason.strip():
        raise ApplicationError("Indique el motivo de la decisión.", status_code=422)
    latest = session.scalar(
        select(NomenclatorReviewDecision.sequence)
        .where(
            NomenclatorReviewDecision.identity_id == identity_id,
            NomenclatorReviewDecision.field_name == payload.field_name,
            NomenclatorReviewDecision.owner_subject_id == owner,
        )
        .order_by(NomenclatorReviewDecision.sequence.desc()).limit(1)
    ) or 0
    if latest != payload.expected_sequence:
        raise ApplicationError("La decisión cambió; recargue el expediente.", status_code=409)
    decision = NomenclatorReviewDecision(
        owner_subject_id=owner,
        identity_id=identity_id, field_name=payload.field_name, sequence=latest + 1,
        snapshot_sha256=snapshot.sha256, source_cn=comparison.code or "",
        source_value=field.source_value, compared_value=field.master_value,
        comparison_status=field.status, action=payload.action,
        actor_id=reviewer.identifier, actor_assurance=reviewer.assurance,
        reason=payload.reason.strip(), recorded_at=datetime.now(UTC),
    )
    session.add(decision)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApplicationError(
            "La decisión cambió; recargue el expediente.", status_code=409
        ) from error
    return _read_decision(decision)
