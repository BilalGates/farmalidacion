from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_validator_api.models import (
    DocumentRecordLink,
    SourceDocument,
    SourceDocumentArtifact,
    SourceDocumentVersion,
)


class ContextualChatError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatCitation:
    document_version_id: str
    section: str
    literal_text: str


@dataclass(frozen=True)
class ChatResult:
    status: str
    message: str
    citations: tuple[ChatCitation, ...]


STOPWORDS = frozenset(
    {
        "algo", "apartado", "como", "cual", "dame", "dice", "documento", "el", "en",
        "la", "las", "lo", "los", "menciona", "me", "muestra", "que", "sobre", "un",
        "una",
    }
)
SECTION_PATTERN = re.compile(r"(?:apartado|secci[oó]n)\s+([0-9]+(?:\.[0-9]+)*)", re.I)


def _text(artifact: SourceDocumentArtifact) -> str | None:
    media_type = (artifact.media_type or "").lower()
    if not (media_type.startswith("text/") or "json" in media_type):
        return None
    try:
        return artifact.body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def _latest_artifacts(session: Session, record_id: str) -> tuple[SourceDocumentArtifact, ...]:
    versions = session.scalars(
        select(SourceDocumentVersion)
        .join(
            DocumentRecordLink,
            DocumentRecordLink.document_version_id == SourceDocumentVersion.id,
        )
        .join(SourceDocument, SourceDocument.id == SourceDocumentVersion.document_id)
        .where(DocumentRecordLink.target_record_id == record_id)
        .where(SourceDocument.source_type == "cima_document_type_1")
        .order_by(
            SourceDocumentVersion.document_id,
            SourceDocumentVersion.acquired_at.desc(),
            SourceDocumentVersion.id.desc(),
        )
    ).all()
    latest: dict[str, SourceDocumentVersion] = {}
    for version in versions:
        latest.setdefault(version.document_id, version)
    if not latest:
        return ()
    return tuple(
        session.scalars(
            select(SourceDocumentArtifact)
            .where(
                SourceDocumentArtifact.document_version_id.in_(
                    [row.id for row in latest.values()]
                )
            )
            .where(SourceDocumentArtifact.artifact_role == "section")
            .order_by(SourceDocumentArtifact.locator, SourceDocumentArtifact.ordinal)
        ).all()
    )


def _excerpt(text: str, terms: tuple[str, ...], *, maximum: int = 500) -> str:
    folded = text.casefold()
    positions = [folded.find(term) for term in terms if folded.find(term) >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - maximum // 3)
    end = min(len(text), start + maximum)
    return text[start:end]


def answer_from_document(session: Session, *, record_id: str, question: str) -> ChatResult:
    cleaned = question.strip()
    if not cleaned:
        raise ContextualChatError("La consulta no puede estar vacía.")
    artifacts = _latest_artifacts(session, record_id)
    if not artifacts:
        return ChatResult(
            "not_available",
            "No hay una ficha técnica CIMA vinculada a este registro.",
            (),
        )

    section_match = SECTION_PATTERN.search(cleaned)
    requested_section = section_match.group(1) if section_match else None
    terms = tuple(
        dict.fromkeys(
            token
            for token in re.findall(r"[\wáéíóúüñ]+", cleaned.casefold())
            if len(token) >= 3 and token not in STOPWORDS
        )
    )
    ranked: list[tuple[int, SourceDocumentArtifact, str]] = []
    for artifact in artifacts:
        text = _text(artifact)
        if text is None:
            continue
        if requested_section is not None:
            if artifact.locator == requested_section:
                ranked.append((10_000, artifact, text))
            continue
        score = sum(text.casefold().count(term) for term in terms)
        if score:
            ranked.append((score, artifact, text))
    ranked.sort(key=lambda item: (-item[0], item[1].locator, item[1].ordinal))
    citations = tuple(
        ChatCitation(
            document_version_id=artifact.document_version_id,
            section=artifact.locator,
            literal_text=text if requested_section else _excerpt(text, terms),
        )
        for _, artifact, text in ranked[:5]
    )
    if not citations:
        return ChatResult(
            "not_found",
            "No se encontró evidencia literal para esa consulta en la ficha vinculada.",
            (),
        )
    return ChatResult(
        "answered",
        f"Se encontraron {len(citations)} fragmentos literales. "
        "Revise las citas; no son una recomendación clínica.",
        citations,
    )
