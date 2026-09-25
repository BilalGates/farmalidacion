"""Persistencia del estado canónico editable del catálogo (CAT-004)."""

import json
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from pharma_validator_api.catalog_domain import CatalogIdentity
from pharma_validator_api.models import MedicationCatalogIdentity, MedicationCatalogRevision


class CatalogStoreError(ValueError):
    pass


class CatalogVersionConflict(CatalogStoreError):
    pass


def _state(identity: MedicationCatalogIdentity) -> dict[str, object]:
    return {
        "id": identity.id,
        "identity_type": identity.identity_type,
        "code": identity.code,
        "display_name": identity.display_name,
        "target_record_id": identity.target_record_id,
        "source_system": identity.source_system,
        "source_version": identity.source_version,
        "source_literal": identity.source_literal,
        "active": bool(identity.active),
        "version": identity.version,
    }


def _json(state: dict[str, object]) -> str:
    return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def create_identity(
    session: Session,
    identity: CatalogIdentity,
    *,
    source_system: str,
    source_version: str,
    source_literal: str | None,
    source_fragment_id: str | None,
    actor_id: str,
    actor_assurance: str,
    reason: str,
) -> MedicationCatalogIdentity:
    if not actor_id.strip() or not reason.strip():
        raise CatalogStoreError("Crear una identidad exige actor y motivo.")
    row = MedicationCatalogIdentity(
        id=identity.id,
        identity_type=identity.identity_type,
        code=identity.code,
        display_name=identity.display_name,
        target_record_id=identity.target_record_id,
        source_system=source_system,
        source_version=source_version,
        source_literal=source_literal,
        source_fragment_id=source_fragment_id,
        active=True,
        version=1,
    )
    session.add(row)
    session.flush()
    session.add(
        MedicationCatalogRevision(
            identity_id=row.id,
            sequence=1,
            action="crear",
            before_state=None,
            after_state=_json(_state(row)),
            actor_id=actor_id,
            actor_assurance=actor_assurance,
            reason=reason.strip(),
            recorded_at=datetime.now(UTC),
        )
    )
    return row


def revise_identity(
    session: Session,
    identity_id: str,
    *,
    expected_version: int,
    display_name: str,
    code: str | None,
    active: bool,
    actor_id: str,
    actor_assurance: str,
    reason: str,
) -> MedicationCatalogIdentity:
    if not display_name.strip():
        raise CatalogStoreError("El nombre visible no puede estar vacío.")
    if not actor_id.strip() or not reason.strip():
        raise CatalogStoreError("Modificar una identidad exige actor y motivo.")
    current = session.get(MedicationCatalogIdentity, identity_id)
    if current is None:
        raise CatalogStoreError("Identidad no encontrada.")
    before = _json(_state(current))
    new_version = expected_version + 1
    result = cast(
        CursorResult[Any],
        session.execute(
            update(MedicationCatalogIdentity)
            .where(
                MedicationCatalogIdentity.id == identity_id,
                MedicationCatalogIdentity.version == expected_version,
            )
            .values(
                display_name=display_name.strip(),
                code=code.strip() if code is not None else None,
                active=active,
                version=new_version,
            )
        )
    )
    if result.rowcount != 1:
        session.expire_all()
        raise CatalogVersionConflict("El registro cambió desde que se abrió; recárguelo.")
    session.flush()
    revised = session.get(MedicationCatalogIdentity, identity_id)
    if revised is None:  # barrera para el tipado; el UPDATE acaba de afectar una fila
        raise CatalogStoreError("Identidad no encontrada tras modificarla.")
    session.add(
        MedicationCatalogRevision(
            identity_id=identity_id,
            sequence=new_version,
            action="archivar" if not active else "modificar",
            before_state=before,
            after_state=_json(_state(revised)),
            actor_id=actor_id,
            actor_assurance=actor_assurance,
            reason=reason.strip(),
            recorded_at=datetime.now(UTC),
        )
    )
    return revised
