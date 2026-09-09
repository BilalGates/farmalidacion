import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.contextual_chat import answer_from_document
from pharma_validator_api.models import (
    Base,
    DocumentRecordLink,
    SourceDocument,
    SourceDocumentArtifact,
    SourceDocumentVersion,
    TargetRecord,
    ValidationDecisionRecord,
)


def artifact(
    version_id: str, section: str, text: str, *, ordinal: int = 1
) -> SourceDocumentArtifact:
    body = text.encode()
    return SourceDocumentArtifact(
        id=f"artifact-{version_id}-{section}",
        document_version_id=version_id,
        artifact_role="section",
        ordinal=ordinal,
        locator=section,
        source_url=f"https://cima.example.test/{version_id}/{section}",
        status_code=200,
        media_type="text/plain; charset=utf-8",
        response_headers="[]",
        content_hash=hashlib.sha256(body).hexdigest(),
        body=body,
        fetched_at="2026-09-09T08:00:00+00:00",
    )


def seeded_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'chat.db').as_posix()}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    document = SourceDocument(id="document", source_type="cima_document_type_1", name="51347")
    old = SourceDocumentVersion(
        id="old",
        document_id=document.id,
        content_hash="1" * 64,
        source_version=None,
        source_locator="old",
        acquired_at=datetime.now(UTC) - timedelta(days=1),
    )
    new = SourceDocumentVersion(
        id="new",
        document_id=document.id,
        content_hash="2" * 64,
        source_version=None,
        source_locator="new",
        acquired_at=datetime.now(UTC),
    )
    record = TargetRecord(id="record", entity_type="medication")
    session.add_all(
        [
            document,
            old,
            new,
            record,
            artifact("old", "4.2", "Texto antiguo sobre insuficiencia renal."),
            artifact("new", "4.2", "Texto vigente sobre insuficiencia renal."),
            artifact("new", "6.3", "Periodo de validez completo y literal.", ordinal=2),
            DocumentRecordLink(
                id="link-old",
                document_version_id="old",
                target_record_id="record",
                link_type="ft",
            ),
            DocumentRecordLink(
                id="link-new",
                document_version_id="new",
                target_record_id="record",
                link_type="ft",
            ),
        ]
    )
    session.commit()
    return session


def test_search_uses_only_latest_version_and_returns_literal_citation(tmp_path: Path) -> None:
    session = seeded_session(tmp_path)
    with session:
        result = answer_from_document(
            session, record_id="record", question="¿Menciona insuficiencia renal?"
        )
        assert result.status == "answered"
        assert result.citations[0].document_version_id == "new"
        assert "Texto vigente" in result.citations[0].literal_text
        assert "Texto antiguo" not in result.citations[0].literal_text


def test_section_request_returns_complete_literal_section(tmp_path: Path) -> None:
    session = seeded_session(tmp_path)
    with session:
        result = answer_from_document(
            session, record_id="record", question="Enséñame el apartado 6.3 completo"
        )
        assert result.citations[0].section == "6.3"
        assert result.citations[0].literal_text == "Periodo de validez completo y literal."


def test_no_evidence_is_not_presented_as_an_answer_and_writes_nothing(tmp_path: Path) -> None:
    session = seeded_session(tmp_path)
    with session:
        before = session.scalar(select(func.count()).select_from(ValidationDecisionRecord))
        result = answer_from_document(session, record_id="record", question="xilófono")
        after = session.scalar(select(func.count()).select_from(ValidationDecisionRecord))
        assert result.status == "not_found"
        assert result.citations == ()
        assert before == after == 0


def test_segmented_full_document_exposes_each_literal_section(tmp_path: Path) -> None:
    session = seeded_session(tmp_path)
    with session:
        body = json.dumps(
            [{"seccion": "4.2", "contenido": "Dosis literal del documento CIMA."}]
        ).encode()
        session.add(
            SourceDocumentVersion(
                id="newest",
                document_id="document",
                content_hash="3" * 64,
                source_version=None,
                source_locator="newest",
                acquired_at=datetime.now(UTC) + timedelta(seconds=1),
            )
        )
        session.flush()
        session.add_all(
            [
                SourceDocumentArtifact(
                    id="full-new",
                    document_version_id="newest",
                    artifact_role="full_document",
                    ordinal=1,
                    locator="all-sections",
                    source_url="https://cima.example.test/new",
                    status_code=200,
                    media_type="application/json",
                    response_headers="[]",
                    content_hash=hashlib.sha256(body).hexdigest(),
                    body=body,
                    fetched_at="2026-09-09T08:00:00+00:00",
                ),
                DocumentRecordLink(
                    id="link-newest",
                    document_version_id="newest",
                    target_record_id="record",
                    link_type="ft",
                ),
            ]
        )
        session.commit()
        result = answer_from_document(
            session, record_id="record", question="Enséñame el apartado 4.2"
        )
        assert result.status == "answered"
        assert result.citations[0].section == "4.2"
        assert result.citations[0].literal_text == "Dosis literal del documento CIMA."
