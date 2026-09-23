from datetime import UTC, datetime

from fastapi.testclient import TestClient

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import (
    BlockInstance,
    FieldValue,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)


def seed_record(session) -> None:
    document = SourceDocument(id="doc-rec-1", source_type="master_excel", name="Maestro")
    session.add(document)
    session.flush()
    session.add(
        SourceDocumentVersion(
            id="ver-rec-1",
            document_id=document.id,
            content_hash="0" * 64,
            source_version="v1",
            source_locator="Maestro.xlsx",
            acquired_at=datetime.now(UTC),
        )
    )
    session.flush()
    session.add(TargetRecord(id="rec-1", entity_type="active_ingredient"))
    session.flush()
    fragment = SourceFragment(
        id="frag-rec-1-1",
        document_version_id="ver-rec-1",
        locator_type="excel_row",
        locator='{"sheet":"Hoja1","row":1}',
        literal_text="Fragmento literal.",
    )
    session.add(fragment)
    session.flush()
    session.add(
        BlockInstance(
            id="blk-rec-1-1",
            target_record_id="rec-1",
            block_type="active_ingredient_general",
            ordinal=1,
            source_fragment_id=fragment.id,
        )
    )
    session.flush()
    value = FieldValue(
        id="fv-rec-1-1-0",
        block_instance_id="blk-rec-1-1",
        field_name="DESCRIPCION",
        literal_value="ácido nicotínico",
        observed_type="texto",
        logical_state="valued",
    )
    session.add(value)
    session.flush()
    session.add(
        ValueProvenance(
            id="vp-rec-1-1-0",
            field_value_id=value.id,
            source_fragment_id=fragment.id,
            provenance_role="master_baseline",
        )
    )
    session.commit()


def test_field_maintenance_preserves_source_and_is_separate_from_review(
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
    with api.app.state.session_factory() as session:
        seed_record(session)

    first = api.post(
        "/records/values/fv-rec-1-1-0/maintenance",
        json={
            "expected_sequence": 0,
            "value": "Ácido nicotínico",
            "actor_id": "ana",
            "reason": "Normalización de mayúsculas.",
        },
    )
    assert first.status_code == 201
    assert first.json()["before_value"] == "ácido nicotínico"

    detail = api.get("/records/rec-1").json()
    field = detail["blocks"][0]["values"][0]
    assert field["literal_value"] == "ácido nicotínico"
    assert field["maintained_value"] == "Ácido nicotínico"
    assert field["maintenance_sequence"] == 1
    assert field["history"] == []
    assert field["maintenance_history"][0]["reason"] == "Normalización de mayúsculas."

    with api.app.state.session_factory() as session:
        source_field = session.get(FieldValue, "fv-rec-1-1-0")
        assert source_field is not None
        assert source_field.literal_value == "ácido nicotínico"


def test_field_maintenance_rejects_stale_edit_and_blank_reason(scratch_db_url: str) -> None:
    api = TestClient(
        create_app(
            Settings(
                database_url=scratch_db_url,
                env="test",
                reviewers=("ana:Ana Ruiz:farmaceutico",),
            )
        )
    )
    with api.app.state.session_factory() as session:
        seed_record(session)
    endpoint = "/records/values/fv-rec-1-1-0/maintenance"
    payload = {
        "expected_sequence": 0,
        "value": "Primera corrección",
        "actor_id": "ana",
        "reason": "Corrección fuente.",
    }
    assert api.post(endpoint, json=payload).status_code == 201
    assert api.post(endpoint, json=payload).status_code == 409
    assert (
        api.post(
            endpoint,
            json={**payload, "expected_sequence": 1, "reason": "  "},
        ).status_code
        == 400
    )
