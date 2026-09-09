"""API de la cola: la capa HTTP no puede saltarse las barreras del dominio."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import (
    Base,
    BlockInstance,
    FieldValue,
    ReviewQueueEntry,
    TargetRecord,
)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        for index in range(2):
            session.add(TargetRecord(id=f"rec-{index}", entity_type="medicamento"))
        session.commit()
        session.add(
            BlockInstance(id="block", target_record_id="rec-0", block_type="general", ordinal=1)
        )
        session.flush()
        session.add(
            FieldValue(
                id="value",
                block_instance_id="block",
                field_name="NAME",
                literal_value="Original",
                observed_type="str",
                logical_state="valued",
            )
        )
        session.commit()
    engine.dispose()
    return TestClient(create_app(Settings(database_url=url, reviewers=("ana:Ana Ruiz",))))


def test_assignment_guards_decision_writes(client: TestClient) -> None:
    client.post("/queue", json={"target_record_id": "rec-0"})
    client.post("/queue/rec-0/assign", json={"reviewer_id": "ana"})
    payload = {
        "state": "confirmado",
        "reviewer_id": "other",
        "reviewer_role": "farmaceutico",
        "final_value": "Original",
    }
    assert client.post("/records/values/value/decisions", json=payload).status_code == 409
    payload["reviewer_id"] = "ana"
    assert client.post("/records/values/value/decisions", json=payload).status_code == 201


def test_disabled_queue_does_not_block_existing_records(client: TestClient) -> None:
    client.post("/queue", json={"target_record_id": "rec-0"})
    client.app.state.settings.enable_review_queue = False
    result = client.post(
        "/records/values/value/decisions",
        json={
            "state": "confirmado",
            "reviewer_id": "ana",
            "final_value": "Original",
            "reviewer_role": "farmaceutico",
        },
    )
    assert result.status_code == 201


def test_expired_assignment_rejects_writes(client: TestClient) -> None:
    client.post("/queue", json={"target_record_id": "rec-0"})
    client.post("/queue/rec-0/assign", json={"reviewer_id": "ana"})
    engine = create_engine(client.app.state.settings.database_url)
    with engine.begin() as connection:
        connection.execute(
            update(ReviewQueueEntry).values(assigned_at=datetime.now(UTC) - timedelta(hours=1))
        )
    engine.dispose()
    result = client.post(
        "/records/values/value/decisions",
        json={
            "state": "confirmado",
            "reviewer_id": "ana",
            "final_value": "Original",
            "reviewer_role": "farmaceutico",
        },
    )
    assert result.status_code == 409


def test_cannot_enqueue_missing_record(client: TestClient) -> None:
    assert client.post("/queue", json={"target_record_id": "missing"}).status_code == 404


def test_enqueue_and_read_back(client: TestClient) -> None:
    created = client.post("/queue", json={"target_record_id": "rec-0", "priority": 3})
    assert created.status_code == 201
    assert created.json()["state"] == "pendiente"
    assert client.get("/queue/rec-0").json()["priority"] == 3


def test_queue_filters_explicit_facets_without_guessing_membership(client: TestClient) -> None:
    first = client.post(
        "/queue",
        json={
            "target_record_id": "rec-0",
            "review_set": "oro",
            "requires_second_review": True,
        },
    )
    client.post("/queue", json={"target_record_id": "rec-1", "review_set": "corpus"})
    assert first.json()["review_set"] == "oro"
    assert first.json()["requires_second_review"] is True
    assert [row["target_record_id"] for row in client.get(
        "/queue?entity_type=medicamento&block_type=general&review_set=oro"
        "&requires_second_review=true"
    ).json()] == ["rec-0"]


def test_batch_assignment_is_atomic_and_versioned(client: TestClient) -> None:
    first = client.post("/queue", json={"target_record_id": "rec-0"}).json()
    second = client.post("/queue", json={"target_record_id": "rec-1"}).json()
    stale = client.post(
        "/queue/assign-batch",
        json={
            "reviewer_id": "ana",
            "items": [
                {"target_record_id": "rec-0", "expected_version": first["version"]},
                {"target_record_id": "rec-1", "expected_version": second["version"] + 1},
            ],
        },
    )
    assert stale.status_code == 409
    assert client.get("/queue/rec-0").json()["state"] == "pendiente"
    assigned = client.post(
        "/queue/assign-batch",
        json={
            "reviewer_id": "ana",
            "items": [
                {"target_record_id": "rec-0", "expected_version": first["version"]},
                {"target_record_id": "rec-1", "expected_version": second["version"]},
            ],
        },
    )
    assert assigned.status_code == 200
    assert {row["assignee_id"] for row in assigned.json()} == {"ana"}


def test_batch_rejects_duplicate_records(client: TestClient) -> None:
    item = client.post("/queue", json={"target_record_id": "rec-0"}).json()
    response = client.post(
        "/queue/assign-batch",
        json={
            "reviewer_id": "ana",
            "items": [
                {"target_record_id": "rec-0", "expected_version": item["version"]},
                {"target_record_id": "rec-0", "expected_version": item["version"]},
            ],
        },
    )
    assert response.status_code == 400


def test_assigning_twice_reports_conflict_not_server_error(client: TestClient) -> None:
    """409 y no 500: que otro llegara antes es un resultado previsible."""
    client.post("/queue", json={"target_record_id": "rec-0"})
    assert client.post("/queue/rec-0/assign", json={"reviewer_id": "ana"}).status_code == 200
    clash = client.post("/queue/rec-0/assign", json={"reviewer_id": "luis"})
    assert clash.status_code == 409
    assert "asignado" in clash.json()["detail"]


def test_a_stale_screen_cannot_complete_someone_elses_progress(client: TestClient) -> None:
    client.post("/queue", json={"target_record_id": "rec-0"})
    assigned = client.post("/queue/rec-0/assign", json={"reviewer_id": "ana"}).json()
    client.post("/queue/rec-0/transition", json={"reviewer_id": "ana", "state": "en_revision"})
    stale = client.post(
        "/queue/rec-0/transition",
        json={
            "reviewer_id": "ana",
            "state": "completado",
            "expected_version": assigned["version"],
        },
    )
    assert stale.status_code == 409


def test_an_illegal_transition_is_a_client_error(client: TestClient) -> None:
    client.post("/queue", json={"target_record_id": "rec-0"})
    client.post("/queue/rec-0/assign", json={"reviewer_id": "ana"})
    refused = client.post(
        "/queue/rec-0/transition", json={"reviewer_id": "ana", "state": "completado"}
    )
    assert refused.status_code == 400


def test_claiming_next_returns_null_when_the_queue_is_empty(client: TestClient) -> None:
    assert client.post("/queue/next", json={"reviewer_id": "ana"}).json() is None


def test_unknown_record_is_not_found(client: TestClient) -> None:
    assert client.get("/queue/does-not-exist").status_code == 404


def test_the_queue_can_be_switched_off(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'off.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    off = TestClient(create_app(Settings(database_url=url, enable_review_queue=False)))
    assert off.get("/queue").status_code == 404


def test_maturity_never_claims_clinical_validation(client: TestClient) -> None:
    """El endpoint que resume el estado no puede mentir sobre la validación."""
    body = client.get("/maturity").json()
    assert body["clinically_validated"] is False
    assert body["flags"]["enable_llm_prefill"] is False
    assert "GOLD-002" in body["clinical_blockers"]
    assert not any(
        c["level"] in ("clinicamente_validada", "lista_para_produccion")
        for c in body["capabilities"]
    )
