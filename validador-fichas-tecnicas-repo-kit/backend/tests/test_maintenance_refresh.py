import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_changes import CimaChange
from pharma_validator_api.cima_client import CimaResponse
from pharma_validator_api.document_versions import ArtifactInput, persist_cima_document_version
from pharma_validator_api.maintenance_refresh import (
    refresh_changed_technical_sheets,
    refresh_technical_sheet,
)
from pharma_validator_api.models import (
    Base,
    BlockInstance,
    DocumentRecordLink,
    FieldValue,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
    ValidationDecisionRecord,
    ValueProvenance,
)


def response(
    body: bytes,
    *,
    path: str,
    fetched_at: str = "2026-09-08T08:00:00+00:00",
) -> CimaResponse:
    return CimaResponse(
        url=f"https://cima.example.test/rest/{path}",
        status_code=200,
        headers=(("Content-Type", "application/json"),),
        body=body,
        content_sha256=hashlib.sha256(body).hexdigest(),
        fetched_at=fetched_at,
        from_cache=False,
    )


def old_artifacts() -> tuple[ArtifactInput, ...]:
    return (
        ArtifactInput("metadata", 1, "medicamento", response(b'{"estado":"A"}', path="m")),
        ArtifactInput(
            "section_index",
            1,
            "secciones",
            response(b'[{"seccion":"1"},{"seccion":"2"}]', path="s"),
        ),
        ArtifactInput("section", 1, "1", response(b'{"contenido":"antes"}', path="c1")),
        ArtifactInput("section", 2, "2", response(b'{"contenido":"igual"}', path="c2")),
    )


@dataclass
class StubClient:
    changed: bool
    calls: list[tuple[str, bool]]

    def medication(
        self,
        *,
        nregistro: str | None = None,
        cn: str | None = None,
        use_cache: bool = True,
    ) -> CimaResponse:
        self.calls.append(("metadata", use_cache))
        return response(
            b'{"estado":"A"}', path="m", fetched_at="2026-09-09T08:00:00+00:00"
        )

    def sections(
        self, *, nregistro: str, document_type: int = 1, use_cache: bool = True
    ) -> CimaResponse:
        self.calls.append(("index", use_cache))
        return response(
            b'[{"seccion":"1"},{"seccion":"2"}]',
            path="s",
            fetched_at="2026-09-09T08:00:00+00:00",
        )

    def content(
        self,
        *,
        nregistro: str,
        section: str | None = None,
        document_type: int = 1,
        accept: str = "application/json",
        use_cache: bool = True,
    ) -> CimaResponse:
        assert section is not None
        self.calls.append((section, use_cache))
        body = b'{"contenido":"despues"}' if self.changed and section == "1" else (
            b'{"contenido":"antes"}' if section == "1" else b'{"contenido":"igual"}'
        )
        return response(body, path=f"c{section}", fetched_at="2026-09-09T08:00:00+00:00")


def seeded_session(tmp_path: Path) -> tuple[Session, str, str, str]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'maintenance.db').as_posix()}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    old = persist_cima_document_version(
        session, nregistro="51347", document_type=1, artifacts=old_artifacts()
    )
    session.add_all(
        [
            BlockInstance(id="block", target_record_id="record", block_type="general", ordinal=1),
        ]
    )
    session.add(TargetRecord(id="record", entity_type="medication"))
    session.flush()
    section_one = SourceFragment(
        id="fragment-1",
        document_version_id=old.version_id,
        locator_type="cima_section",
        locator="1",
        literal_text="antes",
    )
    section_two = SourceFragment(
        id="fragment-2",
        document_version_id=old.version_id,
        locator_type="cima_section",
        locator="2",
        literal_text="igual",
    )
    first = FieldValue(
        id="field-1",
        block_instance_id="block",
        field_name="CAMPO_1",
        literal_value="antes",
        observed_type="texto",
        logical_state="valued",
    )
    second = FieldValue(
        id="field-2",
        block_instance_id="block",
        field_name="CAMPO_2",
        literal_value="igual",
        observed_type="texto",
        logical_state="valued",
    )
    session.add_all(
        [
            section_one,
            section_two,
            first,
            second,
            ValueProvenance(
                id="provenance-1",
                field_value_id=first.id,
                source_fragment_id=section_one.id,
                provenance_role="technical_sheet",
            ),
            ValueProvenance(
                id="provenance-2",
                field_value_id=second.id,
                source_fragment_id=section_two.id,
                provenance_role="technical_sheet",
            ),
            DocumentRecordLink(
                id="link-old",
                document_version_id=old.version_id,
                target_record_id="record",
                link_type="technical_sheet",
            ),
        ]
    )
    for field_id, name in (("field-1", "CAMPO_1"), ("field-2", "CAMPO_2")):
        session.add(
            ValidationDecisionRecord(
                field_value_id=field_id,
                sequence=1,
                field_name=name,
                state="confirmado",
                final_value="valor",
                comment=None,
                reviewer_id="farmaceutica-1",
                reviewer_role="farmaceutico",
                reviewer_assurance="declared",
                seconds_spent=4,
                decided_at=datetime.now(UTC),
            )
        )
    session.commit()
    return session, old.version_id, first.id, second.id


def test_changed_section_marks_only_affected_field(tmp_path: Path) -> None:
    session, old_id, first_id, second_id = seeded_session(tmp_path)
    client = StubClient(True, [])
    with session:
        result = refresh_technical_sheet(session, client=client, nregistro="51347")

        assert result.created is True
        assert result.old_version_id == old_id
        assert result.changed_sections == ("1",)
        assert result.marked_field_value_ids == (first_id,)
        assert result.diff is not None
        assert all(use_cache is False for _, use_cache in client.calls)
        assert session.scalar(select(func.count()).select_from(SourceDocumentVersion)) == 2
        assert session.scalar(select(func.count()).select_from(DocumentRecordLink)) == 2
        first_states = session.scalars(
            select(ValidationDecisionRecord.state)
            .where(ValidationDecisionRecord.field_value_id == first_id)
            .order_by(ValidationDecisionRecord.sequence)
        ).all()
        second_states = session.scalars(
            select(ValidationDecisionRecord.state)
            .where(ValidationDecisionRecord.field_value_id == second_id)
        ).all()
        assert first_states == ["confirmado", "revision_pendiente"]
        assert second_states == ["confirmado"]


def test_identical_refresh_creates_nothing_and_keeps_decisions(tmp_path: Path) -> None:
    session, old_id, _, _ = seeded_session(tmp_path)
    with session:
        result = refresh_technical_sheet(
            session, client=StubClient(False, []), nregistro="51347"
        )

        assert result.created is False
        assert result.new_version_id == old_id
        assert result.marked_field_value_ids == ()
        assert session.scalar(select(func.count()).select_from(SourceDocumentVersion)) == 1
        assert session.scalar(select(func.count()).select_from(ValidationDecisionRecord)) == 2


def test_change_batch_ignores_non_ft_and_deduplicates_nregistro(tmp_path: Path) -> None:
    session, _, _, _ = seeded_session(tmp_path)
    client = StubClient(True, [])
    changes = (
        CimaChange("51347", 1, 3, ("estado",)),
        CimaChange("51347", 2, 3, ("ft",)),
        CimaChange("51347", 3, 3, ("ft", "otros")),
    )
    with session:
        results = refresh_changed_technical_sheets(
            session, client=client, changes=changes
        )

    assert len(results) == 1
    assert results[0].nregistro == "51347"
    assert [name for name, _ in client.calls].count("metadata") == 1
