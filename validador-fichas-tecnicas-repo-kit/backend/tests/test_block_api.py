"""API de edición de bloques repetibles (DEV-507).

Se ejercita el contrato HTTP: qué códigos devuelve, qué mensajes deja llegar al
revisor y, sobre todo, que una operación rechazada no escriba nada.

Base desechable con el esquema real. El corpus real no se toca.
"""

from __future__ import annotations

import pytest
from conftest import seed_reviewable_record
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app

BLOCK = "active_ingredient_general"


@pytest.fixture
def client(scratch_db_url: str) -> TestClient:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session, occurrences=2)
    engine.dispose()
    settings = Settings(
        env="test", database_url=scratch_db_url, reviewers=("ana:Ana Farmacéutica",)
    )
    return TestClient(create_app(settings))


def test_reads_the_occurrences_of_a_block(client: TestClient) -> None:
    response = client.get(f"/records/rec-1/blocks/{BLOCK}")
    assert response.status_code == 200
    body = response.json()
    assert [item["ordinal"] for item in body] == [1, 2]
    assert all(item["from_source"] for item in body)
    assert all(item["not_applicable"] is False for item in body)


def test_unknown_record_is_not_found(client: TestClient) -> None:
    assert client.get(f"/records/no-existe/blocks/{BLOCK}").status_code == 404


def test_creating_an_occurrence_assigns_the_identifier_on_the_server(
    client: TestClient,
) -> None:
    response = client.post(
        f"/records/rec-1/blocks/{BLOCK}",
        json={
            "operation": "crear",
            "reviewer_id": "ana",
            "values": [["DESCRIPCION", "añadida"]],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 3
    created = body[-1]
    # La ocurrencia nueva no procede de ninguna fuente.
    assert created["from_source"] is False
    assert created["ordinal"] == 3


def test_an_unknown_reviewer_cannot_edit_the_model(client: TestClient) -> None:
    response = client.post(
        f"/records/rec-1/blocks/{BLOCK}",
        json={"operation": "crear", "reviewer_id": "quien-sea", "values": []},
    )
    assert response.status_code == 400
    assert "Revisor no reconocido" in response.json()["detail"]
    # Nada se ha creado.
    assert len(client.get(f"/records/rec-1/blocks/{BLOCK}").json()) == 2


def test_deleting_an_imported_occurrence_without_comment_is_refused(
    client: TestClient,
) -> None:
    response = client.post(
        f"/records/rec-1/blocks/{BLOCK}",
        json={
            "operation": "eliminar",
            "reviewer_id": "ana",
            "occurrence_id": "blk-rec-1-1",
        },
    )
    assert response.status_code == 400
    # El mensaje explica por qué y sugiere la operación correcta.
    assert "comentario" in response.json()["detail"]
    assert "no aplicable" in response.json()["detail"]
    assert len(client.get(f"/records/rec-1/blocks/{BLOCK}").json()) == 2


def test_a_rejected_operation_leaves_no_history(client: TestClient) -> None:
    client.post(
        f"/records/rec-1/blocks/{BLOCK}",
        json={
            "operation": "eliminar",
            "reviewer_id": "ana",
            "occurrence_id": "blk-rec-1-1",
        },
    )
    assert client.get("/records/rec-1/block-history").json() == []


def test_reordering_that_drops_an_occurrence_is_refused(client: TestClient) -> None:
    response = client.post(
        f"/records/rec-1/blocks/{BLOCK}",
        json={
            "operation": "reordenar",
            "reviewer_id": "ana",
            "ordered_ids": ["blk-rec-1-1"],
        },
    )
    assert response.status_code == 400
    assert len(client.get(f"/records/rec-1/blocks/{BLOCK}").json()) == 2


def test_marking_not_applicable_is_recorded_and_reversible(client: TestClient) -> None:
    marked = client.post(
        f"/records/rec-1/blocks/{BLOCK}",
        json={
            "operation": "marcar_no_aplicable",
            "reviewer_id": "ana",
            "occurrence_id": "blk-rec-1-1",
            "comment": "Fuera de alcance para esta ficha.",
        },
    )
    assert marked.status_code == 200, marked.text
    first = next(
        item for item in marked.json() if item["occurrence_id"] == "blk-rec-1-1"
    )
    assert first["not_applicable"] is True
    # Marcar no borra: los valores siguen presentes.
    assert first["values"] != []

    reverted = client.post(
        f"/records/rec-1/blocks/{BLOCK}",
        json={
            "operation": "revertir_no_aplicable",
            "reviewer_id": "ana",
            "occurrence_id": "blk-rec-1-1",
            "comment": "Vuelve a aplicar.",
        },
    )
    assert reverted.status_code == 200
    assert (
        next(
            item for item in reverted.json() if item["occurrence_id"] == "blk-rec-1-1"
        )["not_applicable"]
        is False
    )

    history = client.get("/records/rec-1/block-history").json()
    assert [item["operation"] for item in history] == [
        "marcar_no_aplicable",
        "revertir_no_aplicable",
    ]
    assert [item["sequence"] for item in history] == [1, 2]
    assert history[0]["reviewer_id"] == "ana"
    # La firma identifica a quien dijo ser, no a quien era (D-018).
    assert history[0]["reviewer_assurance"] == "declarada"


def test_history_records_who_asked_for_each_change(client: TestClient) -> None:
    client.post(
        f"/records/rec-1/blocks/{BLOCK}",
        json={
            "operation": "eliminar",
            "reviewer_id": "ana",
            "occurrence_id": "blk-rec-1-2",
            "comment": "La fuente la duplicaba.",
        },
    )
    history = client.get("/records/rec-1/block-history").json()
    assert len(history) == 1
    assert history[0]["operation"] == "eliminar"
    assert history[0]["comment"] == "La fuente la duplicaba."
    assert history[0]["affected_ids"] == ["blk-rec-1-2"]


def test_the_review_screen_still_reads_the_record_after_editing(
    client: TestClient,
) -> None:
    # Editar un bloque no puede dejar el registro ilegible para `/records/{id}`,
    # que es lo que consume la pantalla de revisión.
    client.post(
        f"/records/rec-1/blocks/{BLOCK}",
        json={
            "operation": "eliminar",
            "reviewer_id": "ana",
            "occurrence_id": "blk-rec-1-2",
            "comment": "Retirada.",
        },
    )
    detail = client.get("/records/rec-1")
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["blocks"]) == 1
