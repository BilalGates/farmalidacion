"""API de medición de tiempos de revisión (DEV-508/509).

Lo que importa aquí no es que se sumen segundos, sino que no se sumen los que
no representan trabajo. Una pestaña abierta toda la noche no puede convertirse
en ocho horas de revisión: sobre esas cifras se calculará después el ahorro del
piloto farmacéutico.

Base desechable con el esquema real; el corpus real no se toca.
"""

from __future__ import annotations

import pytest
from conftest import seed_reviewable_record
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.time_measurement import INACTIVITY_THRESHOLD_SECONDS


@pytest.fixture
def client(scratch_db_url: str) -> TestClient:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session)
    engine.dispose()
    settings = Settings(env="test", database_url=scratch_db_url, reviewers=("ana:Ana",))
    return TestClient(create_app(settings))


def open_session(client: TestClient) -> str:
    response = client.post(
        "/timing/sessions", json={"target_record_id": "rec-1", "reviewer_id": "ana"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_a_measurement_session_is_not_synthetic_by_choice_of_the_client(
    client: TestClient,
) -> None:
    response = client.post(
        "/timing/sessions",
        # El cliente intenta marcarla; el servidor decide y lo ignora.
        json={
            "target_record_id": "rec-1",
            "reviewer_id": "ana",
            "is_synthetic": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["is_synthetic"] is False


def test_an_unknown_reviewer_cannot_open_a_session(client: TestClient) -> None:
    response = client.post(
        "/timing/sessions", json={"target_record_id": "rec-1", "reviewer_id": "nadie"}
    )
    assert response.status_code == 400


def test_unknown_record_is_not_found(client: TestClient) -> None:
    response = client.post(
        "/timing/sessions", json={"target_record_id": "no-existe", "reviewer_id": "ana"}
    )
    assert response.status_code == 404


def test_counts_the_focus_the_screen_declares(client: TestClient) -> None:
    session_id = open_session(client)
    for field, start, end in (
        ("DESCRIPCION", 1000.0, 1012.0),
        ("ACTIVO", 1012.0, 1020.0),
    ):
        assert (
            client.post(
                f"/timing/sessions/{session_id}/focus",
                json={"field_name": field, "started_at": start, "ended_at": end},
            ).status_code
            == 204
        )

    body = client.get(f"/timing/sessions/{session_id}").json()
    assert body["counted_seconds"] == 20
    assert body["discarded_seconds"] == 0
    assert body["fields"] == {"DESCRIPCION": 12, "ACTIVO": 8}


def test_an_abandoned_tab_does_not_become_hours_of_work(client: TestClient) -> None:
    session_id = open_session(client)
    # Ocho horas con el campo enfocado: la pantalla quedó abierta.
    client.post(
        f"/timing/sessions/{session_id}/focus",
        json={"field_name": "DESCRIPCION", "started_at": 0.0, "ended_at": 28800.0},
    )

    body = client.get(f"/timing/sessions/{session_id}").json()
    # Sólo cuenta hasta el umbral de inactividad; el resto se descarta y se
    # declara, en lugar de desaparecer sin dejar constancia.
    assert body["counted_seconds"] == INACTIVITY_THRESHOLD_SECONDS
    assert body["discarded_seconds"] == 28800 - INACTIVITY_THRESHOLD_SECONDS


def test_an_impossible_interval_is_refused(client: TestClient) -> None:
    session_id = open_session(client)
    response = client.post(
        f"/timing/sessions/{session_id}/focus",
        json={"field_name": "DESCRIPCION", "started_at": 100.0, "ended_at": 50.0},
    )
    assert response.status_code == 400


def test_a_closed_session_refuses_new_intervals(client: TestClient) -> None:
    session_id = open_session(client)
    client.post(
        f"/timing/sessions/{session_id}/focus",
        json={"field_name": "DESCRIPCION", "started_at": 0.0, "ended_at": 10.0},
    )
    closed = client.post(f"/timing/sessions/{session_id}/close")
    assert closed.status_code == 200
    assert closed.json()["counted_seconds"] == 10

    # Admitir tramos después invalidaría en silencio los agregados congelados.
    late = client.post(
        f"/timing/sessions/{session_id}/focus",
        json={"field_name": "ACTIVO", "started_at": 10.0, "ended_at": 20.0},
    )
    assert late.status_code == 400
    assert "cerrada" in late.json()["detail"]


def test_an_unknown_session_is_not_found(client: TestClient) -> None:
    assert client.get("/timing/sessions/no-existe").status_code == 404
    assert client.post("/timing/sessions/no-existe/close").status_code == 404
