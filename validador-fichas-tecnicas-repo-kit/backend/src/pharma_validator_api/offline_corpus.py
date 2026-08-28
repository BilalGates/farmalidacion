from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from pharma_validator_api.cima_client import CimaResponse
from pharma_validator_api.config import Settings
from pharma_validator_api.database import create_database_engine, create_session_factory
from pharma_validator_api.document_versions import (
    ArtifactInput,
    PersistedDocumentVersion,
    persist_cima_document_version,
)

CORPUS_SCHEMA_VERSION = '1.0.0'


class OfflineCorpusError(RuntimeError):
    pass


class CorpusArtifact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    artifact_role: str = Field(min_length=1, max_length=40)
    ordinal: int = Field(gt=0)
    locator: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    source_url: str = Field(pattern=r'^https://')
    status_code: int = Field(ge=200, lt=300)
    headers: list[tuple[str, str]]
    content_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    fetched_at: str


class CorpusDocumentVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    nregistro: str = Field(min_length=1)
    document_type: int = Field(gt=0)
    source_version: str | None
    artifacts: list[CorpusArtifact] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_occurrences(self) -> CorpusDocumentVersion:
        occurrences = [(item.artifact_role, item.ordinal) for item in self.artifacts]
        if len(occurrences) != len(set(occurrences)):
            raise ValueError('El documento contiene ocurrencias de artefacto duplicadas.')
        return self


class CorpusManifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: str
    corpus_id: str = Field(min_length=1)
    corpus_kind: str
    description: str
    documents: list[CorpusDocumentVersion] = Field(min_length=1)


@dataclass(frozen=True)
class VerifiedCorpus:
    root: Path
    manifest: CorpusManifest
    manifest_sha256: str
    total_bytes: int


def _artifact_path(root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or '..' in candidate.parts or candidate.as_posix() != relative_path:
        raise OfflineCorpusError(f'Ruta de artefacto no segura: {relative_path}')
    resolved_root = root.resolve()
    resolved = (root / candidate).resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise OfflineCorpusError(f'Ruta de artefacto fuera del corpus: {relative_path}')
    return resolved


def verify_offline_corpus(root: Path) -> VerifiedCorpus:
    manifest_path = root / 'manifest.json'
    try:
        manifest_body = manifest_path.read_bytes()
    except OSError as exc:
        raise OfflineCorpusError(f'No se puede leer el manifiesto: {manifest_path}') from exc
    try:
        manifest = CorpusManifest.model_validate_json(manifest_body)
    except ValueError as exc:
        raise OfflineCorpusError(f'Manifiesto de corpus incompatible: {exc}') from exc
    if manifest.schema_version != CORPUS_SCHEMA_VERSION:
        raise OfflineCorpusError(f'Versión de corpus no soportada: {manifest.schema_version}')
    if manifest.corpus_kind not in {'synthetic_test_fixture', 'downloaded_cima'}:
        raise OfflineCorpusError(f'Tipo de corpus incompatible: {manifest.corpus_kind}')

    declared: set[Path] = set()
    total_bytes = 0
    for document in manifest.documents:
        for artifact in document.artifacts:
            path = _artifact_path(root, artifact.relative_path)
            if path in declared:
                raise OfflineCorpusError(f'Archivo de artefacto declarado dos veces: {path}')
            declared.add(path)
            try:
                body = path.read_bytes()
            except OSError as exc:
                raise OfflineCorpusError(
                    f'No se puede leer el artefacto: {artifact.relative_path}'
                ) from exc
            actual_hash = hashlib.sha256(body).hexdigest()
            if actual_hash != artifact.content_sha256:
                raise OfflineCorpusError(
                    f'Hash incompatible para {artifact.relative_path}: {actual_hash}'
                )
            total_bytes += len(body)

    actual_files = {
        path.resolve()
        for path in root.rglob('*')
        if path.is_file() and path.resolve() != manifest_path.resolve()
    }
    unexpected = sorted(
        path.relative_to(root.resolve()).as_posix() for path in actual_files - declared
    )
    if unexpected:
        raise OfflineCorpusError(f'Archivos no declarados en el corpus: {unexpected}')
    return VerifiedCorpus(
        root.resolve(), manifest, hashlib.sha256(manifest_body).hexdigest(), total_bytes
    )


def _artifact_input(corpus: VerifiedCorpus, item: CorpusArtifact) -> ArtifactInput:
    body = _artifact_path(corpus.root, item.relative_path).read_bytes()
    return ArtifactInput(
        artifact_role=item.artifact_role,
        ordinal=item.ordinal,
        locator=item.locator,
        response=CimaResponse(
            url=item.source_url,
            status_code=item.status_code,
            headers=tuple(item.headers),
            body=body,
            content_sha256=item.content_sha256,
            fetched_at=item.fetched_at,
            from_cache=True,
        ),
    )


def load_offline_corpus(
    session: Session, corpus: VerifiedCorpus
) -> tuple[PersistedDocumentVersion, ...]:
    results = []
    for document in corpus.manifest.documents:
        results.append(
            persist_cima_document_version(
                session,
                nregistro=document.nregistro,
                document_type=document.document_type,
                source_version=document.source_version,
                artifacts=tuple(_artifact_input(corpus, item) for item in document.artifacts),
            )
        )
    return tuple(results)


def corpus_summary(corpus: VerifiedCorpus) -> dict[str, object]:
    return {
        'schema_version': CORPUS_SCHEMA_VERSION,
        'corpus_id': corpus.manifest.corpus_id,
        'corpus_kind': corpus.manifest.corpus_kind,
        'manifest_sha256': corpus.manifest_sha256,
        'document_versions': len(corpus.manifest.documents),
        'artifacts': sum(len(item.artifacts) for item in corpus.manifest.documents),
        'total_bytes': corpus.total_bytes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Verifica o carga un corpus CIMA offline')
    parser.add_argument('--corpus-dir', type=Path, required=True)
    parser.add_argument('--load', action='store_true', help='Persiste el corpus verificado')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    corpus = verify_offline_corpus(args.corpus_dir)
    if args.load:
        engine = create_database_engine(Settings())
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            loaded = load_offline_corpus(session, corpus)
        summary = {**corpus_summary(corpus), 'created_versions': sum(x.created for x in loaded)}
    else:
        summary = corpus_summary(corpus)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
