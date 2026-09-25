#!/usr/bin/env python3
# mypy: disable-error-code=import-untyped
"""Verify a lossless, unedited export of the three real master workbooks."""

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
                selected_cells: dict[str, tuple[str, str, str]] = {}
                for name in MASTER_WORKBOOKS:
                    selected = session.execute(
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
                        .limit(1)
                    ).first()
                    if selected is None:
                        raise AssertionError(f"Sin campo editable importado: {name}")
                    field, locator = selected
                    coordinates = json.loads(locator)
                    sheet = str(coordinates["sheet"])
                    reference = _reference(int(field.source_column_index), int(coordinates["row"]))
                    marker = f"PRUEBA EXPORTACION {len(selected_cells) + 1}"
                    selected_cells[name] = (sheet, reference, marker)
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
                session.flush()
                corrected = export_master_workbooks(
                    session, source_directory, Path(temporary) / "corrected"
                )
                for item in corrected:
                    sheet, reference, marker = selected_cells[item.filename]
                    if item.changed_cells != 1:
                        raise AssertionError(f"Número de cambios inesperado: {item.filename}")
                    with zipfile.ZipFile(source_directory / item.filename) as source_zip, zipfile.ZipFile(item.output) as output_zip:
                        sheet_path = _workbook_sheets(source_zip)[sheet]
                        if source_zip.namelist() != output_zip.namelist():
                            raise AssertionError(f"Partes XLSX diferentes: {item.filename}")
                        changed_parts = {
                            name
                            for name in source_zip.namelist()
                            if source_zip.read(name) != output_zip.read(name)
                        }
                        if sheet_path not in changed_parts or changed_parts - {
                            sheet_path, "xl/sharedStrings.xml"
                        }:
                            raise AssertionError(f"Partes inesperadas tras corregir {item.filename}: {changed_parts}")
                        _, _, shared = _shared_strings(output_zip)
                        xml = ET.fromstring(output_zip.read(sheet_path))
                        cell = xml.find(f".//{{{MAIN_NS}}}c[@r='{reference}']")
                        if _cell_value(cell, shared) != marker:
                            raise AssertionError(f"Corrección no encontrada: {item.filename}:{reference}")
                    match = next(row for row in result if row["filename"] == item.filename)
                    match["corrected_cell"] = f"{sheet}!{reference}"
                    match["changed_parts"] = sorted(changed_parts)
                if {name: sha256(source_directory / name) for name in MASTER_WORKBOOKS} != originals:
                    raise AssertionError("Cambió el hash de un maestro original.")
                return {"status": "pass", "workbooks": result, "original_sha256": originals}
        finally:
            engine.dispose()


if __name__ == "__main__":
    directory = ROOT.parent / "Catalogo_campos_clinicos_medicamentos" / "base"
    print(json.dumps(verify(directory), ensure_ascii=False, indent=2))
