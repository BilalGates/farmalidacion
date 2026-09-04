"""Diagnóstico de qué base está sirviendo realmente el proceso.

Este endpoint existe por una avería concreta: el código nuevo estaba desplegado
y el backend seguía sirviendo datos de demostración desde otra base, sin que
nada en pantalla lo delatase. Las pruebas fijan justo eso: que el modo
declarado y el contenido almacenado se publican por separado y pueden
contradecirse.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.data_origin import DEMO_SOURCE_TYPE
from pharma_validator_api.main import create_app
from pharma_validator_api.models import (
    Base,
    DocumentRecordLink,
    SourceDocument,
    SourceDocumentVersion,
    TargetRecord,
)

NOW = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)


def _database(tmp_path: Path, name: str) -> str:
    url = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def _seed(url: str, *, real: int, demo: int) -> None:
    """Crea `real` registros importados y `demo` registros de demostración.

    El origen no se marca en el registro: se deriva del `source_type` del
    documento que lo enlaza, igual que en producción. Sembrarlo de otra forma
    probaría un mecanismo que no existe.
    """
    engine = create_engine(url)
    with Session(engine) as session:
        demo_document = SourceDocument(
            id="doc-demo", source_type=DEMO_SOURCE_TYPE, name="Conjunto DEMO"
        )
        demo_version = SourceDocumentVersion(
            id="ver-demo",
            document_id="doc-demo",
            content_hash="d" * 64,
            source_locator="showcase-demo.json",
            acquired_at=NOW,
        )
        session.add_all([demo_document, demo_version])

        for index in range(real):
            session.add(
                TargetRecord(id=f"real-{index}", entity_type="medication")
            )
        for index in range(demo):
            record_id = f"demo-{index}"
            session.add(TargetRecord(id=record_id, entity_type="medication"))
            session.add(
                DocumentRecordLink(
                    id=f"link-{record_id}",
                    document_version_id="ver-demo",
                    target_record_id=record_id,
                    link_type="master_baseline",
                )
            )
        session.commit()
    engine.dispose()


def test_real_mode_reports_stored_real_records(tmp_path: Path) -> None:
    url = _database(tmp_path, "real.db")
    _seed(url, real=3, demo=0)
    client = TestClient(create_app(Settings(env="test", data_mode="real", database_url=url)))

    payload = client.get("/database-info").json()

    assert payload["mode"] == "real"
    assert payload["database"] == "real"
    assert payload["backend"] == "sqlite"
    assert payload["records_total"] == 3
    assert payload["records_real"] == 3
    assert payload["records_demo"] == 0
    assert payload["consistent"] is True


def test_demo_mode_reports_stored_demo_records(tmp_path: Path) -> None:
    url = _database(tmp_path, "demo.db")
    _seed(url, real=0, demo=5)
    client = TestClient(create_app(Settings(env="test", data_mode="demo", database_url=url)))

    payload = client.get("/database-info").json()

    assert payload["mode"] == "demo"
    assert payload["database"] == "demo"
    assert payload["records_demo"] == 5
    assert payload["records_real"] == 0
    assert payload["consistent"] is True


def test_real_mode_without_imported_records_is_declared_inconsistent(tmp_path: Path) -> None:
    """La avería que motivó el endpoint: base migrada, ingesta no ejecutada.

    Responder «ok» aquí es exactamente lo que dejó al usuario mirando la demo
    sin saberlo, así que se declara inconsistente en lugar de correcto.
    """
    url = _database(tmp_path, "real.db")
    client = TestClient(create_app(Settings(env="test", data_mode="real", database_url=url)))

    payload = client.get("/database-info").json()

    assert payload["mode"] == "real"
    assert payload["records_real"] == 0
    assert payload["consistent"] is False


def test_real_mode_does_not_count_demo_records_as_real(tmp_path: Path) -> None:
    """Un arranque REAL sobre una base contaminada con la demo no se disimula."""
    url = _database(tmp_path, "real.db")
    _seed(url, real=0, demo=6)
    client = TestClient(create_app(Settings(env="test", data_mode="real", database_url=url)))

    payload = client.get("/database-info").json()

    assert payload["records_total"] == 6
    assert payload["records_demo"] == 6
    assert payload["records_real"] == 0
    assert payload["consistent"] is False


def test_diagnostic_never_publishes_the_connection_url(tmp_path: Path) -> None:
    """Sólo se publica el nombre de la base, nunca la ruta que la contiene."""
    url = _database(tmp_path, "real.db")
    client = TestClient(create_app(Settings(env="test", data_mode="real", database_url=url)))

    body = client.get("/database-info").text

    assert str(tmp_path) not in body
    assert "sqlite:///" not in body
