"""Read and independently maintain literal source cells kept in quarantine."""

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_validator_api.empty_source_fields import EmptySourceColumn, EmptySourceFieldWrite
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.master_workbook_export import MASTER_WORKBOOKS
from pharma_validator_api.models import (
    ImportBatch,
    ImportedSourceSheet,
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
    header_columns: dict[int, str] | None = None,
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
    source_columns = {field.source_column_index for field in fields}
    for column, history in histories.items():
        if column in source_columns:
            continue
        name = (header_columns or {}).get(column)
        if name is None:
            raise ApplicationError(
                "La revisión de una celda vacía no tiene cabecera.", status_code=500
            )
        fields.append(
            QuarantinedFieldRead(
                source_column_index=column,
                field_name=name,
                literal_value=None,
                maintained_value=history[-1].after_value,
                observed_type="empty",
                maintenance_sequence=history[-1].sequence,
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
    fields.sort(key=lambda field: field.source_column_index)
    return QuarantinedRowRead(
        id=row.id,
        source_workbook=batch.source_locator,
        source_locator=row.source_locator,
        reason_code=row.reason_code,
        reason=row.reason,
        fields=fields,
    )


def _sheet_headers(session: Session, row: QuarantinedSourceRow) -> dict[int, str]:
    batch = session.get(ImportBatch, row.import_batch_id)
    if batch is None or batch.status != "completed" or batch.source_locator not in MASTER_WORKBOOKS:
        raise ApplicationError(
            "La fila no pertenece a un maestro importado completo.", status_code=422
        )
    if "!" not in row.source_locator:
        raise ApplicationError("La coordenada de cuarentena no es válida.", status_code=422)
    sheet_name, row_literal = row.source_locator.rsplit("!", 1)
    try:
        row_number = int(row_literal)
    except ValueError as error:
        raise ApplicationError(
            "La coordenada de cuarentena no es válida.", status_code=422
        ) from error
    sheets = session.scalars(
        select(ImportedSourceSheet).where(
            ImportedSourceSheet.import_batch_id == row.import_batch_id,
            ImportedSourceSheet.sheet_name == sheet_name,
        )
    ).all()
    if len(sheets) != 1 or row_number <= sheets[0].header_row_number:
        raise ApplicationError("La hoja o fila de cuarentena no es inequívoca.", status_code=422)
    try:
        cells = json.loads(sheets[0].header_payload)
    except json.JSONDecodeError as error:
        raise ApplicationError("La cabecera importada no es válida.", status_code=500) from error
    if not isinstance(cells, list):
        raise ApplicationError("La cabecera importada no es válida.", status_code=500)
    headers: dict[int, str] = {}
    for item in cells:
        if not isinstance(item, dict) or type(item.get("column")) is not int:
            raise ApplicationError(
                "La cabecera importada tiene columnas inválidas.", status_code=500
            )
        column = item["column"]
        name = item.get("literal_value")
        if column < 1 or column in headers or not isinstance(name, str) or not name:
            raise ApplicationError(
                "La cabecera importada tiene columnas ambiguas.", status_code=500
            )
        headers[column] = name
    return headers


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
    items = []
    for row, batch in page:
        row_revisions = revisions_by_row[row.id]
        raw_columns = {item.get("column") for item in _decode_fields(row.raw_payload)}
        needs_header = any(
            revision.source_column_index not in raw_columns for revision in row_revisions
        )
        headers = _sheet_headers(session, row) if needs_header else None
        items.append(_row_read(row, batch, row_revisions, headers))
    return QuarantinedRowPage(items=items, total=total)


@router.get("/{row_id}/empty-source-columns", response_model=list[EmptySourceColumn])
def list_quarantined_empty_columns(
    row_id: str, session: SessionDependency
) -> list[EmptySourceColumn]:
    row = session.get(QuarantinedSourceRow, row_id)
    if row is None:
        raise ApplicationError("Fila en cuarentena no encontrada.", status_code=404)
    headers = _sheet_headers(session, row)
    used = {item.get("column") for item in _decode_fields(row.raw_payload)}
    used.update(
        session.scalars(
            select(QuarantinedFieldMaintenanceRevision.source_column_index).where(
                QuarantinedFieldMaintenanceRevision.quarantined_row_id == row_id
            )
        ).all()
    )
    return [
        EmptySourceColumn(source_column_index=column, field_name=name)
        for column, name in sorted(headers.items())
        if column not in used
    ]


@router.post(
    "/{row_id}/empty-source-values",
    response_model=QuarantinedFieldRead,
    status_code=201,
)
def create_quarantined_empty_value(
    row_id: str,
    payload: EmptySourceFieldWrite,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> QuarantinedFieldRead:
    row = session.get(QuarantinedSourceRow, row_id)
    if row is None:
        raise ApplicationError("Fila en cuarentena no encontrada.", status_code=404)
    headers = _sheet_headers(session, row)
    available = list_quarantined_empty_columns(row_id, session)
    if payload.source_column_index not in headers:
        raise ApplicationError("La columna no existe en la hoja de origen.", status_code=422)
    if not any(item.source_column_index == payload.source_column_index for item in available):
        raise ApplicationError("La columna ya contiene un valor o una revisión.", status_code=409)
    if not payload.value.strip():
        raise ApplicationError("Indique un valor para la celda vacía.", status_code=400)
    reason = payload.reason.strip()
    if not reason:
        raise ApplicationError("Indique el motivo del cambio.", status_code=400)
    try:
        actor = directory.resolve(payload.actor_id)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error
    revision = QuarantinedFieldMaintenanceRevision(
        quarantined_row_id=row_id,
        source_column_index=payload.source_column_index,
        sequence=1,
        before_value=None,
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
            "La celda se modificó en paralelo. Recargue antes de guardar.", status_code=409
        ) from error
    batch = session.get(ImportBatch, row.import_batch_id)
    assert batch is not None
    return next(
        field
        for field in _row_read(row, batch, [revision], headers).fields
        if field.source_column_index == payload.source_column_index
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
