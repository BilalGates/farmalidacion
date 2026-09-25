"""Create audited working values for empty cells of an imported master row."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.master_workbook_export import MASTER_WORKBOOKS
from pharma_validator_api.models import (
    BlockInstance,
    FieldMaintenanceRevision,
    FieldValue,
    ImportBatch,
    ImportedSourceSheet,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
    new_id,
)
from pharma_validator_api.records import DirectoryDependency, SessionDependency
from pharma_validator_api.reviewer_identity import ReviewerIdentityError

router = APIRouter(prefix="/records", tags=["mantenimiento de origen"])


class EmptySourceColumn(BaseModel):
    source_column_index: int
    field_name: str


class EmptySourceFieldWrite(BaseModel):
    source_column_index: int = Field(ge=1)
    value: str = Field(min_length=1)
    actor_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=2000)


class EmptySourceFieldCreated(EmptySourceColumn):
    id: str
    maintained_value: str


def _payload(payload: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ApplicationError(
            "El inventario de origen no es JSON válido.", status_code=500
        ) from error
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ApplicationError(
            "El inventario de origen tiene un formato inválido.", status_code=500
        )
    columns = [item.get("column") for item in value]
    if any(type(column) is not int or column < 1 for column in columns):
        raise ApplicationError(
            "El inventario de origen contiene columnas inválidas.", status_code=500
        )
    if len(columns) != len(set(columns)):
        raise ApplicationError("El inventario de origen repite columnas.", status_code=500)
    return value


def _columns(
    record_id: str, block_id: str, session: SessionDependency
) -> tuple[BlockInstance, SourceFragment, list[EmptySourceColumn], set[int]]:
    block = session.get(BlockInstance, block_id)
    if (
        block is None
        or block.target_record_id != record_id
        or session.get(TargetRecord, record_id) is None
    ):
        raise ApplicationError("Bloque de registro no encontrado.", status_code=404)
    fragment = (
        session.get(SourceFragment, block.source_fragment_id) if block.source_fragment_id else None
    )
    if fragment is None or fragment.locator_type != "excel_row":
        raise ApplicationError(
            "El bloque no procede de una fila Excel verificable.", status_code=422
        )
    try:
        locator = json.loads(fragment.locator)
        sheet_name = str(locator["sheet"])
        row_number = int(locator["row"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ApplicationError("La coordenada de origen no es válida.", status_code=422) from error
    sheets = session.execute(
        select(ImportedSourceSheet, ImportBatch)
        .join(ImportBatch, ImportBatch.id == ImportedSourceSheet.import_batch_id)
        .where(
            ImportBatch.source_document_version_id == fragment.document_version_id,
            ImportBatch.source_locator.in_(MASTER_WORKBOOKS),
            ImportBatch.status == "completed",
            ImportedSourceSheet.sheet_name == sheet_name,
        )
    ).all()
    if len(sheets) != 1:
        raise ApplicationError("No hay una hoja maestra importada inequívoca.", status_code=422)
    source_sheet, _batch = sheets[0]
    if row_number <= source_sheet.header_row_number:
        raise ApplicationError("La fila de origen no es una fila de datos.", status_code=422)
    headers = _payload(source_sheet.header_payload)
    source_cells = _payload(fragment.literal_text or "[]")
    source_columns = {int(item["column"]) for item in source_cells}
    present_columns = set(
        session.scalars(
            select(FieldValue.source_column_index).where(FieldValue.block_instance_id == block_id)
        ).all()
    )
    unavailable = source_columns | {column for column in present_columns if column is not None}
    available = [
        EmptySourceColumn(source_column_index=column, field_name=str(item["literal_value"]))
        for item in headers
        if isinstance((column := item.get("column")), int)
        and column > 0
        and isinstance(item.get("literal_value"), str)
        and item["literal_value"]
        and column not in unavailable
    ]
    return block, fragment, available, unavailable


@router.get(
    "/{record_id}/blocks/{block_id}/empty-source-columns", response_model=list[EmptySourceColumn]
)
def list_empty_source_columns(
    record_id: str, block_id: str, session: SessionDependency
) -> list[EmptySourceColumn]:
    return _columns(record_id, block_id, session)[2]


@router.post(
    "/{record_id}/blocks/{block_id}/empty-source-values",
    response_model=EmptySourceFieldCreated,
    status_code=201,
)
def create_empty_source_value(
    record_id: str,
    block_id: str,
    payload: EmptySourceFieldWrite,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> EmptySourceFieldCreated:
    block, fragment, available, unavailable = _columns(record_id, block_id, session)
    column = next(
        (item for item in available if item.source_column_index == payload.source_column_index),
        None,
    )
    if column is None:
        status = 409 if payload.source_column_index in unavailable else 422
        raise ApplicationError("La columna no es una celda vacía disponible.", status_code=status)
    if not payload.value.strip():
        raise ApplicationError("Indique un valor para la celda vacía.", status_code=400)
    reason = payload.reason.strip()
    if not reason:
        raise ApplicationError("Indique el motivo del cambio.", status_code=400)
    try:
        actor = directory.resolve(payload.actor_id)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error
    field = FieldValue(
        id=new_id(),
        block_instance_id=block.id,
        field_name=column.field_name,
        source_column_index=column.source_column_index,
        literal_value=None,
        observed_type="empty",
        logical_state="empty",
    )
    try:
        session.add(field)
        session.flush()
        session.add_all(
            [
                ValueProvenance(
                    id=new_id(),
                    field_value_id=field.id,
                    source_fragment_id=fragment.id,
                    provenance_role="master_baseline",
                ),
                FieldMaintenanceRevision(
                    field_value_id=field.id,
                    sequence=1,
                    before_value=None,
                    after_value=payload.value,
                    actor_id=actor.identifier,
                    actor_assurance=actor.assurance,
                    reason=reason,
                    recorded_at=datetime.now(UTC),
                ),
            ]
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApplicationError(
            "La celda se modificó en paralelo. Recargue antes de guardar.", status_code=409
        ) from error
    return EmptySourceFieldCreated(
        id=field.id,
        source_column_index=column.source_column_index,
        field_name=column.field_name,
        maintained_value=payload.value,
    )
