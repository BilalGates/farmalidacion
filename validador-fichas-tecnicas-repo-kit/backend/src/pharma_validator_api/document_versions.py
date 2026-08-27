from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_client import CimaResponse
from pharma_validator_api.models import (
    SourceDocument,
    SourceDocumentArtifact,
    SourceDocumentVersion,
)


class DocumentVersionError(RuntimeError):
    pass


class DocumentVersionConflictError(DocumentVersionError):
    pass


@dataclass(frozen=True)
class ArtifactInput:
    artifact_role: str
    ordinal: int
    locator: str
    response: CimaResponse


@dataclass(frozen=True)
class PersistedDocumentVersion:
    document_id: str
    version_id: str
    content_hash: str
    created: bool


def _response_headers(response: CimaResponse) -> str:
    return json.dumps(
        list(response.headers),
        ensure_ascii=False,
        separators=(',', ':'),
    )


def _fetched_at(response: CimaResponse) -> datetime:
    try:
        value = datetime.fromisoformat(response.fetched_at)
    except ValueError as exc:
        raise DocumentVersionError(
            f'Fecha de captura CIMA incompatible: {response.fetched_at}'
        ) from exc
    if value.tzinfo is None:
        raise DocumentVersionError('La fecha de captura CIMA debe incluir zona horaria.')
    return value


def _validate_artifacts(artifacts: tuple[ArtifactInput, ...]) -> None:
    if not artifacts:
        raise DocumentVersionError('La versión documental requiere al menos un artefacto.')
    occurrences: set[tuple[str, int]] = set()
    for artifact in artifacts:
        occurrence = (artifact.artifact_role, artifact.ordinal)
        if (
            not artifact.artifact_role
            or len(artifact.artifact_role) > 40
            or artifact.ordinal <= 0
            or not artifact.locator
        ):
            raise DocumentVersionError(f'Ocurrencia documental incompatible: {occurrence}')
        if occurrence in occurrences:
            raise DocumentVersionError(f'Ocurrencia documental repetida: {occurrence}')
        occurrences.add(occurrence)
        response = artifact.response
        if not httpx.URL(response.url).is_absolute_url or not response.url.startswith('https://'):
            raise DocumentVersionError(f'URL de fuente CIMA incompatible: {response.url}')
        if response.status_code < 200 or response.status_code >= 300:
            raise DocumentVersionError(f'Respuesta CIMA no exitosa: {response.status_code}')
        if hashlib.sha256(response.body).hexdigest() != response.content_sha256:
            raise DocumentVersionError(f'Hash de respuesta CIMA incompatible: {response.url}')
        _fetched_at(response)


def _package_hash(
    artifacts: tuple[ArtifactInput, ...],
    *,
    source_version: str | None,
) -> str:
    manifest = {
        'schema_version': '1.0.0',
        'source_version': source_version,
        'artifacts': [
            {
                'artifact_role': artifact.artifact_role,
                'ordinal': artifact.ordinal,
                'locator': artifact.locator,
                'source_url': artifact.response.url,
                'status_code': artifact.response.status_code,
                'media_type': artifact.response.content_type,
                'content_hash': artifact.response.content_sha256,
            }
            for artifact in sorted(
                artifacts,
                key=lambda item: (item.artifact_role, item.ordinal),
            )
        ],
    }
    body = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(body).hexdigest()


def _assert_existing_version(
    session: Session,
    version: SourceDocumentVersion,
    artifacts: tuple[ArtifactInput, ...],
    *,
    source_version: str | None,
    source_locator: str,
) -> None:
    if version.source_version != source_version or version.source_locator != source_locator:
        raise DocumentVersionConflictError(f'Versión fuente incompatible: {version.id}')
    stored = session.scalars(
        select(SourceDocumentArtifact)
        .where(SourceDocumentArtifact.document_version_id == version.id)
        .order_by(SourceDocumentArtifact.artifact_role, SourceDocumentArtifact.ordinal)
    ).all()
    expected = sorted(artifacts, key=lambda item: (item.artifact_role, item.ordinal))
    if len(stored) != len(expected):
        raise DocumentVersionConflictError(f'Artefactos persistidos incompatibles: {version.id}')
    for current, artifact in zip(stored, expected, strict=True):
        response = artifact.response
        current_values = (
            current.artifact_role,
            current.ordinal,
            current.locator,
            current.source_url,
            current.status_code,
            current.media_type,
            current.response_headers,
            current.content_hash,
            current.body,
            current.fetched_at,
        )
        expected_values = (
            artifact.artifact_role,
            artifact.ordinal,
            artifact.locator,
            response.url,
            response.status_code,
            response.content_type,
            _response_headers(response),
            response.content_sha256,
            response.body,
            response.fetched_at,
        )
        if current_values != expected_values:
            raise DocumentVersionConflictError(
                'Artefacto persistido incompatible: '
                f'{version.id}/{artifact.artifact_role}/{artifact.ordinal}'
            )


def persist_cima_document_version(
    session: Session,
    *,
    nregistro: str,
    document_type: int,
    artifacts: tuple[ArtifactInput, ...],
    source_version: str | None = None,
) -> PersistedDocumentVersion:
    if not nregistro or document_type <= 0:
        raise DocumentVersionError('Identidad documental CIMA incompatible.')
    _validate_artifacts(artifacts)
    source_type = f'cima_document_type_{document_type}'
    documents = session.scalars(
        select(SourceDocument).where(
            SourceDocument.source_type == source_type,
            SourceDocument.name == nregistro,
        )
    ).all()
    if len(documents) > 1:
        raise DocumentVersionConflictError(
            f'Identidad documental CIMA duplicada: {source_type}/{nregistro}'
        )
    if documents:
        document = documents[0]
    else:
        document = SourceDocument(source_type=source_type, name=nregistro)
        session.add(document)
        session.flush()

    content_hash = _package_hash(artifacts, source_version=source_version)
    source_locator = f'cima:nregistro:{nregistro}:document-type:{document_type}'
    versions = session.scalars(
        select(SourceDocumentVersion).where(
            SourceDocumentVersion.document_id == document.id,
            SourceDocumentVersion.content_hash == content_hash,
        )
    ).all()
    if len(versions) > 1:
        raise DocumentVersionConflictError(f'Hash documental duplicado: {content_hash}')
    if versions:
        version = versions[0]
        _assert_existing_version(
            session,
            version,
            artifacts,
            source_version=source_version,
            source_locator=source_locator,
        )
        return PersistedDocumentVersion(document.id, version.id, content_hash, False)

    version_id = str(uuid5(NAMESPACE_URL, f'{document.id}:{content_hash}'))
    acquired_at = min(_fetched_at(artifact.response) for artifact in artifacts)
    version = SourceDocumentVersion(
        id=version_id,
        document_id=document.id,
        content_hash=content_hash,
        source_version=source_version,
        source_locator=source_locator,
        acquired_at=acquired_at,
    )
    session.add(version)
    session.add_all(
        [
            SourceDocumentArtifact(
                id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f'{version_id}:{artifact.artifact_role}:{artifact.ordinal}',
                    )
                ),
                document_version_id=version_id,
                artifact_role=artifact.artifact_role,
                ordinal=artifact.ordinal,
                locator=artifact.locator,
                source_url=artifact.response.url,
                status_code=artifact.response.status_code,
                media_type=artifact.response.content_type,
                response_headers=_response_headers(artifact.response),
                content_hash=artifact.response.content_sha256,
                body=artifact.response.body,
                fetched_at=artifact.response.fetched_at,
            )
            for artifact in artifacts
        ]
    )
    session.commit()
    return PersistedDocumentVersion(document.id, version_id, content_hash, True)


def reconstruct_artifact(
    session: Session,
    *,
    version_id: str,
    artifact_role: str,
    ordinal: int,
) -> bytes:
    artifacts = session.scalars(
        select(SourceDocumentArtifact).where(
            SourceDocumentArtifact.document_version_id == version_id,
            SourceDocumentArtifact.artifact_role == artifact_role,
            SourceDocumentArtifact.ordinal == ordinal,
        )
    ).all()
    if len(artifacts) != 1:
        raise DocumentVersionError(
            f'Artefacto no encontrado o ambiguo: {version_id}/{artifact_role}/{ordinal}'
        )
    artifact = artifacts[0]
    if hashlib.sha256(artifact.body).hexdigest() != artifact.content_hash:
        raise DocumentVersionConflictError(
            f'Hash de artefacto persistido incompatible: {artifact.id}'
        )
    return artifact.body
