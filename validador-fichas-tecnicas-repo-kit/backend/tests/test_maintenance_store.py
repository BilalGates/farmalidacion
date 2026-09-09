import hashlib
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.cima_changes import CimaChange, CimaChangeReport
from pharma_validator_api.maintenance_store import list_changes, process_change_report
from pharma_validator_api.models import Base, ImmutableHistoryError, MaintenanceChangeEvent


class UnusedClient:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"No debía consultarse CIMA: {name}")


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

        assert first[0].id == second[0].id
        assert first[0].diff_json is None
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
