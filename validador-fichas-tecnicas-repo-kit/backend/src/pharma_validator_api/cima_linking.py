"""Vinculación exacta y reproducible entre presentaciones del maestro y CIMA."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.models import (
    BlockInstance,
    DocumentRecordLink,
    FieldValue,
    SourceDocument,
    SourceDocumentArtifact,
    SourceDocumentVersion,
)


class CimaLinkingError(RuntimeError):
    pass


@dataclass(frozen=True)
class CimaLinkingResult:
    exact_candidates: int
    created_links: int
    existing_links: int
    ambiguous_cn: tuple[str, ...]
    cima_only_cn: int
    master_only_cn: int


def _master_by_cn(session: Session) -> dict[str, set[str]]:
    rows = session.execute(
        select(FieldValue.literal_value, BlockInstance.target_record_id)
        .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
        .where(
            FieldValue.field_name == "CODIGO_NACIONAL",
            FieldValue.literal_value.is_not(None),
            FieldValue.literal_value != "",
        )
    )
    result: dict[str, set[str]] = defaultdict(set)
    for cn, record_id in rows:
        result[str(cn)].add(record_id)
    return result


def _latest_cima_versions(session: Session) -> dict[str, SourceDocumentVersion]:
    documents = session.scalars(
        select(SourceDocument).where(SourceDocument.source_type == "cima_document_type_1")
    ).all()
    result: dict[str, SourceDocumentVersion] = {}
    for document in documents:
        version = session.scalars(
            select(SourceDocumentVersion)
            .where(SourceDocumentVersion.document_id == document.id)
            .order_by(SourceDocumentVersion.acquired_at.desc(), SourceDocumentVersion.id.desc())
            .limit(1)
        ).first()
        if version is not None:
            result[document.name] = version
    return result


def _cima_by_cn(
    session: Session, versions: dict[str, SourceDocumentVersion]
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for nregistro, version in versions.items():
        artifact = session.scalars(
            select(SourceDocumentArtifact).where(
                SourceDocumentArtifact.document_version_id == version.id,
                SourceDocumentArtifact.artifact_role == "metadata",
            )
        ).first()
        if artifact is None:
            raise CimaLinkingError(f"{nregistro}: versión CIMA sin metadatos.")
        try:
            payload = json.loads(artifact.body)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CimaLinkingError(f"{nregistro}: metadatos CIMA inválidos.") from error
        presentations = payload.get("presentaciones") if isinstance(payload, dict) else None
        if not isinstance(presentations, list):
            raise CimaLinkingError(f"{nregistro}: presentaciones CIMA inválidas.")
        for item in presentations:
            cn = item.get("cn") if isinstance(item, dict) else None
            if isinstance(cn, str) and cn:
                result[cn].add(nregistro)
    return result


def link_cima_to_master(session: Session, *, commit: bool = True) -> CimaLinkingResult:
    """Crea sólo enlaces respaldados por una igualdad CN exacta y no ambigua."""
    master = _master_by_cn(session)
    versions = _latest_cima_versions(session)
    cima = _cima_by_cn(session, versions)
    common = set(master) & set(cima)
    exact = sorted(cn for cn in common if len(master[cn]) == 1 and len(cima[cn]) == 1)
    ambiguous = tuple(sorted(common - set(exact)))
    created = existing = 0
    try:
        for cn in exact:
            record_id = next(iter(master[cn]))
            nregistro = next(iter(cima[cn]))
            version = versions[nregistro]
            identity = f"cima-exact-cn-v1:{version.id}:{record_id}:{cn}"
            link_id = str(uuid5(NAMESPACE_URL, identity))
            if session.get(DocumentRecordLink, link_id) is not None:
                existing += 1
                continue
            session.add(
                DocumentRecordLink(
                    id=link_id,
                    document_version_id=version.id,
                    target_record_id=record_id,
                    link_type="exact_national_code_v1",
                )
            )
            created += 1
        if commit:
            session.commit()
        else:
            session.flush()
    except Exception:
        session.rollback()
        raise
    return CimaLinkingResult(
        len(exact),
        created,
        existing,
        ambiguous,
        len(set(cima) - set(master)),
        len(set(master) - set(cima)),
    )
