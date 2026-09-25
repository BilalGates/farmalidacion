from __future__ import annotations

import hashlib
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_validator_api.active_ingredient_importer import SOURCE_FILENAME
from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app
from pharma_validator_api.master_workbook_export import (
    MASTER_WORKBOOKS,
    MasterWorkbookExportError,
    export_master_workbook,
    export_master_workbooks,
)
from pharma_validator_api.models import (
    Base,
    BlockInstance,
    FieldMaintenanceRevision,
    FieldValue,
    ImportBatch,
    QuarantinedFieldMaintenanceRevision,
    QuarantinedSourceRow,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
)

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def make_xlsx(path: Path) -> None:
    workbook = f'''<?xml version="1.0" encoding="UTF-8"?>
    <workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>
      <sheet name="Hoja1" sheetId="1" r:id="rId1"/>
    </sheets></workbook>'''
    relationships = f'''<?xml version="1.0" encoding="UTF-8"?>
    <Relationships xmlns="{PKG}">
      <Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/>
    </Relationships>'''
    shared = f'''<?xml version="1.0" encoding="UTF-8"?>
    <sst xmlns="{MAIN}" count="1" uniqueCount="1"><si><t>Anterior</t></si></sst>'''
    sheet = f'''<?xml version="1.0" encoding="UTF-8"?>
    <worksheet xmlns="{MAIN}"><sheetData><row r="1">
      <c r="A1" t="s"><v>0</v></c><c r="B1"><v>3</v></c>
    </row><row r="2"><c r="A2" t="s"><v>0</v></c></row>
    </sheetData></worksheet>'''
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/sharedStrings.xml", shared)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        archive.writestr("custom/preserved.bin", b"preserve me")


def seed_export(session: Session, source: Path, original_hash: str, suffix: str = "") -> None:
    def identifier(name: str) -> str:
        return f"{name}-{suffix}" if suffix else name

    document = SourceDocument(id=identifier("doc"), source_type="master_excel", name=source.name)
    version = SourceDocumentVersion(
        id=identifier("version"),
        document_id=document.id,
        content_hash=original_hash,
        source_version="v1",
        source_locator=source.name,
        acquired_at=datetime.now(UTC),
    )
    batch = ImportBatch(
        id=identifier("batch"),
        source_system="AEMPS",
        source_locator=source.name,
        source_version="v1",
        content_hash=original_hash,
        importer_name="test",
        importer_version="1",
        status="completed",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        source_document_version_id=version.id,
    )
    record = TargetRecord(id=identifier("record"), entity_type="active_ingredient")
    fragment = SourceFragment(
        id=identifier("fragment"),
        document_version_id=version.id,
        locator_type="excel_row",
        locator='{"sheet":"Hoja1","row":1}',
        literal_text="Anterior",
    )
    block = BlockInstance(
        id=identifier("block"),
        target_record_id=record.id,
        block_type="active_ingredient_general",
        ordinal=1,
        source_fragment_id=fragment.id,
    )
    field = FieldValue(
        id=identifier("field"),
        block_instance_id=block.id,
        field_name="DESCRIPCION",
        source_column_index=1,
        literal_value="Anterior",
        observed_type="texto",
        logical_state="valued",
    )
    session.add_all([document, version, batch, record, fragment, block, field])
    session.flush()
    session.add(
        FieldMaintenanceRevision(
            id=identifier("revision"),
            field_value_id=field.id,
            sequence=1,
            before_value="Anterior",
            after_value="Corregido",
            actor_id="ana",
            actor_assurance="farmaceutico",
            reason="Corrección de prueba",
            recorded_at=datetime.now(UTC),
        )
    )


def test_export_patches_only_maintained_source_cell_and_preserves_package(
    tmp_path: Path,
) -> None:
    source = tmp_path / SOURCE_FILENAME
    destination = tmp_path / "salida" / SOURCE_FILENAME
    make_xlsx(source)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_export(session, source, original_hash)
        session.commit()
        result = export_master_workbook(session, source, destination)

    assert result.changed_cells == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    with zipfile.ZipFile(destination) as archive:
        assert archive.read("custom/preserved.bin") == b"preserve me"
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = ["".join(item.text or "" for item in node.iter(f"{{{MAIN}}}t")) for node in shared]
    cell = sheet.find(f".//{{{MAIN}}}c[@r='A1']")
    value = cell.find(f"{{{MAIN}}}v")
    assert value is not None and strings[int(value.text or "-1")] == "Corregido"
    # The numeric neighbor and unrelated ZIP package member remain unchanged.
    assert sheet.find(f".//{{{MAIN}}}c[@r='B1']/{{{MAIN}}}v").text == "3"


def test_export_fails_closed_when_source_hash_is_not_current(tmp_path: Path) -> None:
    source = tmp_path / SOURCE_FILENAME
    make_xlsx(source)
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session, pytest.raises(MasterWorkbookExportError):
        export_master_workbook(session, source, tmp_path / "out.xlsx")


def test_export_creates_a_previously_absent_cell_without_mutating_source(tmp_path: Path) -> None:
    source = tmp_path / SOURCE_FILENAME
    destination = tmp_path / "out.xlsx"
    make_xlsx(source)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_export(session, source, original_hash)
        session.add(
            FieldValue(
                id="empty-source-cell",
                block_instance_id="block",
                field_name="EMPTY_COLUMN",
                source_column_index=3,
                literal_value=None,
                observed_type="vacio",
                logical_state="empty",
            )
        )
        session.add(
            FieldMaintenanceRevision(
                id="empty-source-revision",
                field_value_id="empty-source-cell",
                sequence=1,
                before_value=None,
                after_value="Nuevo valor",
                actor_id="ana",
                actor_assurance="farmaceutico",
                reason="Completar celda vacía",
                recorded_at=datetime.now(UTC),
            )
        )
        session.commit()
        result = export_master_workbook(session, source, destination)

    assert result.changed_cells == 2
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    with zipfile.ZipFile(destination) as archive:
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    cell = sheet.find(f".//{{{MAIN}}}c[@r='C1']")
    assert cell is not None and cell.get("t") == "inlineStr"
    assert cell.find(f"{{{MAIN}}}is/{{{MAIN}}}t").text == "Nuevo valor"


def test_quarantined_cell_revision_is_applied_without_changing_its_raw_row(
    tmp_path: Path,
) -> None:
    source = tmp_path / SOURCE_FILENAME
    destination = tmp_path / "out.xlsx"
    make_xlsx(source)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_export(session, source, original_hash)
        row = QuarantinedSourceRow(
            id="quarantined",
            import_batch_id="batch",
            quarantine_key="key",
            source_locator="Hoja1!2",
            reason_code="MISSING_PARENT",
            reason="Parent unavailable",
            raw_payload='[{"column":1,"literal_value":"Anterior"}]',
            payload_hash="0" * 64,
            created_at=datetime.now(UTC),
        )
        revision = QuarantinedFieldMaintenanceRevision(
            id="quarantined-revision",
            quarantined_row_id=row.id,
            source_column_index=1,
            sequence=1,
            before_value="Anterior",
            after_value="Cuarentena corregida",
            actor_id="ana",
            actor_assurance="farmaceutico",
            reason="Corrección de prueba",
            recorded_at=datetime.now(UTC),
        )
        empty_revision = QuarantinedFieldMaintenanceRevision(
            id="quarantined-empty-revision",
            quarantined_row_id=row.id,
            source_column_index=2,
            sequence=1,
            before_value=None,
            after_value="Celda antes vacía",
            actor_id="ana",
            actor_assurance="farmaceutico",
            reason="Completar celda de cuarentena",
            recorded_at=datetime.now(UTC),
        )
        session.add_all([row, revision, empty_revision])
        session.commit()
        result = export_master_workbook(session, source, destination)
        assert session.get(QuarantinedSourceRow, row.id).raw_payload == row.raw_payload
    assert result.changed_cells == 3
    with zipfile.ZipFile(destination) as archive:
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = ["".join(item.text or "" for item in node.iter(f"{{{MAIN}}}t")) for node in shared]
    value = sheet.find(f".//{{{MAIN}}}c[@r='A2']/{{{MAIN}}}v")
    assert value is not None and strings[int(value.text or "-1")] == "Cuarentena corregida"
    empty_cell = sheet.find(f".//{{{MAIN}}}c[@r='B2']/{{{MAIN}}}is/{{{MAIN}}}t")
    assert empty_cell is not None and empty_cell.text == "Celda antes vacía"


def test_three_book_export_publishes_only_a_complete_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_directory = tmp_path / "source"
    source_directory.mkdir()
    destination = tmp_path / "output"
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for index, filename in enumerate(MASTER_WORKBOOKS):
            source = source_directory / filename
            make_xlsx(source)
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            if index < 2:
                seed_export(session, source, source_hash, suffix=str(index))
        session.commit()
        with pytest.raises(MasterWorkbookExportError):
            export_master_workbooks(session, source_directory, destination)
        assert not destination.exists()
        third = source_directory / MASTER_WORKBOOKS[2]
        seed_export(session, third, hashlib.sha256(third.read_bytes()).hexdigest(), suffix="2")
        session.commit()
        original_rename = Path.rename
        attempts = 0

        def transiently_blocked_rename(path: Path, target: Path) -> Path:
            nonlocal attempts
            if path.name == "books" and attempts == 0:
                attempts += 1
                raise PermissionError("Archivo temporalmente bloqueado")
            return original_rename(path, target)

        monkeypatch.setattr(Path, "rename", transiently_blocked_rename)
        results = export_master_workbooks(session, source_directory, destination)
    assert attempts == 1
    assert {result.filename for result in results} == set(MASTER_WORKBOOKS)
    assert all(result.output.is_file() and result.changed_cells == 1 for result in results)


def test_master_export_api_is_disabled_by_default_and_requires_source_directory(
    tmp_path: Path,
) -> None:
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'api.sqlite').as_posix()}", env="test"
    )
    client = TestClient(create_app(settings))
    assert client.post("/master-workbooks/export").status_code == 404

    settings.enable_master_workbook_export = True
    response = client.post("/master-workbooks/export")
    assert response.status_code == 503
    assert "carpeta" in response.json()["detail"]
