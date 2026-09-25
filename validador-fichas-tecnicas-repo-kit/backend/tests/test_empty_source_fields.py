import hashlib
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient

from pharma_validator_api.active_ingredient_importer import SOURCE_FILENAME
from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.master_workbook_export import export_master_workbook
from pharma_validator_api.models import (
    BlockInstance,
    FieldMaintenanceRevision,
    FieldValue,
    ImportBatch,
    ImportedSourceSheet,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
)


def seed_row(session, source_hash: str = "a" * 64) -> None:
    session.add(SourceDocument(id="source", source_type="master_excel", name=SOURCE_FILENAME))
    session.flush()
    session.add(
        SourceDocumentVersion(
            id="version",
            document_id="source",
            content_hash=source_hash,
            source_version="v1",
            source_locator=SOURCE_FILENAME,
            acquired_at=datetime.now(UTC),
        )
    )
    session.flush()
    session.add(
        ImportBatch(
            id="batch",
            source_system="master_excel",
            source_locator=SOURCE_FILENAME,
            source_version="v1",
            content_hash=source_hash,
            importer_name="test",
            importer_version="1",
            status="completed",
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            source_document_version_id="version",
        )
    )
    session.flush()
    session.add(
        ImportedSourceSheet(
            id="sheet",
            import_batch_id="batch",
            sheet_name="General",
            sheet_ordinal=1,
            header_row_number=1,
            header_payload='[{"column":1,"literal_value":"IDEXTERNO"},{"column":2,"literal_value":"DESCRIPCION"}]',
            data_row_count=1,
            material_value_count=1,
        )
    )
    session.add(TargetRecord(id="record", entity_type="active_ingredient"))
    session.add(
        SourceFragment(
            id="fragment",
            document_version_id="version",
            locator_type="excel_row",
            locator='{"sheet":"General","row":2}',
            literal_text='[{"column":1,"literal_value":"123"}]',
        )
    )
    session.flush()
    session.add(
        BlockInstance(
            id="block",
            target_record_id="record",
            block_type="active_ingredient_general",
            ordinal=1,
            source_fragment_id="fragment",
        )
    )
    session.flush()
    session.add(
        FieldValue(
            id="existing",
            block_instance_id="block",
            field_name="IDEXTERNO",
            source_column_index=1,
            literal_value="123",
            observed_type="text",
            logical_state="valued",
        )
    )
    session.commit()


def test_empty_source_cell_is_created_with_provenance_and_revision(scratch_db_url: str) -> None:
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
        seed_row(session)
    endpoint = "/records/record/blocks/block"
    assert api.get(f"{endpoint}/empty-source-columns").json() == [
        {"source_column_index": 2, "field_name": "DESCRIPCION"}
    ]
    payload = {
        "source_column_index": 2,
        "value": "Valor completado",
        "actor_id": "ana",
        "reason": "Completar celda vacía",
    }
    assert (
        api.post(
            f"{endpoint}/empty-source-values", json={**payload, "source_column_index": 1}
        ).status_code
        == 409
    )
    assert (
        api.post(
            f"{endpoint}/empty-source-values", json={**payload, "source_column_index": 9}
        ).status_code
        == 422
    )
    created = api.post(f"{endpoint}/empty-source-values", json=payload)
    assert created.status_code == 201, created.json()
    assert created.json()["field_name"] == "DESCRIPCION"
    assert api.get(f"{endpoint}/empty-source-columns").json() == []
    assert api.post(f"{endpoint}/empty-source-values", json=payload).status_code == 409
    fields = api.get("/records/record").json()["blocks"][0]["values"]
    new_field = next(item for item in fields if item["source_column_index"] == 2)
    assert new_field["literal_value"] is None
    assert new_field["maintained_value"] == "Valor completado"
    assert new_field["maintenance_history"][0]["before_value"] is None
    assert new_field["provenance"][0]["source_fragment_id"] == "fragment"
    with api.app.state.session_factory() as session:
        assert (
            session.query(FieldMaintenanceRevision)
            .filter_by(field_value_id=new_field["id"])
            .count()
            == 1
        )


def test_empty_source_cell_requires_actor_and_reason(scratch_db_url: str) -> None:
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
        seed_row(session)
    endpoint = "/records/record/blocks/block/empty-source-values"
    payload = {"source_column_index": 2, "value": "Nuevo", "actor_id": "ana", "reason": "Motivo"}
    assert api.post(endpoint, json={**payload, "reason": "  "}).status_code == 400
    assert api.post(endpoint, json={**payload, "actor_id": "nadie"}).status_code == 400
    assert api.get("/records/record/blocks/other/empty-source-columns").status_code == 404
    assert api.get("/records/record/blocks/block/empty-source-columns").json() == [
        {"source_column_index": 2, "field_name": "DESCRIPCION"}
    ]


def test_created_empty_field_reaches_workbook_export(scratch_db_url: str, tmp_path: Path) -> None:
    source = tmp_path / SOURCE_FILENAME
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'
            '<sheet name="General" sheetId="1" r:id="rId1"/>'
            '</sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{pkg}">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{ns}"><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>IDEXTERNO</t></is></c>'
            '<c r="B1" t="inlineStr"><is><t>DESCRIPCION</t></is></c></row>'
            '<row r="2"><c r="A2"><v>123</v></c></row>'
            '</sheetData></worksheet>',
        )
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
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
        seed_row(session, source_hash)
    response = api.post(
        "/records/record/blocks/block/empty-source-values",
        json={
            "source_column_index": 2,
            "value": "Nuevo valor",
            "actor_id": "ana",
            "reason": "Completar desde expediente",
        },
    )
    assert response.status_code == 201, response.json()
    with api.app.state.session_factory() as session:
        result = export_master_workbook(session, source, tmp_path / "out.xlsx")
    assert result.changed_cells == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    with zipfile.ZipFile(result.output) as archive:
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    cell = sheet.find(f".//{{{ns}}}c[@r='B2']/{{{ns}}}is/{{{ns}}}t")
    assert cell is not None and cell.text == "Nuevo valor"
