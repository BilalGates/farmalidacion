"""Cruce exacto y decisiones auditables sin escribir en el maestro."""

from pathlib import Path
from types import SimpleNamespace

from conftest import seed_reviewable_record
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.access_policy import authorize
from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.models import (
    FieldValue,
    MedicationCatalogIdentity,
    NomenclatorReviewDecision,
    NomenclatorUserSnapshot,
)
from pharma_validator_api.nomenclator_snapshot import load_snapshot


def _snapshot_file(tmp_path: Path) -> Path:
    columns = [""] * 73
    columns[0] = "634287"
    columns[1] = "600000"
    columns[2] = "66337"
    columns[6] = "2431000140106"
    columns[20] = "https://example.test/ficha"
    columns[26] = "1"
    columns[48] = "J01CR02"
    columns[62] = "2026-10-01"
    columns[65] = "AMOXICILINA, ÁCIDO CLAVULÁNICO"
    path = tmp_path / "nomenclatur.tsv"
    path.write_text("\t".join(columns) + "\n", encoding="utf-8")
    return path


def _client(scratch_db_url: str, path: Path) -> TestClient:
    return TestClient(create_app(Settings(
        env="test", database_url=scratch_db_url, nomenclator_snapshot_path=path,
        reviewers=("ana:Ana Ruiz:farmaceutico", "bea:Bea:tecnico"),
    )))


def test_snapshot_rejects_malformed_or_duplicate_rows(tmp_path: Path) -> None:
    path = _snapshot_file(tmp_path)
    assert load_snapshot(path).row_count == 1
    path.write_text(path.read_text(encoding="utf-8") * 2, encoding="utf-8")
    try:
        load_snapshot(path)
    except ValueError as error:
        assert "duplicado" in str(error)
    else:
        raise AssertionError("Se aceptó un CN duplicado")


def test_snapshot_rejects_changed_content_under_hash_name(tmp_path: Path) -> None:
    original = _snapshot_file(tmp_path)
    named = tmp_path / ("nomenclatur-" + "0" * 64 + ".tsv")
    named.write_bytes(original.read_bytes())
    try:
        load_snapshot(named)
    except ValueError as error:
        assert "hash" in str(error)
    else:
        raise AssertionError("Se aceptó una instantánea alterada")


def test_comparison_and_decision_preserve_master(scratch_db_url: str, tmp_path: Path) -> None:
    path = _snapshot_file(tmp_path)
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(
            session, record_id="specialty-1", entity_type="specialty",
            fields=(("ME_IDEXTERNO", "med-10"), ("SW_USO_HOSPITALARIO", "S")),
        )
        seed_reviewable_record(
            session, record_id="medication-1", entity_type="medication",
            fields=(("MED_IDEXTERNO", "med-10"), ("MED_ATC", "J01CR02"),
                    ("MED_DCP", "old-dcp")),
        )
        session.add(MedicationCatalogIdentity(
            id="presentation-1", identity_type="presentation", code="600000",
            display_name="Producto", target_record_id="specialty-1",
            source_system="master_excel", source_version="v1",
        ))
        session.commit()
    api = _client(scratch_db_url, path)
    comparison = api.get("/nomenclator/identities/presentation-1/comparison")
    assert comparison.status_code == 200
    data = comparison.json()
    assert data["code"] == "600000"
    fields = {item["field_name"]: item for item in data["fields"]}
    assert fields["cod_atc"]["status"] == "coincide"
    assert fields["cod_dcp"]["status"] == "difiere"
    assert fields["sw_uso_hospitalario"]["status"] == "coincide"
    assert fields["principioactivo"]["status"] == "complemento"
    payload = {
        "field_name": "cod_dcp", "snapshot_sha256": data["snapshot_sha256"],
        "expected_sequence": 0, "action": "aceptar", "actor_id": "ana",
        "reason": "Contraste farmacéutico con fuente fechada.",
    }
    endpoint = "/nomenclator/identities/presentation-1/decisions"
    assert api.post(endpoint, json=payload).status_code == 201
    assert api.post(endpoint, json=payload).status_code == 409
    assert api.post("/nomenclator/identities/presentation-1/decisions", json={
        **payload, "expected_sequence": 1, "actor_id": "bea",
    }).status_code == 403
    assert api.post("/nomenclator/identities/presentation-1/decisions", json={
        **payload, "snapshot_sha256": "0" * 64,
    }).status_code == 409
    updated = api.get("/nomenclator/identities/presentation-1/comparison").json()
    dcp = next(item for item in updated["fields"] if item["field_name"] == "cod_dcp")
    assert dcp["latest_decision"]["action"] == "aceptar"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(NomenclatorReviewDecision)) == 1
        assert session.scalar(select(FieldValue.literal_value).where(
            FieldValue.field_name == "MED_DCP",
        )) == "old-dcp"


def test_personal_snapshots_are_isolated(scratch_db_url: str, tmp_path: Path) -> None:
    source = _snapshot_file(tmp_path)
    storage = tmp_path / "users"
    app = create_app(Settings(
        env="test", database_url=scratch_db_url, nomenclator_snapshot_dir=storage,
    ))

    async def identify(request: Request) -> None:
        request.state.principal = SimpleNamespace(
            subject_id=request.headers.get("X-Test-User", "user-a"),
        )

    app.dependency_overrides[authorize] = identify
    api = TestClient(app)
    imported = api.post(
        "/nomenclator/snapshots", content=source.read_bytes(),
        headers={"X-Test-User": "user-a", "Content-Type": "text/tab-separated-values"},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["changed"] is True
    assert imported.json()["row_count"] == 1
    assert api.get("/nomenclator/snapshot", headers={"X-Test-User": "user-a"}).json()[
        "available"
    ] is True
    assert api.get("/nomenclator/snapshot", headers={"X-Test-User": "user-b"}).json()[
        "available"
    ] is False
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(NomenclatorUserSnapshot)) == 1
