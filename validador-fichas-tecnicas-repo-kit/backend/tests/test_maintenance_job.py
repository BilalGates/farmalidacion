import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import pharma_validator_api.maintenance_job as maintenance_job
from pharma_validator_api.cima_client import CimaResponse
from pharma_validator_api.maintenance_job import (
    MaintenanceJobError,
    next_pending_date,
    run_one_day,
    run_pending_days,
)
from pharma_validator_api.models import Base, MaintenanceRun


class ChangesClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.dates: list[str] = []

    def all_presentations(self) -> tuple[dict, ...]:
        return ()

    def changes(self, *, date: str, nregistros: tuple[str, ...] = ()) -> CimaResponse:
        self.dates.append(date)
        if self.fail:
            raise RuntimeError("CIMA no disponible")
        body = json.dumps(
            [{"nregistro": date, "fecha": 1, "tipoCambio": 3, "cambios": ["estado"]}]
        ).encode()
        return CimaResponse(
            url="https://cima.example.test/rest/registroCambios",
            status_code=200,
            headers=(("Content-Type", "application/json"),),
            body=body,
            content_sha256=hashlib.sha256(body).hexdigest(),
            fetched_at="2026-09-09T08:00:00+00:00",
            from_cache=False,
        )


class NoPresentationsClient(ChangesClient):
    def all_presentations(self) -> tuple[dict, ...]:
        return ()


class UnrelatedChangeClient(ChangesClient):
    def all_presentations(self) -> tuple[dict, ...]:
        return ({"cn": "700000", "nregistro": "07/09/2026"},)

    def medication(self, *, nregistro: str, use_cache: bool = False) -> CimaResponse:
        raise AssertionError("An unrelated change must not request medication metadata")


def session_for(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'job.db').as_posix()}")
    Base.metadata.create_all(engine)
    return Session(engine)


def fixed_now() -> datetime:
    return datetime(2026, 9, 9, 8, tzinfo=UTC)


def test_pending_days_resume_after_last_completed_date(tmp_path: Path) -> None:
    session = session_for(tmp_path)
    client = ChangesClient()
    with session:
        runs = run_pending_days(
            session,
            client=client,  # type: ignore[arg-type]
            start_date=date(2026, 9, 7),
            through_date=date(2026, 9, 8),
        )
        assert [run.requested_date for run in runs] == ["07/09/2026", "08/09/2026"]
        assert client.dates == ["07/09/2026"]
        assert next_pending_date(session, start_date=date(2026, 9, 7)) == date(2026, 9, 9)
        assert run_pending_days(
            session,
            client=client,  # type: ignore[arg-type]
            start_date=date(2026, 9, 7),
            through_date=date(2026, 9, 8),
        ) == ()


def test_medication_without_presentations_does_not_block_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        maintenance_job, "_master_cn_index", lambda _session: {"600000": ("record-1",)}
    )
    session = session_for(tmp_path)
    with session:
        run = run_one_day(
            session,
            client=NoPresentationsClient(),  # type: ignore[arg-type]
            day=date(2026, 9, 30),
            now=fixed_now,
        )
        assert run.status == "completed"
        assert run.event_count == 0


def test_bulk_index_requires_unique_literal_cn_on_both_sides() -> None:
    class CatalogClient(ChangesClient):
        def all_presentations(self) -> tuple[dict, ...]:
            return (
                {"cn": "060000", "nregistro": "one"},
                {"cn": "600000", "nregistro": "two"},
                {"cn": "600000", "nregistro": "three"},
                {"cn": "700000", "nregistro": "one"},
                {"cn": "800000", "nregistro": "one"},
            )

    matches = maintenance_job._catalog_targets_by_registration(
        CatalogClient(),
        {
            "060000": ("target-a",),
            "600000": ("target-b",),
            "700000": ("target-c", "target-d"),
            "800000": ("target-e",),
        },
    )
    assert matches == {"one": (("target-a", "060000"), ("target-e", "800000"))}


def test_bulk_index_skips_changes_without_matching_catalog_cn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        maintenance_job, "_master_cn_index", lambda _session: {"600000": ("record-1",)}
    )
    session = session_for(tmp_path)
    with session:
        run = run_one_day(
            session,
            client=UnrelatedChangeClient(),  # type: ignore[arg-type]
            day=date(2026, 9, 7),
        )
        assert run.status == "completed"
        assert run.event_count == 0


def test_failure_is_visible_and_next_attempt_retries_same_day(tmp_path: Path) -> None:
    session = session_for(tmp_path)
    with session:
        with pytest.raises(MaintenanceJobError, match="intento 1"):
            run_one_day(
                session,
                client=ChangesClient(fail=True),  # type: ignore[arg-type]
                day=date(2026, 9, 8),
                now=fixed_now,
            )
        failed = session.scalar(select(MaintenanceRun))
        assert failed is not None
        assert failed.status == "failed"
        assert "CIMA no disponible" in (failed.error_detail or "")

        recovered = run_one_day(
            session,
            client=ChangesClient(),  # type: ignore[arg-type]
            day=date(2026, 9, 8),
            now=fixed_now,
        )
        assert recovered.attempt == 2
        assert recovered.status == "completed"


def test_pending_days_fill_gap_before_later_completed_day(tmp_path: Path) -> None:
    session = session_for(tmp_path)
    with session:
        run_one_day(
            session,
            client=ChangesClient(),  # type: ignore[arg-type]
            day=date(2026, 9, 9),
            now=fixed_now,
        )
        assert next_pending_date(session, start_date=date(2026, 9, 7)) == date(2026, 9, 7)
        runs = run_pending_days(
            session,
            client=ChangesClient(),  # type: ignore[arg-type]
            start_date=date(2026, 9, 7),
            through_date=date(2026, 9, 9),
        )
        assert [run.requested_date for run in runs] == ["07/09/2026", "08/09/2026"]
