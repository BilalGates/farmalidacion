from fastapi.testclient import TestClient

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app


def client(scratch_db_url: str) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                database_url=scratch_db_url,
                env="test",
                reviewers=("ana:Ana Ruiz:farmaceutico",),
            )
        )
    )


def create_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "presentation-1",
        "identity_type": "presentation",
        "code": "654789",
        "display_name": "Producto ejemplo, 20 comprimidos",
        "actor_id": "ana",
        "reason": "Alta manual controlada.",
    }
    payload.update(overrides)
    return payload


def test_create_list_read_and_history(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    created = api.post("/catalog/identities", json=create_payload())
    assert created.status_code == 201
    assert created.json()["version"] == 1
    assert created.json()["source_system"] == "canonical_manual"

    page = api.get("/catalog/identities", params={"identity_type": "presentation"})
    assert page.status_code == 200
    assert page.json()["total"] == 1
    assert page.json()["items"][0]["code"] == "654789"

    detail = api.get("/catalog/identities/presentation-1")
    assert detail.status_code == 200
    assert detail.json()["display_name"] == "Producto ejemplo, 20 comprimidos"

    history = api.get("/catalog/identities/presentation-1/history")
    assert history.status_code == 200
    assert [item["action"] for item in history.json()] == ["crear"]
    assert history.json()[0]["actor_assurance"] == "declarada"


def test_update_and_archive_require_observed_version(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    assert api.post("/catalog/identities", json=create_payload()).status_code == 201
    changed = api.put(
        "/catalog/identities/presentation-1",
        json={
            "expected_version": 1,
            "display_name": "Producto ejemplo, 40 comprimidos",
            "code": "654789",
            "active": False,
            "actor_id": "ana",
            "reason": "Presentación sustituida.",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["version"] == 2
    assert changed.json()["active"] is False

    stale = api.put(
        "/catalog/identities/presentation-1",
        json={
            "expected_version": 1,
            "display_name": "Edición obsoleta",
            "code": "654789",
            "active": True,
            "actor_id": "ana",
            "reason": "Intento obsoleto.",
        },
    )
    assert stale.status_code == 409
    assert "recárguelo" in stale.json()["detail"]

    history = api.get("/catalog/identities/presentation-1/history").json()
    assert [item["action"] for item in history] == ["crear", "archivar"]


def test_inactive_rows_are_hidden_by_default_but_can_be_requested(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    assert api.post("/catalog/identities", json=create_payload()).status_code == 201
    assert api.put(
        "/catalog/identities/presentation-1",
        json={
            "expected_version": 1,
            "display_name": "Presentación archivada",
            "code": "654789",
            "active": False,
            "actor_id": "ana",
            "reason": "Ya no está vigente.",
        },
    ).status_code == 200

    assert api.get("/catalog/identities").json()["total"] == 0
    assert api.get("/catalog/identities", params={"active": False}).json()["total"] == 1


def test_unknown_actor_and_target_record_are_rejected(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    unknown_actor = api.post(
        "/catalog/identities", json=create_payload(actor_id="desconocido")
    )
    assert unknown_actor.status_code == 400

    missing_target = api.post(
        "/catalog/identities",
        json=create_payload(id="presentation-2", target_record_id="missing"),
    )
    assert missing_target.status_code == 404


def test_contract_rejects_unknown_identity_types_and_extra_fields(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    unknown_type = api.post(
        "/catalog/identities", json=create_payload(identity_type="marca_inventada")
    )
    assert unknown_type.status_code == 422

    extra = api.post("/catalog/identities", json=create_payload(silent_overwrite=True))
    assert extra.status_code == 422

