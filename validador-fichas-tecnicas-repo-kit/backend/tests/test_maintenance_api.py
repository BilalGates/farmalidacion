from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import MaintenanceChangeEvent, MaintenanceRun


def client_with_event(scratch_db_url: str) -> tuple[TestClient, str]:
    event_id = "a" * 64
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        session.add(
            MaintenanceChangeEvent(
                id=event_id,
                nregistro="51347",
                occurred_at_epoch=123,
                change_type=3,
                areas_json='["ft"]',
                source_sha256="b" * 64,
                fetched_at="2026-09-09T10:00:00+00:00",
                old_version_id=None,
                new_version_id=None,
                diff_json='{"changes":[]}',
                affected_field_count=2,
                recorded_at=datetime.now(UTC),
            )
        )
        session.commit()
    return TestClient(create_app(Settings(database_url=scratch_db_url, env="test"))), event_id


def test_list_and_detail_expose_summary_then_diff(scratch_db_url: str) -> None:
    client, event_id = client_with_event(scratch_db_url)
    listed = client.get("/maintenance/changes")
    detail = client.get(f"/maintenance/changes/{event_id}")

    assert listed.status_code == 200
    assert listed.json()[0]["has_diff"] is True
    assert "diff" not in listed.json()[0]
    assert detail.status_code == 200
    assert detail.json()["diff"] == {"changes": []}


def test_limits_and_missing_event_fail_in_spanish(scratch_db_url: str) -> None:
    client, _ = client_with_event(scratch_db_url)

    assert client.get("/maintenance/changes?limit=0").status_code == 400
    missing = client.get(f"/maintenance/changes/{'f' * 64}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Novedad CIMA no encontrada."


def test_runs_expose_operational_failure(scratch_db_url: str) -> None:
    client, _ = client_with_event(scratch_db_url)
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        session.add(
            MaintenanceRun(
                requested_date="08/09/2026",
                attempt=1,
                status="failed",
                event_count=0,
                source_sha256=None,
                error_detail="CimaTransportError: timeout",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
        )
        session.commit()

    response = client.get("/maintenance/runs")
    assert response.status_code == 200
    assert response.json()[0]["status"] == "failed"
    assert "timeout" in response.json()[0]["error_detail"]
