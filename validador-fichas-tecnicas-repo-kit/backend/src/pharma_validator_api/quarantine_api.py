"""Read and independently maintain literal source cells kept in quarantine."""

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import (
    ImportBatch,
    QuarantinedFieldMaintenanceRevision,
    QuarantinedSourceRow,
)
from pharma_validator_api.records import (
    DirectoryDependency,
    FieldMaintenanceRead,
    FieldMaintenanceWrite,
    SessionDependency,
)
from pharma_validator_api.reviewer_identity import ReviewerIdentityError

router = APIRouter(prefix="/records/quarantined", tags=["registros en cuarentena"])


class QuarantinedFieldRead(BaseModel):
    source_column_index: int
    field_name: str
    literal_value: str | None
    maintained_value: str | None
    observed_type: str
    maintenance_sequence: int
    maintenance_history: list[FieldMaintenanceRead]


class QuarantinedRowRead(BaseModel):
    id: str
    source_workbook: str
    source_locator: str
    reason_code: str
    reason: str
    fields: list[QuarantinedFieldRead]


class QuarantinedRowPage(BaseModel):
    items: list[QuarantinedRowRead]
    total: int


def _decode_fields(payload: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ApplicationError(
            "El payload de la fila en cuarentena no es JSON válido.", status_code=500
        ) from error
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ApplicationError(
            "El payload de la fila en cuarentena tiene un formato no compatible.",
            status_code=500,
        )
    return value


def _field_revision_history(
    revisions: list[QuarantinedFieldMaintenanceRevision],
) -> dict[int, list[QuarantinedFieldMaintenanceRevision]]:
    grouped: defaultdict[int, list[QuarantinedFieldMaintenanceRevision]] = defaultdict(list)
    for revision in revisions:
        grouped[revision.source_column_index].append(revision)
    return dict(grouped)


def _row_read(
    row: QuarantinedSourceRow,
    batch: ImportBatch,
    revisions: list[QuarantinedFieldMaintenanceRevision],
) -> QuarantinedRowRead:
    histories = _field_revision_history(revisions)
    fields = []
    for item in _decode_fields(row.raw_payload):
        column = item.get("column")
        if not isinstance(column, int):
            raise ApplicationError(
                "El payload de cuarentena no incluye una columna Excel válida.",
                status_code=500,
            )
        history = histories.get(column, [])
        literal = item.get("literal_value")
        fields.append(
            QuarantinedFieldRead(
                source_column_index=column,
                field_name=str(item.get("header") or f"Columna {column}"),
                literal_value=literal,
                maintained_value=history[-1].after_value if history else literal,
                observed_type=str(item.get("observed_type") or "unknown"),
                maintenance_sequence=history[-1].sequence if history else 0,
                maintenance_history=[
                    FieldMaintenanceRead(
                        sequence=revision.sequence,
                        before_value=revision.before_value,
                        after_value=revision.after_value,
                        actor_id=revision.actor_id,
                        actor_assurance=revision.actor_assurance,
                        reason=revision.reason,
                        recorded_at=revision.recorded_at.isoformat(),
                    )
                    for revision in history
                ],
            )
        )
    return QuarantinedRowRead(
        id=row.id,
        source_workbook=batch.source_locator,
        source_locator=row.source_locator,
        reason_code=row.reason_code,
        reason=row.reason,
        fields=fields,
    )


@router.get("", response_model=QuarantinedRowPage)
def list_quarantined_rows(
    session: SessionDependency,
    source_workbook: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> QuarantinedRowPage:
    statement = (
        select(QuarantinedSourceRow, ImportBatch)
        .join(ImportBatch, ImportBatch.id == QuarantinedSourceRow.import_batch_id)
        .order_by(
            ImportBatch.source_locator,
            QuarantinedSourceRow.source_locator,
            QuarantinedSourceRow.id,
        )
    )
    count_statement = (
        select(func.count())
        .select_from(QuarantinedSourceRow)
        .join(ImportBatch, ImportBatch.id == QuarantinedSourceRow.import_batch_id)
    )
    if source_workbook:
        statement = statement.where(ImportBatch.source_locator == source_workbook)
        count_statement = count_statement.where(ImportBatch.source_locator == source_workbook)
    total = int(session.scalar(count_statement) or 0)
    page = session.execute(statement.offset(offset).limit(limit)).all()
    row_ids = [row.id for row, _ in page]
    revisions = (
        session.scalars(
            select(QuarantinedFieldMaintenanceRevision)
            .where(QuarantinedFieldMaintenanceRevision.quarantined_row_id.in_(row_ids))
            .order_by(
                QuarantinedFieldMaintenanceRevision.quarantined_row_id,
                QuarantinedFieldMaintenanceRevision.source_column_index,
                QuarantinedFieldMaintenanceRevision.sequence,
            )
        ).all()
        if row_ids
        else []
    )
    revisions_by_row: defaultdict[str, list[QuarantinedFieldMaintenanceRevision]] = defaultdict(
        list
    )
    for revision in revisions:
        revisions_by_row[revision.quarantined_row_id].append(revision)
    return QuarantinedRowPage(
        items=[_row_read(row, batch, revisions_by_row[row.id]) for row, batch in page],
        total=total,
    )


@router.post(
    "/{row_id}/values/{source_column_index}/maintenance",
    response_model=QuarantinedFieldRead,
    status_code=201,
)
def maintain_quarantined_field(
    row_id: str,
    source_column_index: int,
    payload: FieldMaintenanceWrite,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> QuarantinedFieldRead:
    row = session.get(QuarantinedSourceRow, row_id)
    if row is None:
        raise ApplicationError("Fila en cuarentena no encontrada.", status_code=404)
    field = next(
        (
            item
            for item in _decode_fields(row.raw_payload)
            if item.get("column") == source_column_index
        ),
        None,
    )
    if field is None:
        raise ApplicationError("Columna no encontrada en la fila.", status_code=404)
    current = session.scalar(
        select(QuarantinedFieldMaintenanceRevision)
        .where(
            QuarantinedFieldMaintenanceRevision.quarantined_row_id == row_id,
            QuarantinedFieldMaintenanceRevision.source_column_index == source_column_index,
        )
        .order_by(QuarantinedFieldMaintenanceRevision.sequence.desc())
        .limit(1)
    )
    current_sequence = current.sequence if current else 0
    if payload.expected_sequence != current_sequence:
        raise ApplicationError(
            "El campo cambió desde que lo abrió. Recargue antes de guardar.",
            status_code=409,
        )
    reason = payload.reason.strip()
    if not reason:
        raise ApplicationError("Indique el motivo del cambio.", status_code=400)
    before = current.after_value if current else field.get("literal_value")
    if payload.value == before:
        raise ApplicationError("El valor nuevo es igual al valor vigente.", status_code=400)
    try:
        actor = directory.resolve(payload.actor_id)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error
    revision = QuarantinedFieldMaintenanceRevision(
        quarantined_row_id=row_id,
        source_column_index=source_column_index,
        sequence=current_sequence + 1,
        before_value=before,
        after_value=payload.value,
        actor_id=actor.identifier,
        actor_assurance=actor.assurance,
        reason=reason,
        recorded_at=datetime.now(UTC),
    )
    session.add(revision)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApplicationError(
            "El campo se modificó en paralelo. Recargue antes de guardar.",
            status_code=409,
        ) from error
    batch = session.get(ImportBatch, row.import_batch_id)
    if batch is None:
        raise RuntimeError(f"Lote inexistente para fila en cuarentena {row.id}")
    return _row_read(row, batch, [revision]).fields[
        next(
            index
            for index, item in enumerate(_decode_fields(row.raw_payload))
            if item.get("column") == source_column_index
        )
    ]
