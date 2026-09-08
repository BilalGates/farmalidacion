"""API de edición de bloques repetibles (DEV-507).

No contiene ninguna regla: valida la forma de la petición, comprueba quién
firma y delega en `block_editing_store`, que a su vez delega las decisiones en
el módulo puro `block_editing`. Un error de esas barreras se traduce a 400 con
su mensaje en español, sin reinterpretarlo.

La firma es obligatoria en toda operación. Editar un bloque cambia el modelo
canónico de un registro, y hacerlo sin dejar constancia de quién lo pidió
dejaría un cambio sin autoría, que es exactamente lo que la auditoría de la
especificación 11 tiene que poder reconstruir.
"""

from __future__ import annotations

import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pharma_validator_api.block_editing import BlockEditingError
from pharma_validator_api.block_editing_store import edit_block, edit_history, load_occurrences
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import TargetRecord
from pharma_validator_api.records import DirectoryDependency, SessionDependency
from pharma_validator_api.reviewer_identity import ReviewerDirectory

router = APIRouter(prefix='/records', tags=['bloques'])


class OccurrenceRead(BaseModel):
    occurrence_id: str
    ordinal: int
    values: list[tuple[str, str | None]]
    from_source: bool
    not_applicable: bool
    comment: str | None


class BlockEditWrite(BaseModel):
    """Petición de edición. `reviewer_id` firma la operación."""

    operation: Literal[
        'crear',
        'eliminar',
        'reordenar',
        'fusionar',
        'marcar_no_aplicable',
        'revertir_no_aplicable',
    ]
    reviewer_id: str = Field(min_length=1)
    occurrence_id: str | None = None
    ordered_ids: list[str] | None = None
    source_id: str | None = None
    target_id: str | None = None
    values: list[tuple[str, str | None]] | None = None
    comment: str | None = None


class BlockEditRecordRead(BaseModel):
    sequence: int
    block_type: str
    operation: str
    affected_ids: list[str]
    comment: str | None
    reviewer_id: str
    reviewer_assurance: str
    edited_at: str


def _reviewer_assurance(directory: ReviewerDirectory, reviewer_id: str) -> str:
    """Un revisor desconocido no puede firmar una edición del modelo."""
    for item in directory.reviewers:
        if item.identifier == reviewer_id:
            return item.assurance
    raise ApplicationError('Revisor no reconocido.', status_code=400)


def _require_record(session: Session, record_id: str) -> None:
    if session.get(TargetRecord, record_id) is None:
        raise ApplicationError('Registro no encontrado.', status_code=404)


@router.get('/{record_id}/blocks/{block_type}', response_model=list[OccurrenceRead])
def read_block(
    record_id: str, block_type: str, session: SessionDependency
) -> list[OccurrenceRead]:
    _require_record(session, record_id)
    return [
        OccurrenceRead(
            occurrence_id=item.occurrence_id,
            ordinal=item.ordinal,
            values=list(item.values),
            from_source=item.is_from_source,
            not_applicable=item.not_applicable,
            comment=item.comment,
        )
        for item in load_occurrences(session, record_id, block_type)
    ]


@router.post('/{record_id}/blocks/{block_type}', response_model=list[OccurrenceRead])
def edit_block_endpoint(
    record_id: str,
    block_type: str,
    payload: BlockEditWrite,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> list[OccurrenceRead]:
    """Aplica una operación de bloque en una única transacción.

    Si `block_editing` la rechaza, no se escribe nada: ni el cambio ni su
    rastro. Una operación a medio aplicar dejaría el bloque incoherente.
    """
    _require_record(session, record_id)
    assurance = _reviewer_assurance(directory, payload.reviewer_id)

    kwargs: dict[str, object] = {}
    if payload.occurrence_id is not None:
        kwargs['occurrence_id'] = payload.occurrence_id
    if payload.comment is not None:
        kwargs['comment'] = payload.comment
    if payload.ordered_ids is not None:
        kwargs['ordered_ids'] = tuple(payload.ordered_ids)
    if payload.source_id is not None:
        kwargs['source_id'] = payload.source_id
    if payload.target_id is not None:
        kwargs['target_id'] = payload.target_id
    if payload.values is not None:
        kwargs['values'] = tuple(payload.values)

    if payload.operation == 'crear':
        # El identificador lo asigna el servidor: dejarlo al cliente permitiría
        # colisionar con una ocurrencia existente.
        kwargs.setdefault('occurrence_id', str(uuid4()))
        kwargs.setdefault('values', ())

    try:
        edit_block(
            session,
            target_record_id=record_id,
            block_type=block_type,
            reviewer_id=payload.reviewer_id,
            reviewer_assurance=assurance,
            operation=payload.operation,
            **kwargs,
        )
    except BlockEditingError as error:
        session.rollback()
        # El mensaje explica *por qué* la operación perdería datos.
        raise ApplicationError(str(error), status_code=400) from error
    except KeyError as error:
        session.rollback()
        raise ApplicationError(
            f'Falta un dato obligatorio para la operación: {error}.', status_code=400
        ) from error

    session.commit()
    return read_block(record_id, block_type, session)


@router.get('/{record_id}/block-history', response_model=list[BlockEditRecordRead])
def read_block_history(
    record_id: str, session: SessionDependency
) -> list[BlockEditRecordRead]:
    _require_record(session, record_id)
    return [
        BlockEditRecordRead(
            sequence=item.sequence,
            block_type=item.block_type,
            operation=item.operation,
            affected_ids=json.loads(item.affected_ids),
            comment=item.comment,
            reviewer_id=item.reviewer_id,
            reviewer_assurance=item.reviewer_assurance,
            edited_at=item.edited_at.isoformat(),
        )
        for item in edit_history(session, record_id)
    ]
