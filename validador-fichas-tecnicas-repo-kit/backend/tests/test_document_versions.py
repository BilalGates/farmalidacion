import hashlib
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, func, inspect, select, update
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config

from pharma_validator_api.cima_client import CimaResponse
from pharma_validator_api.document_versions import (
    ArtifactInput,
    DocumentVersionConflictError,
    DocumentVersionError,
    persist_cima_document_version,
    reconstruct_artifact,
)
from pharma_validator_api.models import (
    ImmutableHistoryError,
    SourceDocumentArtifact,
    SourceDocumentVersion,
)


def response(
    body: bytes,
    *,
    url: str,
    content_type: str = 'application/json',
    fetched_at: str = '2026-08-27T08:00:00+00:00',
    extra_headers: tuple[tuple[str, str], ...] = (),
) -> CimaResponse:
    return CimaResponse(
        url=url,
        status_code=200,
        headers=(('Content-Type', content_type), *extra_headers),
        body=body,
        content_sha256=hashlib.sha256(body).hexdigest(),
        fetched_at=fetched_at,
        from_cache=False,
    )


def artifacts(section_two: bytes = b'\xffseccion dos') -> tuple[ArtifactInput, ...]:
    return (
        ArtifactInput(
            artifact_role='metadata',
            ordinal=1,
            locator='medicamento',
            response=response(
                b'{nregistro:51347}',
                url='https://cima.example.test/rest/medicamento?nregistro=51347',
            ),
        ),
        ArtifactInput(
            artifact_role='section',
            ordinal=1,
            locator='1',
            response=response(
                b'<p>seccion uno</p>',
                url='https://cima.example.test/rest/docSegmentado/contenido/1?nregistro=51347&seccion=1',
                content_type='text/html; charset=utf-8',
            ),
        ),
        ArtifactInput(
            artifact_role='section',
            ordinal=2,
            locator='2',
            response=response(
                section_two,
                url='https://cima.example.test/rest/docSegmentado/contenido/1?nregistro=51347&seccion=2',
                content_type='application/octet-stream',
            ),
        ),
    )


def migrated_session(tmp_path: Path) -> tuple[Session, Path]:
    database_path = tmp_path / 'versions.db'
    command.upgrade(alembic_config(database_path), 'head')
    engine = create_engine(f'sqlite:///{database_path.as_posix()}')
    return Session(engine), database_path


def test_identical_ingestion_is_idempotent_and_reconstructs_exact_bytes(tmp_path: Path) -> None:
    session, _ = migrated_session(tmp_path)
    with session:
        first = persist_cima_document_version(
            session,
            nregistro='51347',
            document_type=1,
            artifacts=artifacts(),
            source_version='revision-literal-1',
        )
        second = persist_cima_document_version(
            session,
            nregistro='51347',
            document_type=1,
            artifacts=artifacts(),
            source_version='revision-literal-1',
        )

        assert first.created is True
        assert second.created is False
        assert first == second.__class__(
            second.document_id,
            second.version_id,
            second.content_hash,
            True,
        )
        assert session.scalar(select(func.count()).select_from(SourceDocumentVersion)) == 1
        assert session.scalar(select(func.count()).select_from(SourceDocumentArtifact)) == 3
        assert reconstruct_artifact(
            session,
            version_id=first.version_id,
            artifact_role='section',
            ordinal=2,
        ) == b'\xffseccion dos'


def test_changed_content_creates_new_version_without_overwriting_old(tmp_path: Path) -> None:
    session, _ = migrated_session(tmp_path)
    with session:
        first = persist_cima_document_version(
            session,
            nregistro='51347',
            document_type=1,
            artifacts=artifacts(),
        )
        changed = persist_cima_document_version(
            session,
            nregistro='51347',
            document_type=1,
            artifacts=artifacts(b'nueva seccion dos'),
        )

        assert first.version_id != changed.version_id
        assert session.scalar(select(func.count()).select_from(SourceDocumentVersion)) == 2
        assert session.scalar(select(func.count()).select_from(SourceDocumentArtifact)) == 6
        assert reconstruct_artifact(
            session,
            version_id=first.version_id,
            artifact_role='section',
            ordinal=2,
        ) == b'\xffseccion dos'
        assert reconstruct_artifact(
            session,
            version_id=changed.version_id,
            artifact_role='section',
            ordinal=2,
        ) == b'nueva seccion dos'


def test_metadata_collision_and_persisted_corruption_fail_visibly(tmp_path: Path) -> None:
    session, _ = migrated_session(tmp_path)
    with session:
        persisted = persist_cima_document_version(
            session,
            nregistro='51347',
            document_type=1,
            artifacts=artifacts(),
        )
        changed_headers = list(artifacts())
        original = changed_headers[0]
        changed_headers[0] = ArtifactInput(
            artifact_role=original.artifact_role,
            ordinal=original.ordinal,
            locator=original.locator,
            response=response(
                original.response.body,
                url=original.response.url,
                extra_headers=(('ETag', 'distinto'),),
            ),
        )
        with pytest.raises(DocumentVersionConflictError, match='Artefacto persistido incompatible'):
            persist_cima_document_version(
                session,
                nregistro='51347',
                document_type=1,
                artifacts=tuple(changed_headers),
            )

        stored = session.scalar(
            select(SourceDocumentArtifact).where(
                SourceDocumentArtifact.document_version_id == persisted.version_id,
                SourceDocumentArtifact.artifact_role == 'section',
                SourceDocumentArtifact.ordinal == 1,
            )
        )
        assert stored is not None
        stored.body = b'corrupto'
        with pytest.raises(ImmutableHistoryError, match='inmutables'):
            session.commit()
        session.rollback()
        session.execute(
            update(SourceDocumentArtifact)
            .where(SourceDocumentArtifact.id == stored.id)
            .values(body=b'corrupto')
        )
        session.commit()
        with pytest.raises(DocumentVersionConflictError, match='Hash de artefacto'):
            reconstruct_artifact(
                session,
                version_id=persisted.version_id,
                artifact_role='section',
                ordinal=1,
            )


def test_invalid_or_duplicate_artifact_occurrences_are_rejected(tmp_path: Path) -> None:
    session, _ = migrated_session(tmp_path)
    with session:
        duplicate = (artifacts()[0], artifacts()[0])
        with pytest.raises(DocumentVersionError, match='repetida'):
            persist_cima_document_version(
                session,
                nregistro='51347',
                document_type=1,
                artifacts=duplicate,
            )


def test_artifact_migration_is_reversible(tmp_path: Path) -> None:
    database_path = tmp_path / 'migration.db'
    config = alembic_config(database_path)
    command.upgrade(config, 'head')
    engine = create_engine(f'sqlite:///{database_path.as_posix()}')
    assert 'source_document_artifact' in inspect(engine).get_table_names()

    command.downgrade(config, 'c42aaebd13a8')
    assert 'source_document_artifact' not in inspect(engine).get_table_names()
