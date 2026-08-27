from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import (
    BlockInstance,
    ExternalIdentifier,
    FieldValue,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)

router = APIRouter(prefix='/records', tags=['registros'])


class ExternalIdentifierRead(BaseModel):
    source_system: str
    source_identifier: str
    source_version: str


class ProvenanceRead(BaseModel):
    source_fragment_id: str
    document_version_id: str
    locator_type: str
    locator: str
    literal_text: str | None
    provenance_role: str


class FieldValueRead(BaseModel):
    id: str
    field_name: str
    literal_value: str | None
    observed_type: str
    logical_state: str
    provenance: list[ProvenanceRead]


class BlockInstanceRead(BaseModel):
    id: str
    block_type: str
    ordinal: int
    values: list[FieldValueRead]


class TargetRecordRead(BaseModel):
    id: str
    entity_type: str
    external_identifiers: list[ExternalIdentifierRead]
    blocks: list[BlockInstanceRead]


def get_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    with factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


def _provenance(session: Session, field_value_id: str) -> list[ProvenanceRead]:
    rows = session.scalars(
        select(ValueProvenance)
        .where(ValueProvenance.field_value_id == field_value_id)
        .order_by(ValueProvenance.id)
    ).all()
    result = []
    for row in rows:
        fragment = session.get(SourceFragment, row.source_fragment_id)
        if fragment is None:
            raise RuntimeError(f'Procedencia sin fragmento: {row.id}')
        result.append(
            ProvenanceRead(
                source_fragment_id=fragment.id,
                document_version_id=fragment.document_version_id,
                locator_type=fragment.locator_type,
                locator=fragment.locator,
                literal_text=fragment.literal_text,
                provenance_role=row.provenance_role,
            )
        )
    return result


@router.get('/{record_id}', response_model=TargetRecordRead)
def read_record(record_id: str, session: SessionDependency) -> TargetRecordRead:
    record = session.get(TargetRecord, record_id)
    if record is None:
        raise ApplicationError('Registro no encontrado.', status_code=404)
    identifiers = session.scalars(
        select(ExternalIdentifier)
        .where(ExternalIdentifier.target_record_id == record_id)
        .order_by(
            ExternalIdentifier.source_system,
            ExternalIdentifier.source_identifier,
            ExternalIdentifier.source_version,
        )
    ).all()
    blocks = session.scalars(
        select(BlockInstance)
        .where(BlockInstance.target_record_id == record_id)
        .order_by(BlockInstance.ordinal, BlockInstance.id)
    ).all()
    block_payloads = []
    for block in blocks:
        values = session.scalars(
            select(FieldValue)
            .where(FieldValue.block_instance_id == block.id)
            .order_by(FieldValue.field_name, FieldValue.id)
        ).all()
        block_payloads.append(
            BlockInstanceRead(
                id=block.id,
                block_type=block.block_type,
                ordinal=block.ordinal,
                values=[
                    FieldValueRead(
                        id=value.id,
                        field_name=value.field_name,
                        literal_value=value.literal_value,
                        observed_type=value.observed_type,
                        logical_state=value.logical_state,
                        provenance=_provenance(session, value.id),
                    )
                    for value in values
                ],
            )
        )
    return TargetRecordRead(
        id=record.id,
        entity_type=record.entity_type,
        external_identifiers=[
            ExternalIdentifierRead(
                source_system=item.source_system,
                source_identifier=item.source_identifier,
                source_version=item.source_version,
            )
            for item in identifiers
        ],
        blocks=block_payloads,
    )
