"""API de la cola: la capa HTTP no puede saltarse las barreras del dominio."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import Base, TargetRecord


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        for index in range(2):
            session.add(TargetRecord(id=f"rec-{index}", entity_type="medicamento"))
        session.commit()
    engine.dispose()
    return TestClient(create_app(Settings(database_url=url, reviewers=("ana:Ana Ruiz",))))


def test_enqueue_and_read_back(client: TestClient) -> None:
    created = client.post("/queue", json={"target_record_id": "rec-0", "priority": 3})
    assert created.status_code == 201
    assert created.json()["state"] == "pendiente"
    assert client.get("/queue/rec-0").json()["priority"] == 3


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
    client.post(
        "/queue/rec-0/transition", json={"reviewer_id": "ana", "state": "en_revision"}
    )
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
