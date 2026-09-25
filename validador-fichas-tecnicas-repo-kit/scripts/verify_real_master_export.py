#!/usr/bin/env python3
# mypy: disable-error-code=import-untyped
"""Verify lossless and differential exports of the three real master workbooks."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from pharma_validator_api.catalog_importer import import_catalog
from pharma_validator_api.master_ingestion import ingest_masters
from pharma_validator_api.master_workbook_export import (
    MASTER_WORKBOOKS,
    _cell_value,
    _reference,
    _shared_strings,
    _workbook_sheets,
    export_master_workbooks,
)
from pharma_validator_api.models import (
    Base,
    BlockInstance,
    FieldMaintenanceRevision,
    FieldValue,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
)

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(source_directory: Path) -> dict[str, object]:
    catalog = source_directory.parent / "Catalogo_campos_clinicos_medicamentos.xlsx"
    originals = {name: sha256(source_directory / name) for name in MASTER_WORKBOOKS}
    with tempfile.TemporaryDirectory(prefix="farmalidacion-export-") as temporary:
        engine = create_engine("sqlite://")
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as session:
                import_catalog(session, catalog)
                session.commit()
                ingestion = ingest_masters(
                    session,
                    source_directory,
                    only=("active_ingredients", "medications", "specialties"),
                )
                if not ingestion.ok:
                    raise RuntimeError("No se importaron los tres maestros.")
                exported = export_master_workbooks(
                    session, source_directory, Path(temporary) / "exported"
                )
                result = []
                for item in exported:
                    original = source_directory / item.filename
                    if item.changed_cells != 0:
                        raise AssertionError(f"Se modificaron celdas sin revisiones: {item.filename}")
                    with zipfile.ZipFile(original) as source_zip, zipfile.ZipFile(item.output) as output_zip:
                        if source_zip.namelist() != output_zip.namelist():
                            raise AssertionError(f"Partes XLSX diferentes: {item.filename}")
                        for name in source_zip.namelist():
                            if source_zip.read(name) != output_zip.read(name):
                                raise AssertionError(f"Parte XLSX diferente: {item.filename}:{name}")
                        parts = len(source_zip.namelist())
                    result.append({"filename": item.filename, "parts_identical": parts})
                selected_cells: dict[str, dict[str, tuple[str, str]]] = {}
                for name in MASTER_WORKBOOKS:
                    candidates = session.execute(
                        select(FieldValue, SourceFragment.locator)
                        .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
                        .join(SourceFragment, BlockInstance.source_fragment_id == SourceFragment.id)
                        .join(
                            SourceDocumentVersion,
                            SourceFragment.document_version_id == SourceDocumentVersion.id,
                        )
                        .join(SourceDocument, SourceDocumentVersion.document_id == SourceDocument.id)
                        .where(
                            SourceDocument.name == name,
                            FieldValue.source_column_index.is_not(None),
                        )
                    ).all()
                    if not candidates:
                        raise AssertionError(f"Sin campo editable importado: {name}")
                    selected_cells[name] = {}
                    with zipfile.ZipFile(source_directory / name) as source_zip:
                        sheet_paths = _workbook_sheets(source_zip)
                        _, _, shared = _shared_strings(source_zip)
                        sheet_xml = {
                            sheet: ET.fromstring(source_zip.read(path))
                            for sheet, path in sheet_paths.items()
                        }
                        for field, locator in candidates:
                            coordinates = json.loads(locator)
                            sheet = str(coordinates["sheet"])
                            if sheet in selected_cells[name]:
                                continue
                            reference = _reference(
                                int(field.source_column_index), int(coordinates["row"])
                            )
                            cell = sheet_xml[sheet].find(
                                f".//{{{MAIN_NS}}}c[@r='{reference}']"
                            )
                            if cell is None or cell.find(f"{{{MAIN_NS}}}f") is not None:
                                continue
                            if _cell_value(cell, shared) != field.literal_value:
                                raise AssertionError(f"Literal importado distinto: {name}:{sheet}!{reference}")
                            marker = f"PRUEBA EXPORTACION {len(selected_cells[name]) + 1}"
                            selected_cells[name][sheet] = (reference, marker)
                            session.add(
                                FieldMaintenanceRevision(
                                    field_value_id=field.id,
                                    sequence=1,
                                    before_value=field.literal_value,
                                    after_value=marker,
                                    actor_id="verificacion_temporal",
                                    actor_assurance="tecnico",
                                    reason="Comprobar exportación diferencial en base temporal",
                                    recorded_at=datetime.now(UTC),
                                )
                            )
                    match = next(row for row in result if row["filename"] == name)
                    match["sheets_without_linked_editable_cell"] = sorted(
                        set(sheet_paths) - set(selected_cells[name])
                    )
                session.flush()
                corrected = export_master_workbooks(
                    session, source_directory, Path(temporary) / "corrected"
                )
                for item in corrected:
                    selections = selected_cells[item.filename]
                    if item.changed_cells != len(selections):
                        raise AssertionError(f"Número de cambios inesperado: {item.filename}")
                    with zipfile.ZipFile(source_directory / item.filename) as source_zip, zipfile.ZipFile(item.output) as output_zip:
                        sheet_paths = _workbook_sheets(source_zip)
                        if source_zip.namelist() != output_zip.namelist():
                            raise AssertionError(f"Partes XLSX diferentes: {item.filename}")
                        changed_parts = {
                            name
                            for name in source_zip.namelist()
                            if source_zip.read(name) != output_zip.read(name)
                        }
                        expected_sheets = {sheet_paths[sheet] for sheet in selections}
                        if not expected_sheets <= changed_parts or changed_parts - (
                            expected_sheets | {"xl/sharedStrings.xml"}
                        ):
                            raise AssertionError(f"Partes inesperadas tras corregir {item.filename}: {changed_parts}")
                        _, _, shared = _shared_strings(output_zip)
                        for sheet, (reference, marker) in selections.items():
                            xml = ET.fromstring(output_zip.read(sheet_paths[sheet]))
                            cell = xml.find(f".//{{{MAIN_NS}}}c[@r='{reference}']")
                            if _cell_value(cell, shared) != marker:
                                raise AssertionError(
                                    f"Corrección no encontrada: {item.filename}:{sheet}!{reference}"
                                )
                    match = next(row for row in result if row["filename"] == item.filename)
                    match["corrected_cells"] = [
                        f"{sheet}!{reference}" for sheet, (reference, _) in selections.items()
                    ]
                    match["changed_parts"] = sorted(changed_parts)
                if {name: sha256(source_directory / name) for name in MASTER_WORKBOOKS} != originals:
                    raise AssertionError("Cambió el hash de un maestro original.")
                return {"status": "pass", "workbooks": result, "original_sha256": originals}
        finally:
            engine.dispose()


if __name__ == "__main__":
    directory = ROOT.parent / "Catalogo_campos_clinicos_medicamentos" / "base"
    print(json.dumps(verify(directory), ensure_ascii=False, indent=2))
