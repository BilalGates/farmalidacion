"""API del catálogo tipado y editable (CAT-003/CAT-004)."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_validator_api.catalog_domain import CatalogIdentity, CatalogIdentityType
from pharma_validator_api.catalog_store import (
    CatalogStoreError,
    CatalogVersionConflict,
    create_identity,
    revise_identity,
)
from pharma_validator_api.cima_comparison import (
    CatalogField as ComparisonCatalogField,
)
from pharma_validator_api.cima_comparison import (
    CimaDocument as ComparisonDocument,
)
from pharma_validator_api.cima_comparison import (
    CimaSection as ComparisonSection,
)
from pharma_validator_api.cima_comparison import (
    MasterField as ComparisonMasterField,
)
from pharma_validator_api.cima_comparison import (
    compare_master_fields,
)
from pharma_validator_api.contextual_chat import _sections
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import (
    BlockInstance,
    CatalogCimaReviewDecision,
    CatalogFieldDefinition,
    DocumentRecordLink,
    FieldMaintenanceRevision,
    FieldValue,
    MedicationCatalogClassification,
    MedicationCatalogIdentity,
    MedicationCatalogRelation,
    MedicationCatalogRevision,
    SourceDocument,
    SourceDocumentArtifact,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
)
from pharma_validator_api.national_code import national_code_search_term
from pharma_validator_api.records import DirectoryDependency, SessionDependency
from pharma_validator_api.reviewer_identity import (
    Reviewer,
    ReviewerDirectory,
    ReviewerIdentityError,
)

router = APIRouter(prefix="/catalog", tags=["catálogo"])

SOURCE_WORKBOOKS = {
    "especialidades": "Especialidades-CargaMaster190626.xlsx",
    "medicamentos": "Medicamento-cargaMaster25062026.xlsx",
    "principios_activos": "PrincipioActivoCargaMaster-22062026.xlsx",
}
WORKBOOK_BY_FILENAME = {filename: source for source, filename in SOURCE_WORKBOOKS.items()}
CatalogSourceWorkbook = Literal["especialidades", "medicamentos", "principios_activos"]
CatalogSort = Literal["name_asc", "name_desc", "code_asc", "code_desc"]


class CatalogIdentityRead(BaseModel):
    id: str
    identity_type: str
    code: str | None
    display_name: str
    target_record_id: str | None
    source_system: str
    source_version: str
    source_workbook: str | None = None
    source_literal: str | None
    active: bool
    version: int
    commercial_class: str | None = None
    conditions: list[str] = Field(default_factory=list)


class CatalogIdentityPage(BaseModel):
    items: list[CatalogIdentityRead]
    total: int
    limit: int
    offset: int


class CatalogCimaSection(BaseModel):
    locator: str
    literal_text: str


class CatalogCimaDocument(BaseModel):
    document_name: str
    document_version_id: str
    source_version: str | None
    content_hash: str
    acquired_at: str
    sections: list[CatalogCimaSection]


class CatalogCimaDecisionRead(BaseModel):
    sequence: int
    field_value_id: str
    document_version_id: str
    section_locator: str
    section_content_hash: str
    comparison_status: str
    action: str
    corrected_value: str | None
    actor_id: str
    actor_assurance: str
    reason: str
    recorded_at: str


class CatalogCimaComparisonRead(BaseModel):
    field_value_id: str
    block_type: str
    occurrence: int
    field_name: str
    source_column_index: int | None
    master_value: str | None
    catalog_field_id: str | None
    catalog_classification: str | None
    document_name: str | None
    document_version_id: str | None
    source_version: str | None
    content_hash: str | None
    status: Literal[
        "coincide", "difiere", "falta_registro", "falta_cima", "no_comparable", "requiere_criterio"
    ]
    reason: str
    section_locators: list[str]
    decision_history: list[CatalogCimaDecisionRead] = Field(default_factory=list)


class CatalogCimaDecisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_version_id: str = Field(min_length=1)
    section_locator: str = Field(min_length=1)
    action: Literal["revisado", "corregir", "descartar", "pendiente"]
    corrected_value: str | None = None
    expected_maintenance_sequence: int = Field(ge=0)
    actor_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1)


class CatalogIdentityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=36)
    identity_type: CatalogIdentityType
    code: str | None = None
    display_name: str = Field(min_length=1)
    target_record_id: str | None = None
    actor_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1)


class CatalogIdentityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    display_name: str = Field(min_length=1)
    code: str | None = None
    active: bool = True
    actor_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1)


class CatalogRevisionRead(BaseModel):
    sequence: int
    action: str
    before_state: str | None
    after_state: str
    actor_id: str
    actor_assurance: str
    reason: str
    recorded_at: str


class CatalogRelationRead(BaseModel):
    id: str
    relation_type: str
    direction: str
    ordinal: int | None
    related_identity: CatalogIdentityRead


class CatalogClassificationRead(BaseModel):
    id: str
    classification_type: str
    value: str
    source_system: str
    source_version: str
    source_fragment_id: str | None
    active: bool


class CatalogClassificationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification_type: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=80)
    active: bool = True
    actor_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1)


class CatalogClassificationHistoryRead(BaseModel):
    sequence: int
    action: str
    before_state: str | None
    after_state: str
    actor_id: str
    actor_assurance: str
    reason: str
    recorded_at: str


def _read(
    row: MedicationCatalogIdentity, *, source_workbook: str | None = None
) -> CatalogIdentityRead:
    return CatalogIdentityRead(
        id=row.id,
        identity_type=row.identity_type,
        code=row.code,
        display_name=row.display_name,
        target_record_id=row.target_record_id,
        source_system=row.source_system,
        source_version=row.source_version,
        source_workbook=source_workbook,
        source_literal=row.source_literal,
        active=bool(row.active),
        version=row.version,
    )


def _source_workbook_for_identity(session: Session, row: MedicationCatalogIdentity) -> str | None:
    if not row.source_fragment_id:
        return None
    filename = session.scalar(
        select(SourceDocument.name)
        .join(
            SourceDocumentVersion,
            SourceDocument.id == SourceDocumentVersion.document_id,
        )
        .join(
            SourceFragment,
            SourceDocumentVersion.id == SourceFragment.document_version_id,
        )
        .where(SourceFragment.id == row.source_fragment_id)
    )
    return WORKBOOK_BY_FILENAME.get(filename or "")


def _reviewer(directory: ReviewerDirectory, actor_id: str) -> Reviewer:
    try:
        return directory.resolve(actor_id)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error


def _cima_documents_for_record(
    session: Session, target_record_id: str
) -> list[CatalogCimaDocument]:
    linked = session.execute(
        select(SourceDocument, SourceDocumentVersion)
        .join(SourceDocumentVersion, SourceDocumentVersion.document_id == SourceDocument.id)
        .join(
            DocumentRecordLink,
            DocumentRecordLink.document_version_id == SourceDocumentVersion.id,
        )
        .where(
            DocumentRecordLink.target_record_id == target_record_id,
            DocumentRecordLink.link_type == "ft",
            SourceDocument.source_type == "cima_document_type_1",
        )
        .order_by(
            SourceDocument.id,
            SourceDocumentVersion.acquired_at.desc(),
            SourceDocumentVersion.id.desc(),
        )
    ).all()
    latest: dict[str, tuple[SourceDocument, SourceDocumentVersion]] = {}
    for document, version in linked:
        latest.setdefault(document.id, (document, version))
    result: list[CatalogCimaDocument] = []
    for document, version in latest.values():
        artifacts = session.scalars(
            select(SourceDocumentArtifact)
            .where(
                SourceDocumentArtifact.document_version_id == version.id,
                SourceDocumentArtifact.artifact_role.in_(("section", "full_document")),
            )
            .order_by(SourceDocumentArtifact.ordinal, SourceDocumentArtifact.id)
        ).all()
        for artifact in artifacts:
            if hashlib.sha256(artifact.body).hexdigest() != artifact.content_hash:
                raise ApplicationError(
                    "La ficha técnica archivada no supera la comprobación de integridad.",
                    status_code=409,
                )
        sections = [
            CatalogCimaSection(locator=locator, literal_text=literal)
            for artifact in artifacts
            for locator, literal in _sections(artifact)
        ]
        result.append(
            CatalogCimaDocument(
                document_name=document.name,
                document_version_id=version.id,
                source_version=version.source_version,
                content_hash=version.content_hash,
                acquired_at=version.acquired_at.isoformat(),
                sections=sections,
            )
        )
    return result


def _comparison_inputs(
    session: Session,
    target_record_id: str,
) -> tuple[
    tuple[ComparisonMasterField, ...],
    tuple[ComparisonCatalogField, ...],
    tuple[ComparisonDocument, ...],
]:
    rows = session.execute(
        select(FieldValue, BlockInstance, TargetRecord.entity_type)
        .join(BlockInstance, BlockInstance.id == FieldValue.block_instance_id)
        .join(TargetRecord, TargetRecord.id == BlockInstance.target_record_id)
        .where(BlockInstance.target_record_id == target_record_id)
        .order_by(BlockInstance.block_type, BlockInstance.ordinal, FieldValue.field_name)
    ).all()
    field_ids = [value.id for value, _block, _entity_type in rows]
    revisions = (
        session.scalars(
            select(FieldMaintenanceRevision)
            .where(FieldMaintenanceRevision.field_value_id.in_(field_ids))
            .order_by(
                FieldMaintenanceRevision.field_value_id,
                FieldMaintenanceRevision.sequence,
            )
        ).all()
        if field_ids
        else []
    )
    latest_values = {item.field_value_id: item.after_value for item in revisions}
    fields = tuple(
        ComparisonMasterField(
            id=value.id,
            entity_type=entity_type,
            block_type=block.block_type,
            ordinal=block.ordinal,
            source_column_index=value.source_column_index,
            name=value.field_name,
            value=latest_values.get(value.id, value.literal_value),
        )
        for value, block, entity_type in rows
    )
    definitions = tuple(
        ComparisonCatalogField(
            id=item.id,
            entity=item.entity_literal,
            block=item.block_literal,
            name=item.field_name_literal,
            from_ft=item.from_ft_literal,
            sections=item.ft_section_literal,
        )
        for item in session.scalars(
            select(CatalogFieldDefinition).order_by(CatalogFieldDefinition.source_row_number)
        ).all()
    )
    documents = tuple(
        ComparisonDocument(
            document_name=item.document_name,
            document_version_id=item.document_version_id,
            source_version=item.source_version,
            content_hash=item.content_hash,
            sections=tuple(
                ComparisonSection(locator=section.locator, literal_text=section.literal_text)
                for section in item.sections
            ),
        )
        for item in _cima_documents_for_record(session, target_record_id)
    )
    return fields, definitions, documents


@router.get("/identities", response_model=CatalogIdentityPage)
def list_identities(
    session: SessionDependency,
    identity_type: CatalogIdentityType | None = None,
    commercial_class: str | None = None,
    condition: Annotated[list[str] | None, Query()] = None,
    source_workbook: CatalogSourceWorkbook | None = None,
    sort_by: CatalogSort = "name_asc",
    q: str | None = None,
    active: bool | None = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CatalogIdentityPage:
    statement = select(MedicationCatalogIdentity)
    if source_workbook is not None:
        filename = SOURCE_WORKBOOKS[source_workbook]
        source_fragment_ids = (
            select(SourceFragment.id)
            .join(
                SourceDocumentVersion,
                SourceFragment.document_version_id == SourceDocumentVersion.id,
            )
            .join(
                SourceDocument,
                SourceDocumentVersion.document_id == SourceDocument.id,
            )
            .where(SourceDocument.name == filename)
        )
        statement = statement.where(
            MedicationCatalogIdentity.source_fragment_id.in_(source_fragment_ids)
        )
    if identity_type is not None:
        statement = statement.where(MedicationCatalogIdentity.identity_type == identity_type)
    if active is not None:
        statement = statement.where(MedicationCatalogIdentity.active.is_(active))
    if commercial_class is not None or condition:
        if identity_type not in (None, "presentation"):
            raise ApplicationError(
                "Las clasificaciones sólo pueden filtrar presentaciones.", status_code=422
            )
        classification_query = select(
            MedicationCatalogClassification.presentation_identity_id
        ).where(MedicationCatalogClassification.active.is_(True))
        if commercial_class is not None:
            if commercial_class not in {"original", "generico", "biosimilar", "sin_clasificar"}:
                raise ApplicationError("Clase comercial desconocida.", status_code=422)
            class_query = classification_query.where(
                MedicationCatalogClassification.classification_type == "commercial_class",
                MedicationCatalogClassification.value == commercial_class,
            )
            statement = statement.where(MedicationCatalogIdentity.id.in_(class_query))
        if condition:
            allowed_conditions = {
                "huerfano",
                "estupefaciente",
                "psicotropico",
                "especial_control_medico",
                "uso_hospitalario",
            }
            if any(value not in allowed_conditions for value in condition):
                raise ApplicationError("Condición desconocida.", status_code=422)
            conditions_query = (
                select(MedicationCatalogClassification.presentation_identity_id)
                .where(
                    MedicationCatalogClassification.active.is_(True),
                    MedicationCatalogClassification.classification_type == "condition",
                    MedicationCatalogClassification.value.in_(set(condition)),
                )
                .group_by(MedicationCatalogClassification.presentation_identity_id)
                .having(
                    func.count(func.distinct(MedicationCatalogClassification.value))
                    == len(set(condition))
                )
            )
            condition_query = select(conditions_query.subquery().c.presentation_identity_id)
            statement = statement.where(MedicationCatalogIdentity.id.in_(condition_query))
    if q and q.strip():
        query = q.strip()
        needle = f"%{query}%"
        search_by_name_or_code = MedicationCatalogIdentity.display_name.like(
            needle
        ) | MedicationCatalogIdentity.code.like(needle)
        # Un CN recibido con siete dígitos permite localizar el código de
        # trabajo de seis, pero no valida el control ni crea equivalencias.
        if len(query) == 7 and query.isascii() and query.isdigit():
            canonical_six = national_code_search_term(query)
            statement = statement.where(
                or_(
                    search_by_name_or_code,
                    MedicationCatalogIdentity.code == canonical_six,
                )
            )
        else:
            statement = statement.where(search_by_name_or_code)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    sort_column = (
        MedicationCatalogIdentity.display_name
        if sort_by.startswith("name_")
        else MedicationCatalogIdentity.code
    )
    sort_order = asc if sort_by.endswith("_asc") else desc
    rows = session.scalars(
        statement.order_by(sort_order(sort_column), MedicationCatalogIdentity.id)
        .limit(limit)
        .offset(offset)
    ).all()
    row_ids = [row.id for row in rows]
    fragment_ids = [row.source_fragment_id for row in rows if row.source_fragment_id]
    workbook_by_fragment: dict[str, str] = {}
    if fragment_ids:
        for fragment_id, filename in session.execute(
            select(SourceFragment.id, SourceDocument.name)
            .join(
                SourceDocumentVersion,
                SourceFragment.document_version_id == SourceDocumentVersion.id,
            )
            .join(
                SourceDocument,
                SourceDocumentVersion.document_id == SourceDocument.id,
            )
            .where(SourceFragment.id.in_(fragment_ids))
        ):
            source = WORKBOOK_BY_FILENAME.get(filename)
            if source is not None:
                workbook_by_fragment[fragment_id] = source
    classifications_by_identity: dict[str, list[MedicationCatalogClassification]] = {
        row_id: [] for row_id in row_ids
    }
    if row_ids:
        for classification in session.scalars(
            select(MedicationCatalogClassification)
            .where(MedicationCatalogClassification.presentation_identity_id.in_(row_ids))
            .where(MedicationCatalogClassification.active.is_(True))
            .order_by(
                MedicationCatalogClassification.classification_type,
                MedicationCatalogClassification.value,
            )
        ):
            classifications_by_identity[classification.presentation_identity_id].append(
                classification
            )
    serialized = []
    for row in rows:
        classifications = classifications_by_identity[row.id]
        serialized.append(
            _read(row).model_copy(
                update={
                    "commercial_class": next(
                        (
                            item.value
                            for item in classifications
                            if item.classification_type == "commercial_class"
                        ),
                        None,
                    ),
                    "conditions": [
                        item.value
                        for item in classifications
                        if item.classification_type == "condition"
                    ],
                    "source_workbook": (
                        workbook_by_fragment.get(row.source_fragment_id or "") or None
                    ),
                }
            )
        )
    return CatalogIdentityPage(
        items=serialized,
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/identities/{identity_id}", response_model=CatalogIdentityRead)
def read_identity(identity_id: str, session: SessionDependency) -> CatalogIdentityRead:
    row = session.get(MedicationCatalogIdentity, identity_id)
    if row is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    return _read(row, source_workbook=_source_workbook_for_identity(session, row))


@router.get(
    "/identities/{identity_id}/cima-documents",
    response_model=list[CatalogCimaDocument],
)
def identity_cima_documents(
    identity_id: str, session: SessionDependency
) -> list[CatalogCimaDocument]:
    identity = session.get(MedicationCatalogIdentity, identity_id)
    if identity is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    if identity.target_record_id is None:
        return []
    return _cima_documents_for_record(session, identity.target_record_id)


@router.get(
    "/identities/{identity_id}/cima-comparison",
    response_model=list[CatalogCimaComparisonRead],
)
def identity_cima_comparison(
    identity_id: str, session: SessionDependency
) -> list[CatalogCimaComparisonRead]:
    identity = session.get(MedicationCatalogIdentity, identity_id)
    if identity is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    if identity.target_record_id is None:
        return []
    fields, definitions, documents = _comparison_inputs(session, identity.target_record_id)
    comparisons = compare_master_fields(fields, definitions, documents)
    history_by_field_version: dict[tuple[str, str], list[CatalogCimaDecisionRead]] = {}
    if fields:
        history = session.scalars(
            select(CatalogCimaReviewDecision)
            .where(CatalogCimaReviewDecision.field_value_id.in_([item.id for item in fields]))
            .order_by(
                CatalogCimaReviewDecision.field_value_id,
                CatalogCimaReviewDecision.sequence,
            )
        ).all()
        for row in history:
            history_by_field_version.setdefault(
                (row.field_value_id, row.document_version_id), []
            ).append(
                CatalogCimaDecisionRead(
                    sequence=row.sequence,
                    field_value_id=row.field_value_id,
                    document_version_id=row.document_version_id,
                    section_locator=row.section_locator,
                    section_content_hash=row.section_content_hash,
                    comparison_status=row.comparison_status,
                    action=row.action,
                    corrected_value=row.corrected_value,
                    actor_id=row.actor_id,
                    actor_assurance=row.actor_assurance,
                    reason=row.reason,
                    recorded_at=row.recorded_at.isoformat(),
                )
            )
    return [
        CatalogCimaComparisonRead(
            field_value_id=item.field_value_id,
            block_type=item.block_type,
            occurrence=item.occurrence,
            field_name=item.field_name,
            source_column_index=item.source_column_index,
            master_value=item.master_value,
            catalog_field_id=item.catalog_field_id,
            catalog_classification=item.catalog_classification,
            document_name=item.document_name,
            document_version_id=item.document_version_id,
            source_version=item.source_version,
            content_hash=item.content_hash,
            status=item.status,
            reason=item.reason,
            section_locators=list(item.section_locators),
            decision_history=history_by_field_version.get(
                (item.field_value_id, item.document_version_id or ""), []
            ),
        )
        for item in comparisons
    ]


@router.post(
    "/identities/{identity_id}/cima-comparisons/{field_value_id}/decisions",
    response_model=CatalogCimaDecisionRead,
    status_code=201,
)
def decide_cima_comparison(
    identity_id: str,
    field_value_id: str,
    payload: CatalogCimaDecisionWrite,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> CatalogCimaDecisionRead:
    identity = session.get(MedicationCatalogIdentity, identity_id)
    if identity is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    if identity.target_record_id is None:
        raise ApplicationError(
            "La identidad no tiene registro fuente asociado.",
            status_code=422,
        )
    reviewer = _reviewer(directory, payload.actor_id)
    reason = payload.reason.strip()
    if not reason:
        raise ApplicationError("Indique el motivo de la decisión.", status_code=422)

    fields, definitions, documents = _comparison_inputs(session, identity.target_record_id)
    comparison_field = next((item for item in fields if item.id == field_value_id), None)
    if comparison_field is None:
        raise ApplicationError("El campo no pertenece al registro del expediente.", status_code=404)
    document = next(
        (item for item in documents if item.document_version_id == payload.document_version_id),
        None,
    )
    if document is None:
        raise ApplicationError(
            "La versión CIMA no está vinculada como ficha técnica a este registro.",
            status_code=422,
        )
    result = next(
        (
            item
            for item in compare_master_fields((comparison_field,), definitions, (document,))
            if item.document_version_id == payload.document_version_id
        ),
        None,
    )
    if result is None or result.catalog_field_id is None or result.status == "no_comparable":
        raise ApplicationError(
            "El campo no tiene un mapeo unívoco que permita decidir esta comparación.",
            status_code=422,
        )
    if (
        result.status == "requiere_criterio"
        and payload.action in {"revisado", "corregir"}
        and reviewer.role != "farmaceutico"
    ):
        raise ApplicationError(
            "Esta decisión exige un revisor con rol farmacéutico.", status_code=403
        )
    if payload.section_locator not in result.section_locators:
        raise ApplicationError(
            "El apartado no pertenece a la evidencia candidata de este campo.",
            status_code=422,
        )
    section_rows = [
        section for section in document.sections if section.locator == payload.section_locator
    ]
    if not section_rows:
        raise ApplicationError(
            "El apartado citado no está en la versión archivada.",
            status_code=422,
        )
    section_texts = {item.literal_text for item in section_rows}
    if len(section_texts) != 1:
        raise ApplicationError(
            "El apartado está duplicado con contenido distinto en la versión archivada.",
            status_code=409,
        )
    evidence_hash = hashlib.sha256(next(iter(section_texts)).encode("utf-8")).hexdigest()

    if payload.action == "corregir":
        if payload.corrected_value is None or not payload.corrected_value.strip():
            raise ApplicationError(
                "Indique el valor de trabajo que desea guardar.",
                status_code=422,
            )
    elif payload.corrected_value is not None:
        raise ApplicationError(
            "El valor corregido solo se admite con la acción corregir.", status_code=422
        )

    value = session.get(FieldValue, field_value_id)
    assert value is not None
    maintenance = session.scalars(
        select(FieldMaintenanceRevision)
        .where(FieldMaintenanceRevision.field_value_id == field_value_id)
        .order_by(FieldMaintenanceRevision.sequence.desc())
        .limit(1)
    ).first()
    current_sequence = maintenance.sequence if maintenance else 0
    if current_sequence != payload.expected_maintenance_sequence:
        raise ApplicationError(
            "El valor de trabajo cambió desde que abrió la comparación. Recargue el expediente.",
            status_code=409,
        )
    current_value = maintenance.after_value if maintenance else value.literal_value
    next_sequence = session.scalar(
        select(func.max(CatalogCimaReviewDecision.sequence)).where(
            CatalogCimaReviewDecision.field_value_id == field_value_id
        )
    )
    decision = CatalogCimaReviewDecision(
        field_value_id=field_value_id,
        sequence=(next_sequence or 0) + 1,
        document_version_id=payload.document_version_id,
        catalog_field_definition_id=result.catalog_field_id,
        section_locator=payload.section_locator,
        section_content_hash=evidence_hash,
        comparison_status=result.status,
        action=payload.action,
        corrected_value=payload.corrected_value,
        actor_id=reviewer.identifier,
        actor_assurance=reviewer.assurance,
        reason=reason,
        recorded_at=datetime.now(UTC),
    )
    session.add(decision)
    if payload.action == "corregir":
        session.add(
            FieldMaintenanceRevision(
                field_value_id=field_value_id,
                sequence=current_sequence + 1,
                before_value=current_value,
                after_value=payload.corrected_value,
                actor_id=reviewer.identifier,
                actor_assurance=reviewer.assurance,
                reason=reason,
                recorded_at=decision.recorded_at,
            )
        )
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApplicationError(
            "La comparación cambió en paralelo. Recargue antes de decidir.", status_code=409
        ) from error
    return CatalogCimaDecisionRead(
        sequence=decision.sequence,
        field_value_id=decision.field_value_id,
        document_version_id=decision.document_version_id,
        section_locator=decision.section_locator,
        section_content_hash=decision.section_content_hash,
        comparison_status=decision.comparison_status,
        action=decision.action,
        corrected_value=decision.corrected_value,
        actor_id=decision.actor_id,
        actor_assurance=decision.actor_assurance,
        reason=decision.reason,
        recorded_at=decision.recorded_at.isoformat(),
    )


@router.post("/identities", response_model=CatalogIdentityRead, status_code=201)
def add_identity(
    payload: CatalogIdentityCreate,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> CatalogIdentityRead:
    reviewer = _reviewer(directory, payload.actor_id)
    if (
        payload.target_record_id is not None
        and session.get(TargetRecord, payload.target_record_id) is None
    ):
        raise ApplicationError("Registro canónico relacionado no encontrado.", status_code=404)
    try:
        row = create_identity(
            session,
            CatalogIdentity(
                id=payload.id,
                identity_type=payload.identity_type,
                display_name=payload.display_name,
                code=payload.code,
                target_record_id=payload.target_record_id,
            ),
            source_system="canonical_manual",
            source_version="manual-v1",
            source_literal=None,
            source_fragment_id=None,
            actor_id=reviewer.identifier,
            actor_assurance=reviewer.assurance,
            reason=payload.reason,
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApplicationError(
            "La identidad ya existe o entra en conflicto.", status_code=409
        ) from error
    except CatalogStoreError as error:
        raise ApplicationError(str(error), status_code=400) from error
    return _read(row, source_workbook=_source_workbook_for_identity(session, row))


@router.put("/identities/{identity_id}", response_model=CatalogIdentityRead)
def change_identity(
    identity_id: str,
    payload: CatalogIdentityUpdate,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> CatalogIdentityRead:
    reviewer = _reviewer(directory, payload.actor_id)
    try:
        row = revise_identity(
            session,
            identity_id,
            expected_version=payload.expected_version,
            display_name=payload.display_name,
            code=payload.code,
            active=payload.active,
            actor_id=reviewer.identifier,
            actor_assurance=reviewer.assurance,
            reason=payload.reason,
        )
        session.commit()
    except CatalogVersionConflict as error:
        session.rollback()
        raise ApplicationError(str(error), status_code=409) from error
    except CatalogStoreError as error:
        session.rollback()
        status = 404 if "no encontrada" in str(error) else 400
        raise ApplicationError(str(error), status_code=status) from error
    return _read(row, source_workbook=_source_workbook_for_identity(session, row))


@router.get("/identities/{identity_id}/history", response_model=list[CatalogRevisionRead])
def identity_history(identity_id: str, session: SessionDependency) -> list[CatalogRevisionRead]:
    if session.get(MedicationCatalogIdentity, identity_id) is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    rows = session.scalars(
        select(MedicationCatalogRevision)
        .where(MedicationCatalogRevision.identity_id == identity_id)
        .order_by(MedicationCatalogRevision.sequence)
    ).all()
    return [
        CatalogRevisionRead(
            sequence=row.sequence,
            action=row.action,
            before_state=row.before_state,
            after_state=row.after_state,
            actor_id=row.actor_id,
            actor_assurance=row.actor_assurance,
            reason=row.reason,
            recorded_at=row.recorded_at.isoformat(),
        )
        for row in rows
    ]


@router.get("/identities/{identity_id}/relations", response_model=list[CatalogRelationRead])
def identity_relations(identity_id: str, session: SessionDependency) -> list[CatalogRelationRead]:
    if session.get(MedicationCatalogIdentity, identity_id) is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    rows = session.scalars(
        select(MedicationCatalogRelation)
        .where(
            (MedicationCatalogRelation.source_identity_id == identity_id)
            | (MedicationCatalogRelation.target_identity_id == identity_id)
        )
        .order_by(
            MedicationCatalogRelation.relation_type,
            MedicationCatalogRelation.ordinal,
            MedicationCatalogRelation.id,
        )
    ).all()
    result: list[CatalogRelationRead] = []
    for row in rows:
        outgoing = row.source_identity_id == identity_id
        related_id = row.target_identity_id if outgoing else row.source_identity_id
        related = session.get(MedicationCatalogIdentity, related_id)
        if related is None:
            raise RuntimeError(f"Relación de catálogo sin identidad: {row.id}.")
        result.append(
            CatalogRelationRead(
                id=row.id,
                relation_type=row.relation_type,
                direction="outgoing" if outgoing else "incoming",
                ordinal=row.ordinal,
                related_identity=_read(
                    related, source_workbook=_source_workbook_for_identity(session, related)
                ),
            )
        )
    return result


def _classification_read(row: MedicationCatalogClassification) -> CatalogClassificationRead:
    return CatalogClassificationRead(
        id=row.id,
        classification_type=row.classification_type,
        value=row.value,
        source_system=row.source_system,
        source_version=row.source_version,
        source_fragment_id=row.source_fragment_id,
        active=bool(row.active),
    )


def _classification_state(row: MedicationCatalogClassification) -> str:
    return json.dumps(
        {
            "id": row.id,
            "presentation_identity_id": row.presentation_identity_id,
            "classification_type": row.classification_type,
            "value": row.value,
            "source_system": row.source_system,
            "source_version": row.source_version,
            "source_fragment_id": row.source_fragment_id,
            "active": bool(row.active),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _classification_sequence(session: Session, identity_id: str) -> int:
    current = session.scalar(
        select(func.max(MedicationCatalogRevision.sequence)).where(
            MedicationCatalogRevision.identity_id == identity_id
        )
    )
    return (current or 0) + 1


@router.get(
    "/identities/{identity_id}/classifications",
    response_model=list[CatalogClassificationRead],
)
def identity_classifications(
    identity_id: str,
    session: SessionDependency,
    active: bool | None = True,
) -> list[CatalogClassificationRead]:
    identity = session.get(MedicationCatalogIdentity, identity_id)
    if identity is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    if identity.identity_type != "presentation":
        raise ApplicationError(
            "Las clasificaciones farmacéuticas se asignan a una presentación.",
            status_code=422,
        )
    statement = select(MedicationCatalogClassification).where(
        MedicationCatalogClassification.presentation_identity_id == identity_id
    )
    if active is not None:
        statement = statement.where(MedicationCatalogClassification.active.is_(active))
    rows = session.scalars(
        statement.order_by(
            MedicationCatalogClassification.classification_type,
            MedicationCatalogClassification.value,
        )
    ).all()
    return [_classification_read(row) for row in rows]


@router.put(
    "/identities/{identity_id}/classifications/{classification_id}",
    response_model=CatalogClassificationRead,
)
def set_classification(
    identity_id: str,
    classification_id: str,
    payload: CatalogClassificationWrite,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> CatalogClassificationRead:
    reviewer = _reviewer(directory, payload.actor_id)
    if not payload.reason.strip():
        raise ApplicationError("Indique el motivo del cambio.", status_code=422)
    identity = session.get(MedicationCatalogIdentity, identity_id)
    if identity is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    if identity.identity_type != "presentation":
        raise ApplicationError(
            "Las clasificaciones farmacéuticas se asignan a una presentación.",
            status_code=422,
        )
    if payload.classification_type not in {"commercial_class", "condition"}:
        raise ApplicationError("Tipo de clasificación desconocido.", status_code=422)
    if classification_id != f"{payload.classification_type}:{payload.value}":
        raise ApplicationError(
            "La clasificación de la ruta no coincide con el contenido.", status_code=422
        )
    if payload.classification_type == "commercial_class" and payload.value not in {
        "original",
        "generico",
        "biosimilar",
        "sin_clasificar",
    }:
        raise ApplicationError(
            "La clase comercial no pertenece al catálogo permitido.", status_code=422
        )
    if payload.classification_type == "condition" and payload.value not in {
        "huerfano",
        "estupefaciente",
        "psicotropico",
        "especial_control_medico",
        "uso_hospitalario",
    }:
        raise ApplicationError("La condición no pertenece al catálogo permitido.", status_code=422)
    if payload.classification_type == "commercial_class" and payload.active:
        existing_class = session.scalar(
            select(MedicationCatalogClassification).where(
                MedicationCatalogClassification.presentation_identity_id == identity_id,
                MedicationCatalogClassification.classification_type == "commercial_class",
                MedicationCatalogClassification.active.is_(True),
                MedicationCatalogClassification.value != payload.value,
            )
        )
        if existing_class is not None and not payload.reason.strip():
            raise ApplicationError("Cambiar la clase comercial exige un motivo.", status_code=422)

    statement = select(MedicationCatalogClassification).where(
        MedicationCatalogClassification.presentation_identity_id == identity_id,
        MedicationCatalogClassification.classification_type == payload.classification_type,
        MedicationCatalogClassification.value == payload.value,
    )
    try:
        if payload.classification_type == "commercial_class" and payload.active:
            current_classes = list(
                session.scalars(
                    select(MedicationCatalogClassification).where(
                        MedicationCatalogClassification.presentation_identity_id == identity_id,
                        MedicationCatalogClassification.classification_type == "commercial_class",
                        MedicationCatalogClassification.active.is_(True),
                    )
                )
            )
            for current in current_classes:
                if current.value != payload.value:
                    before_current = _classification_state(current)
                    current.active = False
                    current.source_system = "canonical_manual"
                    current.source_version = "manual-v1"
                    session.flush()
                    session.add(
                        MedicationCatalogRevision(
                            identity_id=identity_id,
                            sequence=_classification_sequence(session, identity_id),
                            action="clasificacion_archivada",
                            before_state=before_current,
                            after_state=_classification_state(current),
                            actor_id=reviewer.identifier,
                            actor_assurance=reviewer.assurance,
                            reason=payload.reason.strip(),
                            recorded_at=datetime.now(UTC),
                        )
                    )

        row = session.scalar(statement)
        if row is None:
            if not payload.active:
                raise ApplicationError(
                    "No existe una clasificación vigente que se pueda archivar.",
                    status_code=404,
                )
            row = MedicationCatalogClassification(
                presentation_identity_id=identity_id,
                classification_type=payload.classification_type,
                value=payload.value,
                source_system="canonical_manual",
                source_version="manual-v1",
                source_fragment_id=None,
                active=True,
            )
            session.add(row)
            session.flush()
            action = "clasificacion_creada"
            before = None
        else:
            before = _classification_state(row)
            row.active = payload.active
            row.source_system = "canonical_manual"
            row.source_version = "manual-v1"
            action = "clasificacion_activada" if payload.active else "clasificacion_archivada"
            session.flush()
        session.add(
            MedicationCatalogRevision(
                identity_id=identity_id,
                sequence=_classification_sequence(session, identity_id),
                action=action,
                before_state=before,
                after_state=_classification_state(row),
                actor_id=reviewer.identifier,
                actor_assurance=reviewer.assurance,
                reason=payload.reason.strip(),
                recorded_at=datetime.now(UTC),
            )
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApplicationError(
            "La clasificación entra en conflicto con otra revisión.", status_code=409
        ) from error
    return _classification_read(row)


@router.get(
    "/identities/{identity_id}/classification-history",
    response_model=list[CatalogClassificationHistoryRead],
)
def classification_history(
    identity_id: str, session: SessionDependency
) -> list[CatalogClassificationHistoryRead]:
    if session.get(MedicationCatalogIdentity, identity_id) is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    actions = ("clasificacion_creada", "clasificacion_activada", "clasificacion_archivada")
    rows = session.scalars(
        select(MedicationCatalogRevision)
        .where(MedicationCatalogRevision.identity_id == identity_id)
        .where(MedicationCatalogRevision.action.in_(actions))
        .order_by(MedicationCatalogRevision.sequence)
    ).all()
    return [
        CatalogClassificationHistoryRead(
            sequence=row.sequence,
            action=row.action,
            before_state=row.before_state,
            after_state=row.after_state,
            actor_id=row.actor_id,
            actor_assurance=row.actor_assurance,
            reason=row.reason,
            recorded_at=row.recorded_at.isoformat(),
        )
        for row in rows
    ]
