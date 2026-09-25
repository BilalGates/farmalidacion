import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import ImportBatch, ImportedSourceSheet, QuarantinedSourceRow


def test_quarantined_values_can_be_maintained_without_linking_or_mutating_source(
    scratch_db_url: str,
) -> None:
    api = TestClient(
        create_app(
            Settings(
                database_url=scratch_db_url,
                env="test",
                reviewers=("ana:Ana Ruiz:farmaceutico",),
            )
        )
    )
    source_payload = json.dumps(
        [
            {
                "column": 1,
                "formula": None,
                "header": "BN_DESCRIPCION",
                "literal_value": "Excipiente",
                "observed_type": "shared_string",
            },
            {
                "column": 2,
                "formula": None,
                "header": "BN_IDEXTERNO",
                "literal_value": "orphan-1",
                "observed_type": "shared_string",
            },
        ],
        ensure_ascii=False,
    )
    with api.app.state.session_factory() as session:
        session.add(
            ImportBatch(
                id="batch-1",
                source_system="master_excel",
                source_locator="Especialidades-CargaMaster190626.xlsx",
                source_version="v1",
                content_hash="a" * 64,
                importer_name="specialty",
                importer_version="1",
                status="completed",
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                source_document_version_id=None,
            )
        )
        session.add(
            ImportedSourceSheet(
                id="sheet-1",
                import_batch_id="batch-1",
                sheet_name="Excipientes",
                sheet_ordinal=1,
                header_row_number=1,
                header_payload=json.dumps(
                    [
                        {"column": 1, "literal_value": "BN_DESCRIPCION"},
                        {"column": 2, "literal_value": "BN_IDEXTERNO"},
                        {"column": 3, "literal_value": "BN_CODIGO"},
                    ]
                ),
                data_row_count=1,
                material_value_count=2,
            )
        )
        session.add(
            QuarantinedSourceRow(
                id="quarantine-1",
                import_batch_id="batch-1",
                quarantine_key="b" * 64,
                source_locator="Excipientes!42",
                reason_code="MISSING_PARENT",
                reason="No existe una única especialidad padre en esta versión.",
                raw_payload=source_payload,
                payload_hash="c" * 64,
                created_at=datetime.now(UTC),
            )
        )
        session.commit()

    listing = api.get("/records/quarantined?source_workbook=Especialidades-CargaMaster190626.xlsx")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["fields"][0]["field_name"] == "BN_DESCRIPCION"
    assert listing.json()["items"][0]["fields"][0]["maintained_value"] == "Excipiente"

    endpoint = "/records/quarantined/quarantine-1/values/1/maintenance"
    change = {
        "expected_sequence": 0,
        "value": "Excipiente corregido",
        "actor_id": "ana",
        "reason": "Corrección del nombre fuente.",
    }
    response = api.post(endpoint, json=change)
    assert response.status_code == 201
    assert response.json()["maintenance_sequence"] == 1
    assert response.json()["maintained_value"] == "Excipiente corregido"
    assert api.post(endpoint, json=change).status_code == 409

    refreshed = api.get("/records/quarantined").json()["items"][0]
    assert refreshed["reason_code"] == "MISSING_PARENT"
    assert refreshed["fields"][0]["literal_value"] == "Excipiente"
    assert refreshed["fields"][0]["maintained_value"] == "Excipiente corregido"
    assert refreshed["fields"][0]["maintenance_history"][0]["reason"] == change["reason"]
    with api.app.state.session_factory() as session:
        stored = session.get(QuarantinedSourceRow, "quarantine-1")
        assert stored is not None
        assert stored.raw_payload == source_payload
        assert stored.reason_code == "MISSING_PARENT"

    empty_endpoint = "/records/quarantined/quarantine-1"
    assert api.get(f"{empty_endpoint}/empty-source-columns").json() == [
        {"source_column_index": 3, "field_name": "BN_CODIGO"}
    ]
    new_value = {
        "source_column_index": 3,
        "value": "Nuevo código",
        "actor_id": "ana",
        "reason": "Completar columna vacía",
    }
    assert (
        api.post(
            f"{empty_endpoint}/empty-source-values", json={**new_value, "source_column_index": 9}
        ).status_code
        == 422
    )
    created = api.post(f"{empty_endpoint}/empty-source-values", json=new_value)
    assert created.status_code == 201, created.json()
    assert created.json()["literal_value"] is None
    assert created.json()["maintained_value"] == "Nuevo código"
    assert api.post(f"{empty_endpoint}/empty-source-values", json=new_value).status_code == 409
    updated = api.get("/records/quarantined").json()["items"][0]
    assert updated["reason_code"] == "MISSING_PARENT"
    assert updated["fields"][2]["field_name"] == "BN_CODIGO"
    assert updated["fields"][2]["maintenance_history"][0]["before_value"] is None
    with api.app.state.session_factory() as session:
        stored = session.get(QuarantinedSourceRow, "quarantine-1")
        assert stored is not None and stored.raw_payload == source_payload
