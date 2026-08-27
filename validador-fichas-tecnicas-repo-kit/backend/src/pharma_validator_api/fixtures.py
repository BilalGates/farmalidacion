from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from pharma_validator_api.models import (
    BlockInstance,
    DocumentRecordLink,
    ExternalIdentifier,
    FieldValue,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)


class FixtureConflictError(RuntimeError):
    pass


class FixtureRow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str


class SourceDocumentFixture(FixtureRow):
    source_type: str
    name: str


class SourceDocumentVersionFixture(FixtureRow):
    document_id: str
    content_hash: str
    source_version: str | None
    source_locator: str
    acquired_at: datetime


class SourceFragmentFixture(FixtureRow):
    document_version_id: str
    locator_type: str
    locator: str
    literal_text: str | None


class TargetRecordFixture(FixtureRow):
    entity_type: str


class ExternalIdentifierFixture(FixtureRow):
    target_record_id: str
    source_system: str
    source_identifier: str
    source_version: str


class DocumentRecordLinkFixture(FixtureRow):
    document_version_id: str
    target_record_id: str
    link_type: str


class BlockInstanceFixture(FixtureRow):
    target_record_id: str
    block_type: str
    ordinal: int
    source_fragment_id: str | None


class FieldValueFixture(FixtureRow):
    block_instance_id: str
    field_name: str
    literal_value: str | None
    observed_type: str
    logical_state: str


class ValueProvenanceFixture(FixtureRow):
    field_value_id: str
    source_fragment_id: str
    provenance_role: str


class DemoFixture(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: str
    source_document: SourceDocumentFixture
    source_document_version: SourceDocumentVersionFixture
    source_fragments: list[SourceFragmentFixture]
    target_record: TargetRecordFixture
    external_identifiers: list[ExternalIdentifierFixture]
    document_record_links: list[DocumentRecordLinkFixture]
    block_instances: list[BlockInstanceFixture]
    field_values: list[FieldValueFixture]
    value_provenances: list[ValueProvenanceFixture]


def read_demo_fixture(path: Path) -> DemoFixture:
    return DemoFixture.model_validate_json(path.read_text(encoding='utf-8'))


def _rows(fixture: DemoFixture) -> list[tuple[type[Any], FixtureRow]]:
    return [
        (SourceDocument, fixture.source_document),
        (SourceDocumentVersion, fixture.source_document_version),
        *((SourceFragment, row) for row in fixture.source_fragments),
        (TargetRecord, fixture.target_record),
        *((ExternalIdentifier, row) for row in fixture.external_identifiers),
        *((DocumentRecordLink, row) for row in fixture.document_record_links),
        *((BlockInstance, row) for row in fixture.block_instances),
        *((FieldValue, row) for row in fixture.field_values),
        *((ValueProvenance, row) for row in fixture.value_provenances),
    ]


def load_demo_fixture(session: Session, path: Path) -> bool:
    fixture = read_demo_fixture(path)
    if fixture.schema_version != '1.0.0':
        raise FixtureConflictError(f'Versión de fixture no soportada: {fixture.schema_version}')
    rows = _rows(fixture)
    existing = [session.get(model, row.id) for model, row in rows]
    if any(item is not None for item in existing):
        if not all(item is not None for item in existing):
            raise FixtureConflictError('El fixture colisiona con una carga parcial existente.')
        for item, (_, row) in zip(existing, rows, strict=True):
            if any(
                getattr(item, field) != value
                for field, value in row.model_dump().items()
            ):
                raise FixtureConflictError(
                    'El fixture colisiona con contenido distinto en '
                    f'{type(item).__name__}:{row.id}.'
                )
        return False
    insertion_groups: list[list[tuple[type[Any], FixtureRow]]] = [
        [
            (SourceDocument, fixture.source_document),
            (TargetRecord, fixture.target_record),
        ],
        [
            (SourceDocumentVersion, fixture.source_document_version),
            *((ExternalIdentifier, row) for row in fixture.external_identifiers),
        ],
        [
            *((SourceFragment, row) for row in fixture.source_fragments),
            *((DocumentRecordLink, row) for row in fixture.document_record_links),
        ],
        [(BlockInstance, row) for row in fixture.block_instances],
        [(FieldValue, row) for row in fixture.field_values],
        [(ValueProvenance, row) for row in fixture.value_provenances],
    ]
    for group in insertion_groups:
        session.add_all([model(**row.model_dump()) for model, row in group])
        session.flush()
    session.commit()
    return True
