"""Gestión de la lista de revisores (10.1, D-018).

Alta, cambio de rol y activación. No hay borrado: las reglas y el porqué están
en `reviewer_store`, que es donde se aplican para que no dependan de que cada
endpoint las recuerde.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.models import ReviewerRecord
from pharma_validator_api.records import get_session
from pharma_validator_api.reviewer_identity import ROLE_LABELS, ReviewerIdentityError
from pharma_validator_api.reviewer_store import (
    create_reviewer,
    list_reviewers,
    set_reviewer_active,
    update_reviewer_role,
)

router = APIRouter(prefix="/reviewers", tags=["revisores"])

SessionDependency = Annotated[Session, Depends(get_session)]


class ReviewerRoleRead(BaseModel):
    value: str
    label: str


class ReviewerAdminRead(BaseModel):
    identifier: str
    display_name: str
    role: str
    role_label: str
    active: bool


class ReviewerCreate(BaseModel):
    identifier: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=160)
    role: str


class ReviewerRoleWrite(BaseModel):
    role: str


class ReviewerActiveWrite(BaseModel):
    active: bool


def _read(record: ReviewerRecord) -> ReviewerAdminRead:
    return ReviewerAdminRead(
        identifier=record.identifier,
        display_name=record.display_name,
        role=record.role,
        role_label=ROLE_LABELS.get(record.role, record.role),
        active=record.active,
    )


@router.get("/roles", response_model=list[ReviewerRoleRead])
def read_roles() -> list[ReviewerRoleRead]:
    """Roles disponibles, con su etiqueta visible.

    La pantalla los pide en lugar de llevarlos escritos: así una lista y otra no
    pueden discrepar sobre qué roles existen.
    """
    return [ReviewerRoleRead(value=value, label=label) for value, label in ROLE_LABELS.items()]


@router.get("", response_model=list[ReviewerAdminRead])
def read_reviewers(session: SessionDependency) -> list[ReviewerAdminRead]:
    """Todos los revisores, activos e inactivos.

    Los inactivos se listan aquí a propósito: la pantalla de gestión existe para
    poder reactivarlos, y esconderlos los volvería irrecuperables.
    """
    return [_read(record) for record in list_reviewers(session, include_inactive=True)]


@router.post("", response_model=ReviewerAdminRead, status_code=201)
def add_reviewer(payload: ReviewerCreate, session: SessionDependency) -> ReviewerAdminRead:
    try:
        record = create_reviewer(
            session,
            identifier=payload.identifier,
            display_name=payload.display_name,
            role=payload.role,
        )
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error
    session.commit()
    return _read(record)


@router.put("/{identifier}/role", response_model=ReviewerAdminRead)
def change_role(
    identifier: str, payload: ReviewerRoleWrite, session: SessionDependency
) -> ReviewerAdminRead:
    try:
        record = update_reviewer_role(session, identifier, payload.role)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error
    session.commit()
    return _read(record)


@router.put("/{identifier}/active", response_model=ReviewerAdminRead)
def change_active(
    identifier: str, payload: ReviewerActiveWrite, session: SessionDependency
) -> ReviewerAdminRead:
    try:
        record = set_reviewer_active(session, identifier, payload.active)
    except ReviewerIdentityError as error:
        raise ApplicationError(str(error), status_code=400) from error
    session.commit()
    return _read(record)
