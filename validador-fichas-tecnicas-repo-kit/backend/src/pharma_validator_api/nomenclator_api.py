"""Comparación trazable con una instantánea local de dbo.nomenclatur."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
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
    compare_snapshots,
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
    version_id: int | None = None
    synced_at: str | None = None
    version_count: int = 0


class ChangesRead(BaseModel):
    """Diferencias literales por CN; `previous_sha256` nulo en la primera versión."""

    previous_sha256: str | None
    added: int
    removed: int
    modified: int
    sample_added: list[str]
    sample_removed: list[str]
    sample_modified: list[str]


class SnapshotImportRead(SnapshotRead):
    changed: bool
    changes: ChangesRead | None = None


class VersionRead(BaseModel):
    version_id: int
    sha256: str
    row_count: int
    latest_source_date: str | None
    synced_at: str
    changed: bool
    current: bool


class RowRead(BaseModel):
    code: str
    source_row_id: str
    values: dict[str, str | None]
    catalog_match: Literal["exacta", "ambigua", "sin_correspondencia"]
    catalog_identity_id: str | None


class RowPageRead(BaseModel):
    available: bool
    sha256: str | None = None
    total: int = 0
    items: list[RowRead] = Field(default_factory=list)


class ReconciliationRead(BaseModel):
    available: bool
    sha256: str | None = None
    nomenclator_rows: int = 0
    exact: int = 0
    ambiguous: int = 0
    nomenclator_without_catalog: int = 0
    catalog_without_nomenclator: int = 0


SAMPLE_SIZE = 20


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


def _versions(session: Session, owner: str) -> list[NomenclatorUserSnapshot]:
    """Historial propio, del más reciente al más antiguo. Nunca mezcla cuentas."""
    return list(session.scalars(
        select(NomenclatorUserSnapshot)
        .where(NomenclatorUserSnapshot.owner_subject_id == owner)
        .order_by(NomenclatorUserSnapshot.id.desc())
    ).all())


def _latest(session: Session, owner: str) -> NomenclatorUserSnapshot | None:
    return session.scalar(
        select(NomenclatorUserSnapshot)
        .where(NomenclatorUserSnapshot.owner_subject_id == owner)
        .order_by(NomenclatorUserSnapshot.id.desc()).limit(1)
    )


def _load(path: Path) -> NomenclatorSnapshot:
    try:
        return load_snapshot(path)
    except (OSError, ValueError) as error:
        raise ApplicationError(
            "La instantánea Nomenclátor configurada no se puede leer.", status_code=503
        ) from error


def _snapshot(request: Request, session: Session) -> NomenclatorSnapshot | None:
    owner = _owner(request)
    latest = _latest(session, owner)
    path = Path(latest.snapshot_path) if latest else (
        request.app.state.settings.nomenclator_snapshot_path if owner == "pilot" else None
    )
    return None if path is None else _load(path)


def _changes(previous: NomenclatorSnapshot | None, current: NomenclatorSnapshot) -> ChangesRead:
    if previous is None:
        return ChangesRead(
            previous_sha256=None, added=current.row_count, removed=0, modified=0,
            sample_added=sorted(current.rows)[:SAMPLE_SIZE], sample_removed=[],
            sample_modified=[],
        )
    diff = compare_snapshots(previous, current)
    return ChangesRead(
        previous_sha256=previous.sha256, added=len(diff.added), removed=len(diff.removed),
        modified=len(diff.modified), sample_added=list(diff.added[:SAMPLE_SIZE]),
        sample_removed=list(diff.removed[:SAMPLE_SIZE]),
        sample_modified=list(diff.modified[:SAMPLE_SIZE]),
    )


def _catalog_codes(session: Session) -> dict[str, list[str]]:
    """CN de presentaciones activas del catálogo. Sólo igualdad literal exacta."""
    codes: dict[str, list[str]] = {}
    for identity_id, code in session.execute(
        select(MedicationCatalogIdentity.id, MedicationCatalogIdentity.code).where(
            MedicationCatalogIdentity.identity_type == "presentation",
            MedicationCatalogIdentity.active.is_(True),
            MedicationCatalogIdentity.code.is_not(None),
        )
    ):
        codes.setdefault((code or "").strip(), []).append(identity_id)
    return codes


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
    # Sólo lee la copia persistida: no depende de que el conector local esté abierto.
    snapshot = _snapshot(request, session)
    if snapshot is None:
        return SnapshotRead(available=False)
    owner = _owner(request)
    latest = _latest(session, owner)
    count = session.scalar(
        select(func.count()).select_from(NomenclatorUserSnapshot)
        .where(NomenclatorUserSnapshot.owner_subject_id == owner)
    ) or 0
    return SnapshotRead(
        available=True, sha256=snapshot.sha256, row_count=snapshot.row_count,
        latest_source_date=snapshot.latest_source_date,
        version_id=latest.id if latest else None,
        synced_at=latest.created_at.isoformat() if latest else None, version_count=count,
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
        last = _latest(session, owner)
        changed = last is None or last.snapshot_sha256 != snapshot.sha256
        previous: NomenclatorSnapshot | None = None
        if last is not None and changed:
            try:
                previous = load_snapshot(Path(last.snapshot_path))
            except (OSError, ValueError):
                previous = None  # La nueva versión sigue siendo válida por sí misma.
        version = NomenclatorUserSnapshot(
            owner_subject_id=owner, snapshot_sha256=snapshot.sha256,
            snapshot_path=str(destination), row_count=snapshot.row_count,
            latest_source_date=snapshot.latest_source_date, created_at=datetime.now(UTC),
        )
        session.add(version)
        session.commit()
        return SnapshotImportRead(
            available=True, sha256=snapshot.sha256, row_count=snapshot.row_count,
            latest_source_date=snapshot.latest_source_date, changed=changed,
            version_id=version.id, synced_at=version.created_at.isoformat(),
            version_count=len(_versions(session, owner)),
            changes=(
                _changes(previous, snapshot)
                if changed and (last is None or previous is not None) else None
            ),
        )
    except OSError as error:
        raise ApplicationError(
            "No se puede guardar la instantánea Nomenclátor.", status_code=503
        ) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@router.get("/snapshots", response_model=list[VersionRead])
def snapshot_history(request: Request, session: SessionDependency) -> list[VersionRead]:
    versions = _versions(session, _owner(request))
    result: list[VersionRead] = []
    for index, row in enumerate(versions):
        older = versions[index + 1] if index + 1 < len(versions) else None
        result.append(VersionRead(
            version_id=row.id, sha256=row.snapshot_sha256, row_count=row.row_count,
            latest_source_date=row.latest_source_date, synced_at=row.created_at.isoformat(),
            changed=older is None or older.snapshot_sha256 != row.snapshot_sha256,
            current=index == 0,
        ))
    return result


@router.get("/snapshots/{version_id}/changes", response_model=ChangesRead)
def snapshot_changes(
    version_id: int, request: Request, session: SessionDependency,
) -> ChangesRead:
    versions = _versions(session, _owner(request))
    position = next((i for i, row in enumerate(versions) if row.id == version_id), None)
    if position is None:
        # Misma respuesta para inexistente y ajena: no revela otras cuentas.
        raise ApplicationError("Versión Nomenclátor no encontrada.", status_code=404)
    current = versions[position]
    previous = next(
        (row for row in versions[position + 1:]
         if row.snapshot_sha256 != current.snapshot_sha256),
        None,
    )
    return _changes(
        _load(Path(previous.snapshot_path)) if previous else None,
        _load(Path(current.snapshot_path)),
    )


@router.get("/rows", response_model=RowPageRead)
def snapshot_rows(
    request: Request, session: SessionDependency,
    q: str = Query("", max_length=120),
    limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
) -> RowPageRead:
    snapshot = _snapshot(request, session)
    if snapshot is None:
        return RowPageRead(available=False)
    needle = q.strip().casefold()
    searchable = [FIELD_BY_NAME[name] for name in ("nro_definitivo", "principioactivo", "cod_atc")]
    matches = [
        (cn, row) for cn, row in sorted(snapshot.rows.items())
        if not needle or cn.startswith(needle) or any(
            needle in (source_value(row.columns, spec) or "").casefold() for spec in searchable
        )
    ]
    codes = _catalog_codes(session)
    items: list[RowRead] = []
    for cn, row in matches[offset:offset + limit]:
        identities = codes.get(cn, [])
        items.append(RowRead(
            code=cn, source_row_id=row.columns[0],
            values={spec.name: source_value(row.columns, spec) for spec in FIELDS},
            catalog_match=(
                "exacta" if len(identities) == 1
                else "ambigua" if identities else "sin_correspondencia"
            ),
            catalog_identity_id=identities[0] if len(identities) == 1 else None,
        ))
    return RowPageRead(available=True, sha256=snapshot.sha256, total=len(matches), items=items)


@router.get("/reconciliation", response_model=ReconciliationRead)
def reconciliation(request: Request, session: SessionDependency) -> ReconciliationRead:
    """Recuento de correspondencias por CN exacto. No consolida ni reescribe nada."""
    snapshot = _snapshot(request, session)
    if snapshot is None:
        return ReconciliationRead(available=False)
    codes = _catalog_codes(session)
    exact = sum(1 for cn in snapshot.rows if len(codes.get(cn, [])) == 1)
    ambiguous = sum(1 for cn in snapshot.rows if len(codes.get(cn, [])) > 1)
    return ReconciliationRead(
        available=True, sha256=snapshot.sha256, nomenclator_rows=snapshot.row_count,
        exact=exact, ambiguous=ambiguous,
        nomenclator_without_catalog=snapshot.row_count - exact - ambiguous,
        catalog_without_nomenclator=sum(1 for cn in codes if cn not in snapshot.rows),
    )


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
