from fastapi.testclient import TestClient

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app


def test_chat_without_linked_ft_returns_explicit_non_answer(scratch_db_url: str) -> None:
    client = TestClient(create_app(Settings(database_url=scratch_db_url, env="test")))
    response = client.post("/records/missing/chat", json={"question": "apartado 6.3"})

    assert response.status_code == 200
    assert response.json()["status"] == "not_available"
    assert response.json()["citations"] == []


def test_chat_rejects_extra_write_shaped_fields(scratch_db_url: str) -> None:
    client = TestClient(create_app(Settings(database_url=scratch_db_url, env="test")))
    response = client.post(
        "/records/record/chat",
        json={"question": "texto", "final_value": "500 mg"},
    )
    assert response.status_code == 422
