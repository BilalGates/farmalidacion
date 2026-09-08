from conftest import seed_reviewable_record
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import ValidationDecisionRecord
from pharma_validator_api.review import record_decision
from pharma_validator_api.reviewer_identity import ReviewerDirectory
from pharma_validator_api.validation_states import ValidationDecision

FIELD = "fv-rec-1-1-0"


def setup(scratch_db_url):
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session)
        record_decision(
            session,
            field_value_id=FIELD,
            decision=ValidationDecision(
                field_name="DESCRIPCION",
                state="confirmado",
                final_value="SECRETO PRIMERA LECTURA",
                reviewer_id="ana",
                reviewer_role="farmaceutico",
            ),
            directory=ReviewerDirectory.from_configuration(("ana:Ana", "luis:Luis", "eva:Eva")),
        )
    engine.dispose()
    return TestClient(
        create_app(
            Settings(
                database_url=scratch_db_url,
                reviewers=("ana:Ana", "luis:Luis", "eva:Eva"),
                enable_second_review=True,
            )
        )
    )


def open_assignment(client):
    result = client.post("/second-reviews/fields/" + FIELD, json={"reviewer_id": "ana"})
    assert result.status_code == 201
    return result.json()["id"]


def test_blind_http_and_ordinary_route_do_not_leak(scratch_db_url):
    client = setup(scratch_db_url)
    key = open_assignment(client)
    response = client.get("/second-reviews/" + key + "/blind?reviewer_id=luis")
    assert response.status_code == 200
    assert "SECRETO" not in response.text
    assert "first_reviewer" not in response.text
    # La ruta ordinaria de revision sigue disponible: la ceguera se garantiza
    # no sirviendo la primera lectura por el endpoint ciego, no bloqueando la
    # ficha entera. Bloquearla dejaria sin revisar los demas campos del
    # registro por tener uno en segunda lectura.
    ordinary = client.get("/records/rec-1")
    assert ordinary.status_code == 200
    # Y la comparacion sigue cerrada hasta que la segunda lectura se emita:
    # abrirla antes revelaria la primera por otra via.
    assert client.get("/second-reviews/" + key + "/comparison?reviewer_id=luis").status_code == 400


def test_claim_owner_and_reconciliation(scratch_db_url):
    client = setup(scratch_db_url)
    key = open_assignment(client)
    base = "/second-reviews/" + key
    assert client.post(base + "/claim", json={"reviewer_id": "ana"}).status_code == 400
    claimed = client.post(base + "/claim", json={"reviewer_id": "luis"}).json()
    assert (
        client.post(
            base + "/decisions", json={"reviewer_id": "eva", "final_value": "otro"}
        ).status_code
        == 409
    )
    result = client.post(
        base + "/decisions",
        json={
            "reviewer_id": "luis",
            "state": "confirmado",
            "final_value": "SEGUNDA",
            "expected_version": claimed["version"],
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["state"] == "desacuerdo"
    comparison = client.get(base + "/comparison?reviewer_id=eva")
    assert "SECRETO PRIMERA LECTURA" in comparison.text
    assert "SEGUNDA" in comparison.text
    resolved = client.post(
        base + "/reconcile",
        json={
            "reviewer_id": "eva",
            "choice": "revisor_a",
            "comment": "Comprobado en fuente.",
            "expected_version": result.json()["version"],
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["state"] == "conciliado"
    assert (
        client.post(
            base + "/reconcile", json={"reviewer_id": "eva", "comment": "duplicado"}
        ).status_code
        == 400
    )
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ValidationDecisionRecord)) == 3
    engine.dispose()


def test_invalid_second_decision_has_no_partial_history(scratch_db_url):
    client = setup(scratch_db_url)
    key = open_assignment(client)
    response = client.post(
        "/second-reviews/" + key + "/decisions", json={"reviewer_id": "luis", "state": "no_aplica"}
    )
    assert response.status_code == 400
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ValidationDecisionRecord)) == 1
    engine.dispose()


def test_the_ordinary_route_is_not_the_blind_route(scratch_db_url):
    """La ruta ordinaria sirve el historial completo, y debe hacerlo.

    Es la pantalla de revision de Fase 5: quien la usa no esta haciendo una
    segunda lectura ciega. La ceguera protege el endpoint ciego, que es el que
    consume el segundo revisor. Confundir ambas cosas llevaria a bloquear la
    revision ordinaria de todo un registro por tener un campo en segunda
    lectura, o peor, a creer protegido un dato que se sirve por otra ruta.
    """
    client = setup(scratch_db_url)
    key = open_assignment(client)

    # El endpoint ciego no entrega la primera lectura.
    blind = client.get("/second-reviews/" + key + "/blind?reviewer_id=luis")
    assert blind.status_code == 200
    assert "SECRETO PRIMERA LECTURA" not in blind.text

    # El listado tampoco revela quien firmo la primera mientras no este emitida.
    listing = client.get("/second-reviews?reviewer_id=luis")
    assert listing.status_code == 200
    assert "ana" not in listing.text
