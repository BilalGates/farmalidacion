"""Endpoints de acciones de novedades CIMA: bandeja, decisiones, origen y permisos."""

import pytest
from fastapi.testclient import TestClient
from maintenance_actions_support import (
    FakeCima,
    listing,
    seed_catalog_record,
    seed_event,
    seed_master_header,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_authentication import ANA, auth, corporate, signing_key  # noqa: F401

import pharma_validator_api.maintenance_actions_api as actions_api
from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.maintenance_actions import persist_actions
from pharma_validator_api.models import MaintenanceAction, MaintenanceChangeEvent

from test_maintenance_actions import STATE_REV, STATE_SUSP, derive  # isort: skip


@pytest.fixture
def api(scratch_db_url: str) -> tuple[TestClient, str]:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_catalog_record(session)
        seed_catalog_record(session, record_id="demo-1", cn="500000", demo=True)
        client = FakeCima(states={"600000": STATE_SUSP, "500000": STATE_SUSP})
        for event in (
            seed_event(session, areas=["estado", "comerc"], suffix="a"),
            seed_event(session, areas=["estado"], suffix="b", epoch=2000,
                       targets=(("demo-1", "500000"),)),
        ):
            persist_actions(session, derive(session, event, client))
        # Aviso sin registro en el catálogo.
        seed_event(session, areas=["prosp"], suffix="c", epoch=3000, nregistro="zzz", targets=())
        session.commit()
    engine.dispose()
    app = create_app(
        Settings(database_url=scratch_db_url, env="test", data_mode="real",
                 reviewers=("ana:Ana Ruiz:farmaceutico",))
    )
    return TestClient(app), scratch_db_url


def test_pending_tray_counts_by_kind_and_has_no_preselection(api) -> None:
    client, _ = api
    page = client.get("/maintenance/actions").json()
    assert page["origin"] == "real" and page["total"] == 2
    assert page["counts"] == {"revisar_comercializacion": 1, "revisar_estado": 1}
    item = next(i for i in page["items"] if i["kind"] == "revisar_estado")
    assert item["proposed_value"] is None and item["state"] == "pendiente"
    assert item["cima_fetched_at"].startswith("2026-10-30")
    assert item["cima_source_url"].endswith("/presentacion/600000")
    assert item["identity_name"] == "Medicamento rec-1"
    assert client.get("/maintenance/actions?kind=nope").status_code == 422


def test_origin_separation(api) -> None:
    client, _ = api
    real = client.get("/maintenance/actions").json()
    demo = client.get("/maintenance/actions?origin=demo").json()
    assert {i["data_origin"] for i in real["items"]} == {"real"}
    assert {i["data_origin"] for i in demo["items"]} == {"demo"}
    assert not {i["id"] for i in real["items"]} & {i["id"] for i in demo["items"]}
    history = client.get("/maintenance/actions/history?origin=demo").json()
    assert history["total"] == 0


def test_decide_flow_moves_action_to_history(api) -> None:
    client, _ = api
    item = next(i for i in client.get("/maintenance/actions").json()["items"]
                if i["kind"] == "revisar_estado")
    url = f"/maintenance/actions/{item['id']}/decisions"
    body = {"actor_id": "ana", "decision": "descartada", "reason": "", "expected_sequence": 0}
    assert client.post(url, json=body).status_code == 400
    ok = client.post(url, json={**body, "reason": "No aplica"})
    assert ok.status_code == 201 and ok.json()["sequence"] == 1
    assert client.post(url, json={**body, "reason": "No aplica"}).status_code == 409
    assert client.get("/maintenance/actions").json()["total"] == 1
    history = client.get("/maintenance/actions/history").json()
    assert [i["state"] for i in history["items"]] == ["descartada"]
    detail = client.get(f"/maintenance/actions/{item['id']}").json()
    assert detail["decisions"][0]["reason"] == "No aplica"
    assert client.get("/maintenance/actions/nope").status_code == 404
    unknown = client.post(url, json={**body, "actor_id": "nadie", "reason": "x"})
    assert unknown.status_code == 400


def test_send_to_review_endpoint(api) -> None:
    client, _ = api
    ids = [i["id"] for i in client.get("/maintenance/actions").json()["items"]]
    result = client.post("/maintenance/actions/send-to-review",
                         json={"actor_id": "ana", "action_ids": ids})
    assert result.status_code == 200
    assert result.json()["enqueued"] == ["rec-1"] and len(result.json()["decided"]) == 2
    assert client.get("/maintenance/actions").json()["total"] == 0
    assert client.post("/maintenance/actions/send-to-review",
                       json={"actor_id": "ana", "action_ids": []}).status_code == 422


def test_unlinked_events_are_listed_apart(api) -> None:
    client, _ = api
    page = client.get("/maintenance/actions/unlinked").json()
    assert page["total"] == 1 and page["items"][0]["nregistro"] == "zzz"
    assert page["items"][0]["diagnostic_code"] == "sin_registro_en_catalogo"
    assert client.get("/maintenance/actions/unlinked?limit=0").status_code == 400


def test_identity_actions_and_catalog_filter(api) -> None:
    client, _ = api
    mine = client.get("/catalog/identities/ident-rec-1/maintenance-actions").json()
    assert {i["kind"] for i in mine} == {"revisar_estado", "revisar_comercializacion"}
    assert client.get("/catalog/identities/nope/maintenance-actions").status_code == 404
    flagged = client.get("/catalog/identities?maintenance=pending").json()
    # Solo el origen del despliegue (REAL): la acción DEMO no cuenta.
    assert [i["id"] for i in flagged["items"]] == ["ident-rec-1"]
    for item in mine:
        client.post(f"/maintenance/actions/{item['id']}/decisions", json={
            "actor_id": "ana", "decision": "aceptada", "reason": "", "expected_sequence": 0})
    assert client.get("/catalog/identities/ident-rec-1/maintenance-actions").json() == []
    after = client.get("/catalog/identities?maintenance=pending").json()
    assert after["items"] == []
    assert client.get("/catalog/identities?maintenance=other").status_code == 422


def test_catalog_filter_maintenance_pending_reopened_counts(api) -> None:
    client, _ = api
    item = client.get("/catalog/identities/ident-rec-1/maintenance-actions").json()[0]
    url = f"/maintenance/actions/{item['id']}/decisions"
    client.post(url, json={"actor_id": "ana", "decision": "aceptada", "reason": "",
                           "expected_sequence": 0})
    client.post(url, json={"actor_id": "ana", "decision": "reabierta", "reason": "Me equivoqué",
                           "expected_sequence": 1})
    pending = client.get("/catalog/identities/ident-rec-1/maintenance-actions").json()
    assert item["id"] in {i["id"] for i in pending}


def test_backfill_endpoint_runs_in_background(api, monkeypatch: pytest.MonkeyPatch) -> None:
    client, url = api
    engine = create_engine(url)
    with Session(engine) as session:
        session.execute(MaintenanceAction.__table__.delete())  # type: ignore[attr-defined]
        session.commit()
    fake = FakeCima(states={"600000": STATE_REV, "500000": STATE_REV})
    monkeypatch.setattr(actions_api, "build_cima_client", lambda settings: fake)
    started = client.post("/maintenance/actions/backfill")
    assert started.status_code == 202 and started.json() == {
        "status": "iniciado", "origin": "real"}
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(MaintenanceAction)) > 0
        assert session.scalar(select(func.count()).select_from(MaintenanceChangeEvent)) == 3
    again = client.post("/maintenance/actions/backfill", json={"limit": 1})
    assert again.status_code == 202


def test_access_policy_maintenance_actions(corporate, signing_key) -> None:  # noqa: F811
    client, _ = corporate
    reader = auth(signing_key, roles=["Reader"])  # solo catalog.read
    admin = auth(signing_key)
    reads = ["/maintenance/actions", "/maintenance/actions/history",
             "/maintenance/actions/unlinked", "/maintenance/actions/x"]
    posts = [("/maintenance/actions/x/decisions",
              {"actor_id": "ana", "decision": "aceptada", "expected_sequence": 0}),
             ("/maintenance/actions/send-to-review", {"actor_id": "ana", "action_ids": ["x"]}),
             ("/maintenance/actions/backfill", {})]
    for path in reads:
        assert client.get(path).status_code == 401
        assert client.get(path, headers=reader).status_code == 403, path
        assert client.get(path, headers=admin).status_code != 403, path
    for path, body in posts:
        assert client.post(path, json=body).status_code == 401
        assert client.post(path, json=body, headers=reader).status_code == 403, path
    identity = "/catalog/identities/x/maintenance-actions"
    assert client.get(identity, headers=reader).status_code == 404  # pasó la política
    # El actor del cuerpo debe coincidir con la sesión (patrón existente).
    forged = {"actor_id": "luis", "decision": "aceptada", "expected_sequence": 0}
    assert client.post("/maintenance/actions/x/decisions", json=forged,
                       headers=admin).status_code == 403
    assert client.post("/maintenance/actions/x/decisions", json={**forged, "actor_id": "ana"},
                       headers=admin).status_code == 404


def test_alta_through_api_lists_proposal(scratch_db_url: str) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_catalog_record(session)
        seed_master_header(session)
        event = seed_event(session, areas=["estado"], change_type=1, targets=(), nregistro="9001")
        persist_actions(session, derive(
            session, event, FakeCima(lists={"9001": listing(("777777", "NUEVO"))})))
        session.commit()
    client = TestClient(create_app(Settings(
        database_url=scratch_db_url, env="test", data_mode="real",
        reviewers=("ana:Ana Ruiz:farmaceutico",))))
    item = client.get("/maintenance/actions?kind=proponer_alta").json()["items"][0]
    assert item["target_record_id"] is None and item["proposal"]["columns"][2]["value"] == "777777"
    created = client.post(f"/maintenance/actions/{item['id']}/decisions", json={
        "actor_id": "ana", "decision": "aceptada", "reason": "", "expected_sequence": 0})
    assert created.status_code == 201


def test_individual_route_rejects_enviada_revision(api) -> None:
    client, _ = api
    item = client.get("/maintenance/actions").json()["items"][0]
    sent = client.post(f"/maintenance/actions/{item['id']}/decisions", json={
        "actor_id": "ana", "decision": "enviada_revision", "reason": "", "expected_sequence": 0})
    assert sent.status_code == 422
    assert client.get("/maintenance/actions").json()["total"] == 2


def test_action_of_other_origin_is_not_found(api) -> None:
    client, _ = api
    demo = client.get("/maintenance/actions?origin=demo").json()["items"][0]
    assert client.get(f"/maintenance/actions/{demo['id']}").status_code == 404
    refused = client.post(f"/maintenance/actions/{demo['id']}/decisions", json={
        "actor_id": "ana", "decision": "aceptada", "reason": "", "expected_sequence": 0})
    assert refused.status_code == 404
    assert client.get("/maintenance/actions?origin=demo").json()["total"] == 1
