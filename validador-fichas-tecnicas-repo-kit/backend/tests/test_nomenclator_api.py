"""Cruce exacto y decisiones auditables sin escribir en el maestro."""

from pathlib import Path
from types import SimpleNamespace

from conftest import seed_reviewable_record
from fastapi import Request
from fastapi.testclient import TestClient
from httpx import Response
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


def _rows(*items: tuple[str, str]) -> bytes:
    """Filas de 73 columnas con CN y principio activo; sin datos de pacientes."""
    lines = []
    for index, (cn, active) in enumerate(items, start=1):
        columns = [""] * 73
        columns[0], columns[1], columns[2] = str(index), cn, f"R{cn}"
        columns[62], columns[65] = "2026-10-01", active
        lines.append("\t".join(columns))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _personal_app(scratch_db_url: str, tmp_path: Path) -> TestClient:
    app = create_app(Settings(
        env="test", database_url=scratch_db_url, nomenclator_snapshot_dir=tmp_path / "users",
    ))

    async def identify(request: Request) -> None:
        request.state.principal = SimpleNamespace(
            subject_id=request.headers.get("X-Test-User", "user-a"),
        )

    app.dependency_overrides[authorize] = identify
    return TestClient(app)


def _upload(api: TestClient, body: bytes, user: str = "user-a") -> Response:
    return api.post("/nomenclator/snapshots", content=body, headers={
        "X-Test-User": user, "Content-Type": "text/tab-separated-values",
    })


def test_resync_reports_changes_and_keeps_history(scratch_db_url: str, tmp_path: Path) -> None:
    api = _personal_app(scratch_db_url, tmp_path)
    first = _upload(api, _rows(("600000", "A"), ("600001", "B"), ("600002", "C")))
    assert first.status_code == 201
    assert first.json()["changes"]["added"] == 3
    second = _upload(api, _rows(("600000", "A"), ("600001", "B MODIFICADO"), ("600003", "D")))
    changes = second.json()["changes"]
    assert (changes["added"], changes["removed"], changes["modified"]) == (1, 1, 1)
    assert changes["sample_modified"] == ["600001"]
    assert changes["previous_sha256"] == first.json()["sha256"]
    repeated = _upload(api, _rows(("600000", "A"), ("600001", "B MODIFICADO"), ("600003", "D")))
    assert repeated.json()["changed"] is False
    assert repeated.json()["changes"] is None
    history = api.get("/nomenclator/snapshots").json()
    assert [item["changed"] for item in history] == [False, True, True]
    assert history[0]["current"] is True
    # Las versiones anteriores siguen legibles y su diferencia es reproducible.
    again = api.get(f"/nomenclator/snapshots/{history[1]['version_id']}/changes").json()
    assert again["modified"] == 1
    oldest = api.get(f"/nomenclator/snapshots/{history[2]['version_id']}/changes").json()
    assert oldest["previous_sha256"] is None
    info = api.get("/nomenclator/snapshot").json()
    assert info["version_count"] == 3
    assert info["synced_at"]


def test_failed_import_keeps_last_valid_version(scratch_db_url: str, tmp_path: Path) -> None:
    api = _personal_app(scratch_db_url, tmp_path)
    valid = _upload(api, _rows(("600000", "A")))
    truncated = _rows(("600001", "B"))[:-40]
    assert _upload(api, truncated).status_code == 422
    assert _upload(api, b"").status_code == 422
    info = api.get("/nomenclator/snapshot").json()
    assert info["sha256"] == valid.json()["sha256"]
    assert info["version_count"] == 1
    assert not list((tmp_path / "users").rglob("recepcion-*"))


def test_history_and_rows_are_private(scratch_db_url: str, tmp_path: Path) -> None:
    api = _personal_app(scratch_db_url, tmp_path)
    _upload(api, _rows(("600000", "A")), user="user-a")
    _upload(api, _rows(("700000", "Z")), user="user-b")
    version_a = api.get("/nomenclator/snapshots", headers={"X-Test-User": "user-a"}).json()
    assert len(version_a) == 1
    assert api.get(
        f"/nomenclator/snapshots/{version_a[0]['version_id']}/changes",
        headers={"X-Test-User": "user-b"},
    ).status_code == 404
    rows_b = api.get("/nomenclator/rows", headers={"X-Test-User": "user-b"}).json()
    assert [item["code"] for item in rows_b["items"]] == ["700000"]
    assert api.get("/nomenclator/snapshots", headers={"X-Test-User": "user-c"}).json() == []
    assert api.get("/nomenclator/rows", headers={"X-Test-User": "user-c"}).json()[
        "available"
    ] is False


def test_rows_and_reconciliation_use_exact_cn_only(
    scratch_db_url: str, tmp_path: Path,
) -> None:
    api = _personal_app(scratch_db_url, tmp_path)
    identities = [
        ("exact", "600000", "master_excel"), ("dup-1", "600001", "master_excel"),
        ("dup-2", "600001", "cima"), ("orphan", "999999", "master_excel"),
        # Un CN parecido no es una correspondencia.
        ("near", "60000", "master_excel"),
    ]
    with api.app.state.session_factory() as session:  # type: ignore[attr-defined]
        session.add_all([
            MedicationCatalogIdentity(
                id=identity_id, identity_type="presentation", code=code, display_name=code,
                source_system=system, source_version="v1",
            )
            for identity_id, code, system in identities
        ])
        session.commit()
    _upload(api, _rows(("600000", "AMOXICILINA"), ("600001", "B"), ("600002", "C")))
    rows = {item["code"]: item for item in api.get("/nomenclator/rows").json()["items"]}
    assert rows["600000"]["catalog_match"] == "exacta"
    assert rows["600000"]["catalog_identity_id"] == "exact"
    assert rows["600001"]["catalog_match"] == "ambigua"
    assert rows["600001"]["catalog_identity_id"] is None
    assert rows["600002"]["catalog_match"] == "sin_correspondencia"
    found = api.get("/nomenclator/rows", params={"q": "amoxi"}).json()
    assert found["total"] == 1
    assert found["items"][0]["values"]["principioactivo"] == "AMOXICILINA"
    summary = api.get("/nomenclator/reconciliation").json()
    assert (summary["exact"], summary["ambiguous"], summary["nomenclator_without_catalog"]) == (
        1, 1, 1,
    )
    assert summary["catalog_without_nomenclator"] == 2
    with api.app.state.session_factory() as session:  # type: ignore[attr-defined]
        assert session.scalar(
            select(func.count()).select_from(MedicationCatalogIdentity)
        ) == len(identities)


def test_volume_comparable_to_real_table(scratch_db_url: str, tmp_path: Path) -> None:
    rows = [(f"{600000 + index:06d}", f"PA {index}") for index in range(35_228)]
    api = _personal_app(scratch_db_url, tmp_path)
    imported = _upload(api, _rows(*rows))
    assert imported.status_code == 201
    assert imported.json()["row_count"] == 35_228
    page = api.get("/nomenclator/rows", params={"limit": 100, "offset": 35_200}).json()
    assert page["total"] == 35_228
    assert len(page["items"]) == 28
