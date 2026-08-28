import json
import shutil
import socket
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config

from pharma_validator_api.document_versions import reconstruct_artifact
from pharma_validator_api.models import SourceDocumentArtifact, SourceDocumentVersion
from pharma_validator_api.offline_corpus import (
    OfflineCorpusError,
    corpus_summary,
    load_offline_corpus,
    verify_offline_corpus,
)
from pharma_validator_api.version_diff import create_version_diff

CORPUS = Path(__file__).parents[2] / 'data/examples/cima-offline-corpus'


def migrated_session(tmp_path: Path) -> Session:
    database = tmp_path / 'offline-corpus.db'
    command.upgrade(alembic_config(database), 'head')
    return Session(create_engine(f'sqlite:///{database.as_posix()}'))


def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError('DEV-207 prohíbe acceso de red durante la operación offline.')

    monkeypatch.setattr(socket, 'socket', forbidden_socket)


def test_corpus_verifies_and_loads_idempotently_with_network_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    block_network(monkeypatch)
    corpus = verify_offline_corpus(CORPUS)
    assert corpus_summary(corpus) == {
        'schema_version': '1.0.0',
        'corpus_id': 'dev-207-synthetic-v1',
        'corpus_kind': 'synthetic_test_fixture',
        'manifest_sha256': corpus.manifest_sha256,
        'document_versions': 2,
        'artifacts': 4,
        'total_bytes': 264,
    }

    with migrated_session(tmp_path) as session:
        first = load_offline_corpus(session, corpus)
        second = load_offline_corpus(session, corpus)
        assert [item.created for item in first] == [True, True]
        assert [item.created for item in second] == [False, False]
        assert session.scalar(select(func.count()).select_from(SourceDocumentVersion)) == 2
        assert session.scalar(select(func.count()).select_from(SourceDocumentArtifact)) == 4

        body = reconstruct_artifact(
            session,
            version_id=first[0].version_id,
            artifact_role='section',
            ordinal=1,
        )
        assert body == (CORPUS / 'artifacts/51347-v1-section-1.html').read_bytes()
        report = create_version_diff(
            session,
            old_version_id=first[0].version_id,
            new_version_id=first[1].version_id,
        )
        section = next(item for item in report.changes if item.role == 'section')
        assert section.diff_kind == 'text'
        assert '-<p>Versión uno para pruebas offline.</p>' in (section.text_diff or '')
        assert '+<p>Versión dos para pruebas offline.</p>' in (section.text_diff or '')


def test_corpus_rejects_tampering_and_undeclared_files(tmp_path: Path) -> None:
    copied = tmp_path / 'corpus'
    shutil.copytree(CORPUS, copied)
    target = copied / 'artifacts/51347-v1-section-1.html'
    target.write_bytes(target.read_bytes() + b'alterado')
    with pytest.raises(OfflineCorpusError, match='Hash incompatible'):
        verify_offline_corpus(copied)

    shutil.rmtree(copied)
    shutil.copytree(CORPUS, copied)
    (copied / 'no-declarado.txt').write_text('dato sin manifiesto', encoding='utf-8')
    with pytest.raises(OfflineCorpusError, match='Archivos no declarados'):
        verify_offline_corpus(copied)


def test_corpus_rejects_path_escape_and_duplicate_occurrence(tmp_path: Path) -> None:
    copied = tmp_path / 'corpus'
    shutil.copytree(CORPUS, copied)
    manifest_path = copied / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['documents'][0]['artifacts'][0]['relative_path'] = '../fuera.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(OfflineCorpusError, match='Ruta de artefacto no segura'):
        verify_offline_corpus(copied)

    shutil.rmtree(copied)
    shutil.copytree(CORPUS, copied)
    manifest_path = copied / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    duplicate = dict(manifest['documents'][0]['artifacts'][0])
    duplicate['relative_path'] = manifest['documents'][1]['artifacts'][0]['relative_path']
    manifest['documents'][0]['artifacts'].append(duplicate)
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(OfflineCorpusError, match='ocurrencias de artefacto duplicadas'):
        verify_offline_corpus(copied)
