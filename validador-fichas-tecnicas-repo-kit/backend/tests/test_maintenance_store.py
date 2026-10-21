import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_changes import CimaChange, CimaChangeReport
from pharma_validator_api.cima_client import CimaResponse
from pharma_validator_api.maintenance_refresh import MaintenanceRefreshError
from pharma_validator_api.maintenance_store import list_changes, process_change_report
from pharma_validator_api.models import Base, ImmutableHistoryError, MaintenanceChangeEvent


class UnusedClient:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"No debía consultarse CIMA: {name}")


class SectionsUnavailableClient:
    def __init__(self, *, error: str = "No existen secciones para el medicamento indicado") -> None:
        self.error = error
        self.section_calls = 0

    def _response(self, body: bytes) -> CimaResponse:
        return CimaResponse(
            url="https://cima.aemps.es/cima/rest/docSegmentado/secciones/1",
            status_code=200,
            headers=(("Content-Type", "application/json"),),
            body=body,
            content_sha256=hashlib.sha256(body).hexdigest(),
            fetched_at="2026-10-21T08:00:00+00:00",
            from_cache=False,
        )

    def medication(self, **_: object) -> CimaResponse:
        return self._response(b'{"nregistro":"07398006"}')

    def sections(self, **_: object) -> CimaResponse:
        self.section_calls += 1
        return self._response(json.dumps({"error": self.error}).encode())

    def content(self, **_: object) -> CimaResponse:
        raise AssertionError("No debe solicitarse contenido si CIMA no ofrece secciones")


def session_for(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'events.db').as_posix()}")
    Base.metadata.create_all(engine)
    return Session(engine)


def report(*changes: CimaChange) -> CimaChangeReport:
    digest = hashlib.sha256(repr(changes).encode()).hexdigest()
    return CimaChangeReport(
        requested_date="09/09/2026",
        changes=changes,
        unknown_areas=(),
        source_sha256=digest,
        fetched_at="2026-09-09T10:00:00+00:00",
    )


def test_non_ft_changes_are_persisted_idempotently_without_refresh(tmp_path: Path) -> None:
    session = session_for(tmp_path)
    change_report = report(CimaChange("51347", 10, 3, ("estado", "comerc")))
    with session:
        first = process_change_report(
            session, client=UnusedClient(), report=change_report  # type: ignore[arg-type]
        )
        second = process_change_report(
            session, client=UnusedClient(), report=change_report  # type: ignore[arg-type]
        )

        assert len(first) == 1
        assert second == ()
        assert first[0].diff_json is None
        assert session.scalar(select(func.count()).select_from(MaintenanceChangeEvent)) == 1


def test_unavailable_ft_sections_keep_notice_and_continue_batch(tmp_path: Path) -> None:
    session = session_for(tmp_path)
    client = SectionsUnavailableClient()
    changes = report(
        CimaChange("07398006", 10, 3, ("ft",)),
        CimaChange("07398006", 11, 3, ("ft", "otros")),
        CimaChange("other", 12, 3, ("otros",)),
    )
    with session:
        events = process_change_report(session, client=client, report=changes)  # type: ignore[arg-type]
        assert len(events) == 3
        assert client.section_calls == 1
        assert all(event.new_version_id is None for event in events)
        assert session.scalar(select(func.count()).select_from(MaintenanceChangeEvent)) == 3
        assert process_change_report(session, client=client, report=changes) == ()  # type: ignore[arg-type]


def test_unexpected_sections_error_fails_with_registration(tmp_path: Path) -> None:
    session = session_for(tmp_path)
    client = SectionsUnavailableClient(error="Error interno")
    with session, pytest.raises(MaintenanceRefreshError, match="nregistro 07398006"):
        process_change_report(
            session, client=client, report=report(CimaChange("07398006", 10, 3, ("ft",)))  # type: ignore[arg-type]
        )


def test_cumulative_responses_do_not_duplicate_the_same_notice(tmp_path: Path) -> None:
    session = session_for(tmp_path)
    notice = CimaChange("51347", 10, 3, ("estado", "comerc"))
    first_report = report(notice)
    later_report = CimaChangeReport(
        requested_date="10/09/2026", changes=(notice,), unknown_areas=(),
        source_sha256="f" * 64, fetched_at="2026-09-10T10:00:00+00:00",
    )
    with session:
        first = process_change_report(
            session, client=UnusedClient(), report=first_report  # type: ignore[arg-type]
        )
        second = process_change_report(
            session, client=UnusedClient(), report=later_report  # type: ignore[arg-type]
        )
        assert len(first) == 1
        assert second == ()
        stored = session.get(MaintenanceChangeEvent, first[0].id)
        assert stored is not None and stored.source_sha256 == first_report.source_sha256
        assert session.scalar(select(func.count()).select_from(MaintenanceChangeEvent)) == 1


def test_notice_from_previous_id_scheme_is_recognized(tmp_path: Path) -> None:
    session = session_for(tmp_path)
    notice = CimaChange("51347", 10, 3, ("estado",))
    with session:
        session.add(MaintenanceChangeEvent(
            id="0" * 64, nregistro=notice.nregistro,
            occurred_at_epoch=notice.occurred_at, change_type=notice.change_type,
            areas_json='["estado"]', source_sha256="a" * 64,
            fetched_at="2026-09-09T10:00:00+00:00", old_version_id=None,
            new_version_id=None, diff_json=None, affected_field_count=0,
            recorded_at=datetime.now(UTC),
        ))
        session.commit()
        assert process_change_report(
            session, client=UnusedClient(), report=report(notice)  # type: ignore[arg-type]
        ) == ()
        assert session.scalar(select(func.count()).select_from(MaintenanceChangeEvent)) == 1


def test_events_are_ordered_and_immutable(tmp_path: Path) -> None:
    session = session_for(tmp_path)
    with session:
        process_change_report(
            session,
            client=UnusedClient(),  # type: ignore[arg-type]
            report=report(
                CimaChange("older", 1, 1, ("estado",)),
                CimaChange("newer", 2, 2, ("comerc",)),
            ),
        )
        rows = list_changes(session)
        assert [row.nregistro for row in rows] == ["newer", "older"]
        rows[0].affected_field_count = 9
        with pytest.raises(ImmutableHistoryError, match="inmutables"):
            session.commit()
