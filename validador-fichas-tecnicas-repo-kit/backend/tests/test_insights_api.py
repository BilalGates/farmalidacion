"""Consulta read-only de los datos reales (vertical de visibilidad).

Las pruebas construyen datos mínimos directamente sobre el modelo físico en
lugar de ejecutar los importadores reales: los maestros pesan decenas de MB y
su importación ya está cubierta por sus propias suites. Lo que aquí se
comprueba es la agregación y, sobre todo, que REAL y DEMO nunca se mezclan.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.config import Settings
from pharma_validator_api.data_origin import DEMO_SOURCE_TYPE, DataOrigin, origin_for_record
from pharma_validator_api.main import create_app
from pharma_validator_api.models import (
    Base,
    BlockInstance,
    DocumentRecordLink,
    FieldValue,
    ImportBatch,
    ImportDiagnostic,
    ImportedSourceSheet,
    QuarantinedSourceRow,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)

NOW = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)


def _database(tmp_path: Path, name: str) -> str:
    url = f"sqlite:///{(tmp_path / name).as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def _seed(url: str) -> None:
    """Crea un registro REAL importado y otro DEMO, con la misma forma.

    Que ambos tengan bloques y valores es deliberado: si el filtro de origen
    fallara, la única diferencia visible sería el conjunto devuelto.
    """
    engine = create_engine(url)
    with Session(engine) as session:
        real_document = SourceDocument(
            id="doc-real", source_type="master_excel", name="Medicamento-cargaMaster.xlsx"
        )
        demo_document = SourceDocument(
            id="doc-demo", source_type=DEMO_SOURCE_TYPE, name="Conjunto DEMO"
        )
        session.add_all([real_document, demo_document])
        session.flush()

        real_version = SourceDocumentVersion(
            id="ver-real",
            document_id="doc-real",
            content_hash="a" * 64,
            source_version="2026-06-25",
            source_locator="Medicamento-cargaMaster.xlsx",
            acquired_at=NOW,
        )
        demo_version = SourceDocumentVersion(
            id="ver-demo",
            document_id="doc-demo",
            content_hash="b" * 64,
            source_version="demo-v1",
            source_locator="demo://maestro",
            acquired_at=NOW,
        )
        session.add_all([real_version, demo_version])
        session.flush()

        session.add(
            ImportBatch(
                id="batch-real",
                source_system="master_excel",
                source_locator="Medicamento-cargaMaster.xlsx",
                source_version="2026-06-25",
                content_hash="a" * 64,
                importer_name="medication_master",
                importer_version="1.0.0",
                status="completed",
                created_at=NOW,
                completed_at=NOW,
                source_document_version_id="ver-real",
            )
        )
        session.flush()
        session.add_all(
            [
                ImportedSourceSheet(
                    id="sheet-1",
                    import_batch_id="batch-real",
                    sheet_name="General",
                    sheet_ordinal=1,
                    header_row_number=1,
                    header_payload="{}",
                    data_row_count=7,
                    material_value_count=14,
                ),
                ImportDiagnostic(
                    id="diag-1",
                    import_batch_id="batch-real",
                    diagnostic_key="k1",
                    severity="error",
                    code="ORPHAN_PARENT",
                    source_locator="General!5",
                    message="Sin padre.",
                    details_literal=None,
                    occurrence_count=2,
                    created_at=NOW,
                ),
                QuarantinedSourceRow(
                    id="quar-1",
                    import_batch_id="batch-real",
                    quarantine_key="q1",
                    source_locator="General!9",
                    reason_code="MISSING_PARENT",
                    reason="No existe padre.",
                    raw_payload="{}",
                    payload_hash="c" * 64,
                    created_at=NOW,
                ),
            ]
        )

        for record_id, version_id, name in (
            ("rec-real", "ver-real", "OMEPRAZOL 20 MG"),
            ("rec-demo", "ver-demo", "DEMO OMEPRAZOL"),
        ):
            session.add(TargetRecord(id=record_id, entity_type="medication"))
            session.flush()
            session.add(
                DocumentRecordLink(
                    id=f"link-{record_id}",
                    document_version_id=version_id,
                    target_record_id=record_id,
                    link_type="master_baseline",
                )
            )
            fragment_id = f"frag-{record_id}"
            session.add(
                SourceFragment(
                    id=fragment_id,
                    document_version_id=version_id,
                    locator_type="excel_row",
                    locator='{"row":2,"sheet":"General"}',
                    literal_text=name,
                )
            )
            session.flush()
            block_id = f"block-{record_id}"
            session.add(
                BlockInstance(
                    id=block_id,
                    target_record_id=record_id,
                    block_type="medication_general",
                    ordinal=1,
                    source_fragment_id=fragment_id,
                )
            )
            session.flush()
            value_id = f"value-{record_id}"
            session.add(
                FieldValue(
                    id=value_id,
                    block_instance_id=block_id,
                    field_name="ME_DESCRIPCION",
                    literal_value=name,
                    observed_type="text",
                    logical_state="valued",
                )
            )
            session.flush()
            session.add(
                ValueProvenance(
                    id=f"prov-{record_id}",
                    field_value_id=value_id,
                    source_fragment_id=fragment_id,
                    provenance_role="master_baseline",
                )
            )
        session.commit()
    engine.dispose()


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    url = _database(tmp_path, "insights.db")
    _seed(url)
    settings = Settings(env="test", database_url=url)
    return TestClient(create_app(settings))


def test_dashboard_counts_come_from_stored_data(client: TestClient) -> None:
    payload = client.get("/insights/dashboard").json()
    metrics = {item["key"]: item["value"] for item in payload["metrics"]}
    # Un registro real y uno DEMO: la cifra de negocio no incluye la demostración.
    assert metrics["real_records"] == 1
    assert metrics["demo_records"] == 1
    assert metrics["medications"] == 1
    assert metrics["batches"] == 1
    assert metrics["quarantined"] == 1
    assert metrics["diagnostics"] == 1
    assert payload["empty"] is False
    assert payload["last_import_at"] is not None


def test_dashboard_reports_empty_system_without_inventing_numbers(tmp_path: Path) -> None:
    url = _database(tmp_path, "vacio.db")
    client = TestClient(create_app(Settings(env="test", database_url=url)))
    payload = client.get("/insights/dashboard").json()
    assert payload["empty"] is True
    assert all(item["value"] == 0 for item in payload["metrics"])
    assert payload["last_import_at"] is None
    # El estado se deriva de la ausencia de datos, no de una constante.
    assert {item["status"] for item in payload["pipeline"]} == {"pendiente"}


def test_pipeline_marks_master_available_when_records_exist(client: TestClient) -> None:
    stages = {item["key"]: item for item in client.get("/insights/dashboard").json()["pipeline"]}
    assert stages["maestros"]["status"] == "disponible"
    # CIMA no está enlazado: se declara pendiente en lugar de suponerlo.
    assert stages["cima"]["status"] == "pendiente"


def test_sources_expose_version_hash_and_incidents(client: TestClient) -> None:
    payload = client.get("/insights/sources").json()
    by_name = {item["source_type"]: item for item in payload["items"]}
    real = by_name["master_excel"]
    # El lote terminó correctamente: la fuente está disponible aunque tenga
    # incidencias, y éstas se cuentan aparte en lugar de degradar el estado.
    assert real["status"] == "disponible"
    assert real["diagnostics"] == 1
    assert real["latest_content_hash"] == "a" * 64
    assert real["latest_version"] == "2026-06-25"
    assert real["records"] == 1
    assert real["quarantined_rows"] == 1
    assert DEMO_SOURCE_TYPE in by_name


def test_source_detail_lists_sheets(client: TestClient) -> None:
    payload = client.get("/insights/sources/doc-real").json()
    assert [sheet["sheet_name"] for sheet in payload["sheets"]] == ["General"]
    assert payload["sheets"][0]["data_row_count"] == 7
    assert payload["batch_ids"] == ["batch-real"]


def test_unknown_source_returns_404(client: TestClient) -> None:
    assert client.get("/insights/sources/no-existe").status_code == 404


def test_imports_report_batch_counters(client: TestClient) -> None:
    payload = client.get("/insights/imports").json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["status"] == "completed"
    assert item["content_hash"] == "a" * 64
    assert item["processed_rows"] == 7
    assert item["quarantined_rows"] == 1
    assert item["errors"] == 1


def test_import_detail_lists_incidents(client: TestClient) -> None:
    payload = client.get("/insights/imports/batch-real").json()
    assert payload["incidents"][0]["code"] == "ORPHAN_PARENT"
    assert payload["incidents"][0]["occurrence_count"] == 2
    assert client.get("/insights/imports/desconocido").status_code == 404


def test_records_default_to_real_and_never_include_demo(client: TestClient) -> None:
    payload = client.get("/insights/records").json()
    assert payload["total"] == 1
    assert [item["id"] for item in payload["items"]] == ["rec-real"]
    assert payload["items"][0]["origin"] == "real"
    assert payload["items"][0]["display_name"] == "OMEPRAZOL 20 MG"


def test_records_demo_view_is_explicit_and_separate(client: TestClient) -> None:
    payload = client.get("/insights/records", params={"origin": "demo"}).json()
    assert [item["id"] for item in payload["items"]] == ["rec-demo"]
    assert payload["items"][0]["origin"] == "demo"


def test_record_search_matches_stored_literals(client: TestClient) -> None:
    found = client.get("/insights/records", params={"q": "omeprazol"}).json()
    assert found["total"] == 1
    missing = client.get("/insights/records", params={"q": "inexistente"}).json()
    assert missing["total"] == 0
    assert missing["items"] == []


def test_record_pagination_reports_total_beyond_page(client: TestClient) -> None:
    payload = client.get("/insights/records", params={"limit": 1, "offset": 1}).json()
    assert payload["total"] == 1
    assert payload["items"] == []


def test_record_detail_exposes_provenance_of_each_value(client: TestClient) -> None:
    payload = client.get("/insights/records/rec-real").json()
    assert payload["origin"] == "real"
    value = payload["blocks"][0]["values"][0]
    assert value["literal_value"] == "OMEPRAZOL 20 MG"
    provenance = value["provenance"][0]
    assert provenance["source_system"] == "master_excel"
    assert provenance["source_version"] == "2026-06-25"
    assert provenance["content_hash"] == "a" * 64
    assert provenance["import_batch_id"] == "batch-real"
    assert provenance["locator"] == '{"row":2,"sheet":"General"}'


def test_record_detail_declares_cima_link_as_pending(client: TestClient) -> None:
    payload = client.get("/insights/records/rec-real").json()
    sources = {item["key"]: item for item in payload["sources"]}
    assert sources["maestro"]["status"] == "disponible"
    # No se insinúa una asociación Maestro↔CIMA que el modelo no almacena.
    assert sources["cima"]["status"] == "pendiente"
    assert "pendiente" in sources["cima"]["detail"].lower()


def test_unknown_record_returns_404(client: TestClient) -> None:
    assert client.get("/insights/records/no-existe").status_code == 404


def test_origin_helper_treats_unlinked_record_as_real(tmp_path: Path) -> None:
    """Un registro sin enlace documental no es de demostración.

    Clasificarlo como DEMO lo ocultaría del listado real sin que nada lo
    explicase, que es justo el fallo que esta vertical debe evitar.
    """
    url = _database(tmp_path, "huerfano.db")
    engine = create_engine(url)
    with Session(engine) as session:
        session.add(TargetRecord(id="suelto", entity_type="medication"))
        session.commit()
        assert origin_for_record(session, "suelto") is DataOrigin.REAL
    engine.dispose()
