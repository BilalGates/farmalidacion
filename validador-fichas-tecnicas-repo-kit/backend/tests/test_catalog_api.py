from datetime import UTC, datetime

from fastapi.testclient import TestClient

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import (
    MedicationCatalogIdentity,
    MedicationCatalogRelation,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
)


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


def test_catalog_sort_is_server_side_and_stable(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    for identity_id, name, code in (
        ("item-a", "Beta", "20"),
        ("item-b", "Alfa", "30"),
        ("item-c", "Gamma", "10"),
    ):
        assert api.post(
            "/catalog/identities",
            json=create_payload(id=identity_id, display_name=name, code=code),
        ).status_code == 201

    by_name = api.get("/catalog/identities", params={"sort_by": "name_desc"})
    assert [item["display_name"] for item in by_name.json()["items"]] == [
        "Gamma", "Beta", "Alfa",
    ]
    by_code = api.get(
        "/catalog/identities", params={"sort_by": "code_asc", "limit": 2}
    )
    assert [item["code"] for item in by_code.json()["items"]] == ["10", "20"]
    assert api.get("/catalog/identities", params={"sort_by": "random"}).status_code == 422


def test_seven_digit_national_code_search_uses_six_digit_working_code(
    scratch_db_url: str,
) -> None:
    api = client(scratch_db_url)
    assert api.post(
        "/catalog/identities", json=create_payload(code="654789")
    ).status_code == 201

    by_six = api.get("/catalog/identities", params={"q": "654789"}).json()
    by_seven = api.get("/catalog/identities", params={"q": "6547893"}).json()
    invalid_length = api.get("/catalog/identities", params={"q": "65478930"}).json()

    assert by_six["total"] == 1
    assert by_seven["total"] == 1
    assert by_seven["items"][0]["code"] == "654789"
    assert invalid_length["total"] == 0


def test_catalog_can_be_filtered_by_its_exact_source_workbook(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    assert api.post("/catalog/identities", json=create_payload()).status_code == 201
    with api.app.state.session_factory() as session:
        document = SourceDocument(
            id="specialties-document",
            source_type="master_excel",
            name="Especialidades-CargaMaster190626.xlsx",
        )
        version = SourceDocumentVersion(
            id="specialties-version",
            document_id=document.id,
            content_hash="a" * 64,
            source_version=None,
            source_locator=document.name,
            acquired_at=datetime.now(UTC),
        )
        fragment = SourceFragment(
            id="specialties-fragment",
            document_version_id=version.id,
            locator_type="excel_row",
            locator='{"row":2,"sheet":"General"}',
            literal_text="{}",
        )
        identity = session.get(MedicationCatalogIdentity, "presentation-1")
        assert identity is not None
        session.add(document)
        session.flush()
        session.add(version)
        session.flush()
        session.add(fragment)
        session.flush()
        identity.source_fragment_id = fragment.id
        session.commit()

    source_view = api.get(
        "/catalog/identities",
        params={"source_workbook": "especialidades", "identity_type": "presentation"},
    )
    assert source_view.status_code == 200
    assert source_view.json()["total"] == 1
    assert source_view.json()["items"][0]["source_workbook"] == "especialidades"
    assert api.get(
        "/catalog/identities",
        params={"source_workbook": "medicamentos", "identity_type": "dcp"},
    ).json()["total"] == 0
    assert api.get(
        "/catalog/identities",
        params={"source_workbook": "especialidades", "identity_type": "dcp"},
    ).json()["total"] == 0
    assert api.get(
        "/catalog/identities", params={"source_workbook": "otro"}
    ).status_code == 422
    detail = api.get("/catalog/identities/presentation-1")
    assert detail.json()["source_workbook"] == "especialidades"
    changed = api.put(
        "/catalog/identities/presentation-1",
        json={
            "expected_version": 1,
            "display_name": "Producto revisado",
            "code": "654789",
            "active": True,
            "actor_id": "ana",
            "reason": "Prueba de que la procedencia sigue visible.",
        },
    )
    assert changed.json()["source_workbook"] == "especialidades"


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


def test_relations_show_direction_and_related_identity(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    assert api.post(
        "/catalog/identities",
        json=create_payload(id="dcp-1", identity_type="dcp", code="DCP-1"),
    ).status_code == 201
    assert api.post(
        "/catalog/identities",
        json=create_payload(
            id="ingredient-1",
            identity_type="active_ingredient",
            code="ING-1",
            display_name="Sustancia uno",
        ),
    ).status_code == 201
    with api.app.state.session_factory() as session:
        session.add(
            MedicationCatalogRelation(
                id="relation-1",
                relation_type="dcp_active_ingredient",
                source_identity_id="dcp-1",
                target_identity_id="ingredient-1",
                ordinal=1,
                source_fragment_id=None,
            )
        )
        session.commit()

    outgoing = api.get("/catalog/identities/dcp-1/relations")
    assert outgoing.status_code == 200
    assert outgoing.json()[0]["direction"] == "outgoing"
    assert outgoing.json()[0]["ordinal"] == 1
    assert outgoing.json()[0]["related_identity"]["display_name"] == "Sustancia uno"

    incoming = api.get("/catalog/identities/ingredient-1/relations")
    assert incoming.status_code == 200
    assert incoming.json()[0]["direction"] == "incoming"
    assert incoming.json()[0]["related_identity"]["id"] == "dcp-1"


def test_classifications_keep_commercial_class_exclusive_and_conditions_multiple(
    scratch_db_url: str,
) -> None:
    api = client(scratch_db_url)
    assert api.post("/catalog/identities", json=create_payload()).status_code == 201

    def set_class(kind: str, value: str, active: bool = True):
        return api.put(
            f"/catalog/identities/presentation-1/classifications/{kind}:{value}",
            json={
                "classification_type": kind,
                "value": value,
                "active": active,
                "actor_id": "ana",
                "reason": "Revisión funcional de prueba.",
            },
        )

    assert set_class("commercial_class", "generico").status_code == 200
    assert set_class("condition", "huerfano").status_code == 200
    assert set_class("condition", "uso_hospitalario").status_code == 200
    assert set_class("commercial_class", "biosimilar").status_code == 200

    active = api.get("/catalog/identities/presentation-1/classifications").json()
    assert {(item["classification_type"], item["value"]) for item in active} == {
        ("commercial_class", "biosimilar"),
        ("condition", "huerfano"),
        ("condition", "uso_hospitalario"),
    }
    history = api.get("/catalog/identities/presentation-1/classification-history").json()
    assert len(history) == 5
    assert history[-1]["actor_id"] == "ana"
    assert "Revisión funcional" in history[-1]["reason"]


def test_classifications_are_only_allowed_on_presentations(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    assert api.post(
        "/catalog/identities",
        json=create_payload(id="dcp-1", identity_type="dcp"),
    ).status_code == 201
    response = api.get("/catalog/identities/dcp-1/classifications")
    assert response.status_code == 422


def test_catalog_can_filter_presentations_by_classification(scratch_db_url: str) -> None:
    api = client(scratch_db_url)
    assert api.post("/catalog/identities", json=create_payload()).status_code == 201
    assert api.post(
        "/catalog/identities",
        json=create_payload(
            id="presentation-2", code="123456", display_name="Otra presentación"
        ),
    ).status_code == 201
    api.put(
        "/catalog/identities/presentation-1/classifications/commercial_class:generico",
        json={
            "classification_type": "commercial_class",
            "value": "generico",
            "actor_id": "ana",
            "reason": "Prueba.",
        },
    )
    api.put(
        "/catalog/identities/presentation-1/classifications/condition:huerfano",
        json={
            "classification_type": "condition",
            "value": "huerfano",
            "actor_id": "ana",
            "reason": "Prueba.",
        },
    )

    generic = api.get(
        "/catalog/identities",
        params={"identity_type": "presentation", "commercial_class": "generico"},
    )
    orphan = api.get(
        "/catalog/identities", params={"condition": "huerfano"}
    )
    assert [item["id"] for item in generic.json()["items"]] == ["presentation-1"]
    assert [item["id"] for item in orphan.json()["items"]] == ["presentation-1"]

    wrong_level = api.get(
        "/catalog/identities", params={"identity_type": "dcp", "condition": "huerfano"}
    )
    assert wrong_level.status_code == 422

    combined = api.get(
        "/catalog/identities",
        params={"commercial_class": "generico", "condition": "huerfano"},
    )
    assert [item["id"] for item in combined.json()["items"]] == ["presentation-1"]
    result_item = combined.json()["items"][0]
    assert result_item["commercial_class"] == "generico"
    assert result_item["conditions"] == ["huerfano"]

    api.put(
        "/catalog/identities/presentation-1/classifications/condition:uso_hospitalario",
        json={
            "classification_type": "condition",
            "value": "uso_hospitalario",
            "actor_id": "ana",
            "reason": "Prueba.",
        },
    )
    both_conditions = api.get(
        "/catalog/identities",
        params=[("condition", "huerfano"), ("condition", "uso_hospitalario")],
    )
    assert [item["id"] for item in both_conditions.json()["items"]] == ["presentation-1"]
    all_conditions = api.get(
        "/catalog/identities",
        params=[
            ("condition", "huerfano"),
            ("condition", "uso_hospitalario"),
            ("condition", "estupefaciente"),
        ],
    )
    assert all_conditions.json()["total"] == 0
