"""API de exportación, exclusiones, auditoría y riesgo (DEV-604/605/606/609).

Base desechable con el esquema real; el corpus real no se toca.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import seed_reviewable_record
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.review import record_decision
from pharma_validator_api.reviewer_identity import ReviewerDirectory
from pharma_validator_api.validation_states import ValidationDecision

DIRECTORY = ReviewerDirectory.from_configuration(("ana:Ana",))

PROFILE = {
    "actor_id": "ana",
    "profile_name": "perfil-prueba",
    "fmt": "csv",
    "columns": [
        {"name": "Descripcion", "source_field": "DESCRIPCION", "required": True},
        {"name": "Activo", "source_field": "ACTIVO"},
    ],
}


def build(scratch_db_url: str, tmp_path: Path, *, enabled: bool = True) -> TestClient:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session)
        for field_id, name, value in (
            ("fv-rec-1-1-0", "DESCRIPCION", "acido nicotinico"),
            ("fv-rec-1-1-1", "ACTIVO", "N"),
        ):
            record_decision(
                session,
                field_value_id=field_id,
                decision=ValidationDecision(
                    field_name=name,
                    state="confirmado",
                    final_value=value,
                    reviewer_id="ana",
                    reviewer_role="farmaceutico",
                ),
                directory=DIRECTORY,
            )
    engine.dispose()
    return TestClient(
        create_app(
            Settings(
                env="test",
                database_url=scratch_db_url,
                reviewers=("ana:Ana",),
                enable_export=enabled,
                export_artifact_dir=tmp_path / "exports",
            )
        )
    )


def test_export_is_off_by_default(scratch_db_url: str, tmp_path: Path) -> None:
    # D-011 sigue pendiente: encenderla es decisión de quien opera, no efecto
    # de haber programado el motor.
    client = build(scratch_db_url, tmp_path, enabled=False)
    assert client.post("/exports", json=PROFILE).status_code == 404


def test_a_run_produces_an_artifact_and_a_summary(
    scratch_db_url: str, tmp_path: Path
) -> None:
    client = build(scratch_db_url, tmp_path)
    response = client.post("/exports", json=PROFILE)
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["status"] == "completado"
    assert body["delivered_rows"] == 1
    assert body["content_hash"]
    # Un perfil que produce fichero no es un contrato aceptado.
    assert body["provider_accepted"] is False

    written = list((tmp_path / "exports").glob("*.csv"))
    assert len(written) == 1
    assert "acido nicotinico" in written[0].read_text(encoding="utf-8")


def test_an_unknown_actor_cannot_export(scratch_db_url: str, tmp_path: Path) -> None:
    client = build(scratch_db_url, tmp_path)
    response = client.post("/exports", json={**PROFILE, "actor_id": "nadie"})
    assert response.status_code == 400


def test_a_malformed_profile_is_refused(scratch_db_url: str, tmp_path: Path) -> None:
    client = build(scratch_db_url, tmp_path)
    # Dos columnas con el mismo nombre: el fichero sería ambiguo.
    broken = {
        **PROFILE,
        "columns": [
            {"name": "X", "source_field": "DESCRIPCION"},
            {"name": "X", "source_field": "ACTIVO"},
        ],
    }
    response = client.post("/exports", json=broken)
    assert response.status_code == 400
    assert "repite nombres de columna" in response.json()["detail"]


def test_unknown_fields_in_the_request_are_refused(
    scratch_db_url: str, tmp_path: Path
) -> None:
    client = build(scratch_db_url, tmp_path)
    # Un campo desconocido suele ser una opción mal escrita; aceptarlo en
    # silencio produciría un export distinto del que se pidió.
    response = client.post("/exports", json={**PROFILE, "delimiterr": "|"})
    assert response.status_code == 422


def test_the_run_is_listed_with_its_counts(scratch_db_url: str, tmp_path: Path) -> None:
    client = build(scratch_db_url, tmp_path)
    created = client.post("/exports", json=PROFILE).json()

    listing = client.get("/exports").json()
    assert len(listing) == 1
    assert listing[0]["run_id"] == created["run_id"]
    assert listing[0]["row_count"] == 1
    assert listing[0]["content_hash"] == created["content_hash"]
    assert listing[0]["profile_version"]


def test_the_archived_profile_can_be_read_back(
    scratch_db_url: str, tmp_path: Path
) -> None:
    client = build(scratch_db_url, tmp_path)
    run_id = client.post("/exports", json=PROFILE).json()["run_id"]

    stored = client.get(f"/exports/{run_id}/profile").json()
    # La configuración archivada es lo que hace repetible una ejecución.
    assert stored["profile"]["name"] == "perfil-prueba"
    assert [c["name"] for c in stored["profile"]["columns"]] == ["Descripcion", "Activo"]


def test_exclusions_are_reported_with_their_reason(
    scratch_db_url: str, tmp_path: Path
) -> None:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session, record_id="rec-2")
    engine.dispose()

    client = build(scratch_db_url, tmp_path)
    run_id = client.post("/exports", json=PROFILE).json()["run_id"]

    exclusions = client.get(f"/exports/{run_id}/exclusions").json()
    assert exclusions
    excluded = exclusions[0]
    assert excluded["target_record_id"] == "rec-2"
    assert excluded["severity"] == "bloqueante"
    assert excluded["rule"] == "campo_sin_validar"
    assert excluded["detail"]


def test_exclusions_of_an_unknown_run_are_not_found(
    scratch_db_url: str, tmp_path: Path
) -> None:
    client = build(scratch_db_url, tmp_path)
    assert client.get("/exports/no-existe/exclusions").status_code == 404


def test_the_record_history_is_served(scratch_db_url: str, tmp_path: Path) -> None:
    client = build(scratch_db_url, tmp_path)
    history = client.get("/audit/records/rec-1").json()

    assert len(history) == 2
    assert {item["source"] for item in history} == {"decision"}
    assert {item["actor_id"] for item in history} == {"ana"}
    # En orden cronológico: reconstruir qué pasó exige saber en qué orden.
    assert [item["occurred_at"] for item in history] == sorted(
        item["occurred_at"] for item in history
    )


def test_the_history_of_an_unknown_record_is_not_found(
    scratch_db_url: str, tmp_path: Path
) -> None:
    client = build(scratch_db_url, tmp_path)
    assert client.get("/audit/records/no-existe").status_code == 404


def test_the_export_leaves_an_audit_event(scratch_db_url: str, tmp_path: Path) -> None:
    client = build(scratch_db_url, tmp_path)
    run_id = client.post("/exports", json=PROFILE).json()["run_id"]

    events = client.get(f"/audit/events?entity_type=export_run&entity_id={run_id}").json()
    assert len(events) == 1
    assert events[0]["action"] == "exportacion"
    assert events[0]["actor_id"] == "ana"


def test_risk_rules_declare_their_pending_decision(
    scratch_db_url: str, tmp_path: Path
) -> None:
    client = build(scratch_db_url, tmp_path)
    body = client.get("/risk/rules").json()

    assert [rule["atc_prefix"] for rule in body["rules"]] == ["L04"]
    # La API dice explícitamente que ampliar la lista no le corresponde.
    assert "D-017" in body["pending_decision"]
    assert "farmacia" in body["pending_decision"]


@pytest.mark.parametrize(
    ("code", "expected", "undetermined"),
    [
        ("L04AB01", True, False),
        ("A02BC01", False, False),
        (None, None, True),
        ("no-es-atc", None, True),
    ],
)
def test_risk_assessment_over_http(
    scratch_db_url: str,
    tmp_path: Path,
    code: str | None,
    expected: bool | None,
    undetermined: bool,
) -> None:
    client = build(scratch_db_url, tmp_path)
    query = f"?atc={code}" if code is not None else ""
    body = client.get(f"/risk/assess{query}").json()
    assert body["requires_double_review"] is expected
    assert body["undetermined"] is undetermined
