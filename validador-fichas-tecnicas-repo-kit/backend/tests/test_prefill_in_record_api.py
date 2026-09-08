"""Consumo de la política de pre-relleno en la pantalla de revisión (DEV-512).

La especificación 9 existe porque un revisor que ve 300 campos en una mañana
acepta lo que la pantalla le propone. Estas pruebas comprueban que la API no
propone nada mientras no haya una decisión farmacéutica que lo autorice.

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
from pharma_validator_api.prefill_policy import (
    DEFAULT_POLICY,
    assert_no_protected_preselection,
    plan_field_presentation,
    select_bulk_confirmable,
)


@pytest.fixture
def client(scratch_db_url: str) -> TestClient:
    engine = create_engine(scratch_db_url)
    with Session(engine) as session:
        seed_reviewable_record(session)
    engine.dispose()
    settings = Settings(env="test", database_url=scratch_db_url, reviewers=("ana:Ana",))
    return TestClient(create_app(settings))


def test_the_conservative_policy_is_the_default() -> None:
    # Mientras D-015 no fije umbrales, no se propone ningún valor.
    assert DEFAULT_POLICY == "solo_evidencia"


def test_every_field_is_served_without_a_proposed_value(client: TestClient) -> None:
    detail = client.get("/records/rec-1")
    assert detail.status_code == 200, detail.text
    values = detail.json()["blocks"][0]["values"]
    assert values

    for value in values:
        assert value["prefill_policy"] == "solo_evidencia"
        assert value["prefill_presentation"] == "casilla_vacia"
        # Lo esencial: la pantalla no recibe nada que pueda preseleccionar.
        assert value["proposed_value"] is None
        assert value["prefill_options"] == []
        # El aviso nombra que la decisión es criterio clínico.
        assert "criterio farmacéutico" in value["prefill_warning"]


def test_the_evidence_is_still_served(client: TestClient) -> None:
    # `solo_evidencia` no oculta la fuente: es lo que permite juzgar sin que
    # nadie decida por el revisor.
    value = client.get("/records/rec-1").json()["blocks"][0]["values"][0]
    assert value["provenance"]
    assert value["provenance"][0]["literal_text"]


def test_a_protected_field_never_arrives_preselected() -> None:
    # La comprobación ejecutable de la especificación 9 sobre la pantalla
    # completa, no sobre un campo suelto.
    plans = tuple(
        plan_field_presentation(name, DEFAULT_POLICY)
        for name in ("DESCRIPCION", "ACTIVO", "DOSIS")
    )
    assert_no_protected_preselection(plans)
    assert all(plan.is_protected for plan in plans)


def test_no_field_admits_bulk_confirmation_under_the_default_policy() -> None:
    # 9.3 sólo permite bloque en `proponer_valor` con evidencia visible.
    plans = tuple(
        plan_field_presentation(name, DEFAULT_POLICY) for name in ("DESCRIPCION", "ACTIVO")
    )
    assert select_bulk_confirmable(plans) == ()
