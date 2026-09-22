import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pharma_validator_api.catalog_domain import CatalogIdentity
from pharma_validator_api.catalog_store import (
    CatalogStoreError,
    CatalogVersionConflict,
    create_identity,
    revise_identity,
)
from pharma_validator_api.models import (
    ImmutableHistoryError,
    MedicationCatalogIdentity,
    MedicationCatalogRevision,
)


def create_presentation(session: Session) -> MedicationCatalogIdentity:
    return create_identity(
        session,
        CatalogIdentity(
            id="presentation-1",
            identity_type="presentation",
            display_name="Producto ejemplo, 20 comprimidos",
            code="654789",
        ),
        source_system="synthetic_acceptance",
        source_version="v1",
        source_literal="6547892",
        source_fragment_id=None,
        actor_id="ana",
        actor_assurance="declarada",
        reason="Alta del caso de aceptación.",
    )


def test_create_and_revise_preserve_append_only_history(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        created = create_presentation(session)
        session.commit()
        assert created.version == 1
        assert created.source_literal == "6547892"

        revised = revise_identity(
            session,
            created.id,
            expected_version=1,
            display_name="Producto ejemplo, 40 comprimidos",
            code="654789",
            active=True,
            actor_id="ana",
            actor_assurance="declarada",
            reason="Corrección del contenido del envase.",
        )
        session.commit()

        assert revised.version == 2
        history = list(
            session.scalars(
                select(MedicationCatalogRevision)
                .where(MedicationCatalogRevision.identity_id == created.id)
                .order_by(MedicationCatalogRevision.sequence)
            )
        )
        assert [item.action for item in history] == ["crear", "modificar"]
        assert json.loads(history[0].after_state)["display_name"] == (
            "Producto ejemplo, 20 comprimidos"
        )
        assert json.loads(history[1].before_state or "{}")["version"] == 1
        assert json.loads(history[1].after_state)["version"] == 2


def test_stale_version_writes_neither_change_nor_history(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        created = create_presentation(session)
        session.commit()
        revise_identity(
            session,
            created.id,
            expected_version=1,
            display_name="Versión dos",
            code="654789",
            active=True,
            actor_id="ana",
            actor_assurance="declarada",
            reason="Primera edición.",
        )
        session.commit()

        with pytest.raises(CatalogVersionConflict, match="cambió desde que se abrió"):
            revise_identity(
                session,
                created.id,
                expected_version=1,
                display_name="Edición obsoleta",
                code="654789",
                active=True,
                actor_id="luis",
                actor_assurance="declarada",
                reason="Intento concurrente.",
            )
        session.rollback()

        current = session.get(MedicationCatalogIdentity, created.id)
        assert current is not None
        assert current.display_name == "Versión dos"
        assert current.version == 2
        assert len(
            list(
                session.scalars(
                    select(MedicationCatalogRevision).where(
                        MedicationCatalogRevision.identity_id == created.id
                    )
                )
            )
        ) == 2


def test_archiving_keeps_the_identity_and_source_literal(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        created = create_presentation(session)
        session.commit()
        archived = revise_identity(
            session,
            created.id,
            expected_version=1,
            display_name=created.display_name,
            code=created.code,
            active=False,
            actor_id="ana",
            actor_assurance="declarada",
            reason="Presentación sustituida.",
        )
        session.commit()

        assert not archived.active
        assert archived.source_literal == "6547892"
        assert session.get(MedicationCatalogIdentity, created.id) is not None


def test_revision_cannot_be_updated_or_deleted(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        create_presentation(session)
        session.commit()
        revision = session.scalar(select(MedicationCatalogRevision))
        assert revision is not None
        revision.reason = "Reescritura prohibida"
        with pytest.raises(ImmutableHistoryError):
            session.commit()


def test_actor_and_reason_are_required(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session, pytest.raises(CatalogStoreError, match="actor y motivo"):
        create_identity(
            session,
            CatalogIdentity("id", "dcp", "Producto clínico"),
            source_system="manual",
            source_version="v1",
            source_literal=None,
            source_fragment_id=None,
            actor_id="",
            actor_assurance="declarada",
            reason="",
        )
