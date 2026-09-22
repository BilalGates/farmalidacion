"""API del catálogo tipado y editable (CAT-003/CAT-004)."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from pharma_validator_api.catalog_domain import CatalogIdentity, CatalogIdentityType
from pharma_validator_api.catalog_store import (
    CatalogStoreError,
    CatalogVersionConflict,
    create_identity,
    revise_identity,
)
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import (
    MedicationCatalogIdentity,
    MedicationCatalogRelation,
    MedicationCatalogRevision,
    TargetRecord,
)
from pharma_validator_api.records import DirectoryDependency, SessionDependency
from pharma_validator_api.reviewer_identity import (
    Reviewer,
    ReviewerDirectory,
    ReviewerIdentityError,
)

router = APIRouter(prefix="/catalog", tags=["catálogo"])


class CatalogIdentityRead(BaseModel):
    id: str
    identity_type: str
    code: str | None
    display_name: str
    target_record_id: str | None
    source_system: str
    source_version: str
    source_literal: str | None
    active: bool
    version: int


class CatalogIdentityPage(BaseModel):
    items: list[CatalogIdentityRead]
    total: int
    limit: int
    offset: int


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


def _read(row: MedicationCatalogIdentity) -> CatalogIdentityRead:
    return CatalogIdentityRead(
        id=row.id,
        identity_type=row.identity_type,
        code=row.code,
        display_name=row.display_name,
        target_record_id=row.target_record_id,
        source_system=row.source_system,
        source_version=row.source_version,
        source_literal=row.source_literal,
        active=bool(row.active),
        version=row.version,
    )


def _reviewer(directory: ReviewerDirectory, actor_id: str) -> Reviewer:
    try:
        return directory.resolve(actor_id)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error


@router.get("/identities", response_model=CatalogIdentityPage)
def list_identities(
    session: SessionDependency,
    identity_type: CatalogIdentityType | None = None,
    q: str | None = None,
    active: bool | None = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CatalogIdentityPage:
    statement = select(MedicationCatalogIdentity)
    if identity_type is not None:
        statement = statement.where(MedicationCatalogIdentity.identity_type == identity_type)
    if active is not None:
        statement = statement.where(MedicationCatalogIdentity.active.is_(active))
    if q and q.strip():
        needle = f"%{q.strip()}%"
        statement = statement.where(
            MedicationCatalogIdentity.display_name.like(needle)
            | MedicationCatalogIdentity.code.like(needle)
        )
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.scalars(
        statement.order_by(
            MedicationCatalogIdentity.display_name,
            MedicationCatalogIdentity.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return CatalogIdentityPage(
        items=[_read(row) for row in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/identities/{identity_id}", response_model=CatalogIdentityRead)
def read_identity(identity_id: str, session: SessionDependency) -> CatalogIdentityRead:
    row = session.get(MedicationCatalogIdentity, identity_id)
    if row is None:
        raise ApplicationError("Identidad de catálogo no encontrada.", status_code=404)
    return _read(row)


@router.post("/identities", response_model=CatalogIdentityRead, status_code=201)
def add_identity(
    payload: CatalogIdentityCreate,
    session: SessionDependency,
    directory: DirectoryDependency,
) -> CatalogIdentityRead:
    reviewer = _reviewer(directory, payload.actor_id)
    if payload.target_record_id is not None and session.get(
        TargetRecord, payload.target_record_id
    ) is None:
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
    return _read(row)


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
    return _read(row)


@router.get("/identities/{identity_id}/history", response_model=list[CatalogRevisionRead])
def identity_history(
    identity_id: str, session: SessionDependency
) -> list[CatalogRevisionRead]:
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


@router.get(
    "/identities/{identity_id}/relations", response_model=list[CatalogRelationRead]
)
def identity_relations(
    identity_id: str, session: SessionDependency
) -> list[CatalogRelationRead]:
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
                related_identity=_read(related),
            )
        )
    return result
