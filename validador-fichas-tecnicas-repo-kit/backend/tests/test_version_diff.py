import hashlib
from pathlib import Path

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config
from test_document_versions import response

from pharma_validator_api.document_versions import (
    ArtifactInput,
    DocumentVersionConflictError,
    DocumentVersionError,
    persist_cima_document_version,
)
from pharma_validator_api.models import SourceDocumentArtifact
from pharma_validator_api.sampling import SamplingPersistenceError
from pharma_validator_api.version_diff import create_version_diff, write_version_diff


def old_artifacts() -> tuple[ArtifactInput, ...]:
    return (
        ArtifactInput(
            'metadata',
            1,
            'medicamento',
            response(
                b'{nregistro:51347}',
                url='https://cima.example.test/medicamento?nregistro=51347',
            ),
        ),
        ArtifactInput(
            'section',
            1,
            '1',
            response(
                'título\nlínea anterior\n'.encode(),
                url='https://cima.example.test/contenido?seccion=1',
                content_type='text/plain; charset=utf-8',
            ),
        ),
        ArtifactInput(
            'section',
            2,
            '2',
            response(
                b'\xffbinario anterior',
                url='https://cima.example.test/contenido?seccion=2',
                content_type='application/octet-stream',
            ),
        ),
        ArtifactInput(
            'section',
            4,
            '4',
            response(
                b'eliminada',
                url='https://cima.example.test/contenido?seccion=4',
                content_type='text/plain',
            ),
        ),
    )


def new_artifacts() -> tuple[ArtifactInput, ...]:
    return (
        old_artifacts()[0],
        ArtifactInput(
            'section',
            1,
            '1',
            response(
                'título\nlínea nueva\n'.encode(),
                url='https://cima.example.test/contenido?seccion=1',
                content_type='text/plain; charset=utf-8',
            ),
        ),
        ArtifactInput(
            'section',
            2,
            '2',
            response(
                b'\xffbinario nuevo',
                url='https://cima.example.test/contenido?seccion=2',
                content_type='application/octet-stream',
            ),
        ),
        ArtifactInput(
            'section',
            3,
            '3',
            response(
                b'anadida',
                url='https://cima.example.test/contenido?seccion=3',
                content_type='text/plain',
            ),
        ),
    )


def session_for(tmp_path: Path) -> Session:
    database = tmp_path / 'diff.db'
    from alembic import command

    command.upgrade(alembic_config(database), 'head')
    return Session(create_engine(f'sqlite:///{database.as_posix()}'))


def persisted_versions(session: Session) -> tuple[str, str]:
    old = persist_cima_document_version(
        session,
        nregistro='51347',
        document_type=1,
        artifacts=old_artifacts(),
        source_version='revisión literal anterior',
    )
    new = persist_cima_document_version(
        session,
        nregistro='51347',
        document_type=1,
        artifacts=new_artifacts(),
        source_version='revisión literal nueva',
    )
    return old.version_id, new.version_id


def test_diff_classifies_all_changes_and_preserves_binary_without_decoding(
    tmp_path: Path,
) -> None:
    with session_for(tmp_path) as session:
        old_id, new_id = persisted_versions(session)
        report = create_version_diff(
            session,
            old_version_id=old_id,
            new_version_id=new_id,
        )

    changes = {(item.role, item.ordinal): item for item in report.changes}
    assert changes[('metadata', 1)].change_type == 'unchanged'
    assert changes[('section', 1)].change_type == 'modified'
    assert changes[('section', 1)].diff_kind == 'text'
    assert '-línea anterior' in (changes[('section', 1)].text_diff or '')
    assert '+línea nueva' in (changes[('section', 1)].text_diff or '')
    assert changes[('section', 2)].diff_kind == 'binary_or_undecodable'
    assert changes[('section', 2)].text_diff is None
    assert changes[('section', 2)].old_media_type == 'application/octet-stream'
    assert changes[('section', 2)].new_media_type == 'application/octet-stream'
    assert changes[('section', 3)].change_type == 'added'
    assert changes[('section', 4)].change_type == 'removed'
    assert report.old_source_version == 'revisión literal anterior'
    assert report.new_source_version == 'revisión literal nueva'


def test_diff_is_directional_reproducible_and_outputs_are_immutable(tmp_path: Path) -> None:
    with session_for(tmp_path) as session:
        old_id, new_id = persisted_versions(session)
        first = create_version_diff(session, old_version_id=old_id, new_version_id=new_id)
        second = create_version_diff(session, old_version_id=old_id, new_version_id=new_id)
        reverse = create_version_diff(session, old_version_id=new_id, new_version_id=old_id)

    assert first == second
    assert first.report_id != reverse.report_id
    output = tmp_path / 'report'
    paths = write_version_diff(output, first)
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert write_version_diff(output, second) == paths
    assert hashes == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    with pytest.raises(SamplingPersistenceError, match='Diff existente incompatible'):
        write_version_diff(output, reverse)


def test_metadata_only_change_is_visible_without_fabricating_text_diff(tmp_path: Path) -> None:
    with session_for(tmp_path) as session:
        old = persist_cima_document_version(
            session,
            nregistro='51347',
            document_type=1,
            artifacts=old_artifacts(),
        )
        changed = list(old_artifacts())
        original = changed[1]
        changed[1] = ArtifactInput('section', 1, '1-renombrada', original.response)
        new = persist_cima_document_version(
            session,
            nregistro='51347',
            document_type=1,
            artifacts=tuple(changed),
        )
        report = create_version_diff(
            session,
            old_version_id=old.version_id,
            new_version_id=new.version_id,
        )

    item = next(
        change
        for change in report.changes
        if change.role == 'section' and change.ordinal == 1
    )
    assert item.change_type == 'modified'
    assert item.diff_kind == 'metadata_only'
    assert item.changed_metadata == ('locator',)
    assert item.text_diff is None


def test_cross_document_and_corrupt_artifact_fail_visibly(tmp_path: Path) -> None:
    with session_for(tmp_path) as session:
        old_id, new_id = persisted_versions(session)
        other = persist_cima_document_version(
            session,
            nregistro='99999',
            document_type=1,
            artifacts=old_artifacts(),
        )
        with pytest.raises(DocumentVersionError, match='documentos distintos'):
            create_version_diff(
                session,
                old_version_id=old_id,
                new_version_id=other.version_id,
            )

        artifact = session.query(SourceDocumentArtifact).filter_by(
            document_version_id=new_id,
            artifact_role='section',
            ordinal=1,
        ).one()
        session.execute(
            update(SourceDocumentArtifact)
            .where(SourceDocumentArtifact.id == artifact.id)
            .values(body=b'corrupto')
        )
        session.commit()
        with pytest.raises(DocumentVersionConflictError, match='Hash de artefacto'):
            create_version_diff(session, old_version_id=old_id, new_version_id=new_id)
