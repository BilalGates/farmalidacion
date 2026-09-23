#!/usr/bin/env python3
# mypy: disable-error-code=import-untyped
"""Audit real master-import coverage in an isolated in-memory database.

This checks source-row payloads and per-cell values stored by the production
importers. It does not decide pharmaceutical identity or generate exports.
"""

from __future__ import annotations

import json
import sys
from itertools import groupby
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from scripts.verify_reference_files import EXPECTED, sha256

BACKEND_SOURCE = Path(__file__).resolve().parents[1] / "backend" / "src"
sys.path.insert(0, str(BACKEND_SOURCE))
from pharma_validator_api import (
    active_ingredient_importer as active_importer,
)
from pharma_validator_api import (
    medication_importer,
    specialty_importer,
)
from pharma_validator_api.catalog_importer import import_catalog
from pharma_validator_api.master_ingestion import ingest_masters
from pharma_validator_api.models import (
    Base,
    BlockInstance,
    FieldValue,
    ImportBatch,
    ImportedSourceSheet,
    QuarantinedSourceRow,
    SourceFragment,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_FILE = "Catalogo_campos_clinicos_medicamentos.xlsx"
WORKBOOKS = (
    "PrincipioActivoCargaMaster-22062026.xlsx",
    "Medicamento-cargaMaster25062026.xlsx",
    "Especialidades-CargaMaster190626.xlsx",
)


class ImportCoverageError(RuntimeError):
    pass


def _source_payloads(
    filename: str, source: Path
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if filename == WORKBOOKS[0]:
        importer = active_importer
    elif filename == WORKBOOKS[1]:
        importer = medication_importer
    elif filename == WORKBOOKS[2]:
        importer = specialty_importer
    else:
        raise ImportCoverageError(f"Unrecognized source workbook: {filename}")

    rows: dict[str, str] = {}
    sheets: list[dict[str, Any]] = []
    for (
        ordinal,
        sheet_name,
        _block_type,
        header_row,
        headers,
        header_cells,
        data_rows,
    ) in importer._parse_workbook(source):
        sheet_values = 0
        for row_number, cells in data_rows:
            if not cells:
                continue
            locator = f"{sheet_name}!{row_number}"
            payload = importer._payload(headers, cells)
            if locator in rows:
                raise ImportCoverageError(f"Duplicate parsed source locator: {locator}")
            rows[locator] = payload
            sheet_values += len(json.loads(payload))
        sheets.append(
            {
                "sheet_name": sheet_name,
                "sheet_ordinal": ordinal,
                "header_row_number": header_row,
                "header_payload": importer._payload(headers, header_cells),
                "data_row_count": len(data_rows),
                "material_value_count": sheet_values,
            }
        )
    return rows, sheets


def _stored_rows(
    session: Session, batch: ImportBatch
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    if batch.source_document_version_id is None:
        raise ImportCoverageError(f"Import batch has no source version: {batch.id}")
    fragments = session.scalars(
        select(SourceFragment)
        .where(SourceFragment.document_version_id == batch.source_document_version_id)
        .order_by(SourceFragment.id)
    ).all()
    stored_rows: dict[str, str] = {}
    fragment_ids: dict[str, str] = {}
    for fragment in fragments:
        locator_data = json.loads(fragment.locator)
        locator = f"{locator_data['sheet']}!{locator_data['row']}"
        if locator in stored_rows:
            raise ImportCoverageError(f"Duplicate stored source fragment: {locator}")
        stored_rows[locator] = fragment.literal_text or ""
        fragment_ids[str(fragment.id)] = locator

    quarantined: dict[str, str] = {}
    for item in session.scalars(
        select(QuarantinedSourceRow)
        .where(QuarantinedSourceRow.import_batch_id == batch.id)
        .order_by(QuarantinedSourceRow.source_locator)
    ):
        if item.source_locator in quarantined:
            raise ImportCoverageError(
                f"Duplicate quarantined source row: {item.source_locator}"
            )
        quarantined[item.source_locator] = item.raw_payload
    return stored_rows, fragment_ids, quarantined


def _audit_workbook(session: Session, source: Path) -> dict[str, Any]:
    filename = source.name
    batch = session.scalar(
        select(ImportBatch).where(
            ImportBatch.source_locator == filename,
            ImportBatch.source_system == "master_excel",
        )
    )
    if batch is None or batch.status != "completed":
        raise ImportCoverageError(f"No completed batch found for {filename}")

    expected_rows, expected_sheets = _source_payloads(filename, source)
    imported_rows, fragment_ids, quarantined_rows = _stored_rows(session, batch)
    fragment_ids_by_locator = {
        locator: fragment_id for fragment_id, locator in fragment_ids.items()
    }
    sheets = session.scalars(
        select(ImportedSourceSheet)
        .where(ImportedSourceSheet.import_batch_id == batch.id)
        .order_by(ImportedSourceSheet.sheet_ordinal)
    ).all()
    actual_sheets = [
        {
            "sheet_name": item.sheet_name,
            "sheet_ordinal": item.sheet_ordinal,
            "header_row_number": item.header_row_number,
            "header_payload": item.header_payload,
            "data_row_count": item.data_row_count,
            "material_value_count": item.material_value_count,
        }
        for item in sheets
    ]
    if actual_sheets != expected_sheets:
        raise ImportCoverageError(f"Worksheet inventory differs for {filename}")

    overlap = set(imported_rows) & set(quarantined_rows)
    recovered_rows = imported_rows | quarantined_rows
    if overlap or set(recovered_rows) != set(expected_rows):
        raise ImportCoverageError(
            f"Source row coverage differs for {filename}: "
            f"missing={len(set(expected_rows) - set(recovered_rows))}, "
            f"extra={len(set(recovered_rows) - set(expected_rows))}, overlap={len(overlap)}"
        )
    for locator, payload in expected_rows.items():
        stored_payload = imported_rows.get(locator, quarantined_rows.get(locator))
        if stored_payload != payload:
            raise ImportCoverageError(
                f"Literal row payload differs at {filename}:{locator}"
            )

    imported_field_count = 0
    field_rows = session.execute(
        select(
            BlockInstance.source_fragment_id,
            FieldValue.source_column_index,
            FieldValue.literal_value,
            FieldValue.observed_type,
        )
        .join(BlockInstance, BlockInstance.id == FieldValue.block_instance_id)
        .join(SourceFragment, SourceFragment.id == BlockInstance.source_fragment_id)
        .where(SourceFragment.document_version_id == batch.source_document_version_id)
        .order_by(BlockInstance.source_fragment_id, FieldValue.source_column_index)
    )
    seen_field_fragments: set[str] = set()
    for fragment_id, records in groupby(field_rows, key=lambda row: str(row[0])):
        stored_locator = fragment_ids.get(fragment_id)
        if stored_locator is None:
            raise ImportCoverageError(
                f"FieldValue points to unknown source fragment {fragment_id}"
            )
        if stored_locator in quarantined_rows:
            raise ImportCoverageError(
                f"Quarantined row has editable fields: {filename}:{stored_locator}"
            )
        expected = [
            {
                "column": item["column"],
                "literal_value": item["literal_value"],
                "observed_type": item["observed_type"],
            }
            for item in json.loads(expected_rows[stored_locator])
        ]
        stored = []
        for _fragment, column, value, observed_type in records:
            if column is None:
                raise ImportCoverageError(
                    "Imported FieldValue has no source column coordinate"
                )
            stored.append(
                {
                    "column": int(column),
                    "literal_value": value,
                    "observed_type": observed_type,
                }
            )
        if stored != expected:
            raise ImportCoverageError(
                f"Field values differ at {filename}:{stored_locator}"
            )
        seen_field_fragments.add(fragment_id)
        imported_field_count += len(stored)

    for source_locator in imported_rows:
        source_fragment_id = fragment_ids_by_locator.get(source_locator)
        if source_fragment_id is None:
            raise ImportCoverageError(
                f"Imported row has no fragment id: {source_locator}"
            )
        if (
            source_locator not in quarantined_rows
            and json.loads(expected_rows[source_locator])
            and source_fragment_id not in seen_field_fragments
        ):
            raise ImportCoverageError(
                f"Editable fields missing for {filename}:{source_locator}"
            )

    quarantined_value_count = sum(
        len(json.loads(payload)) for payload in quarantined_rows.values()
    )
    source_value_count = sum(sheet["material_value_count"] for sheet in expected_sheets)
    if imported_field_count + quarantined_value_count != source_value_count:
        raise ImportCoverageError(f"Material field coverage differs for {filename}")

    formulas = sum(
        item["formula"] is not None
        for payload in expected_rows.values()
        for item in json.loads(payload)
    )
    return {
        "filename": filename,
        "sha256_before": sha256(source),
        "sha256_after": sha256(source),
        "status": batch.status,
        "sheets": len(expected_sheets),
        "source_rows": len(expected_rows),
        "rows_with_editable_fields": len(imported_rows),
        "rows_in_quarantine": len(quarantined_rows),
        "source_material_values": source_value_count,
        "values_stored_as_fields": imported_field_count,
        "values_only_in_quarantine_payload": quarantined_value_count,
        "formulas_in_source_rows": formulas,
        "quarantine_reasons": dict(
            session.execute(
                select(QuarantinedSourceRow.reason_code, func.count())
                .where(QuarantinedSourceRow.import_batch_id == batch.id)
                .group_by(QuarantinedSourceRow.reason_code)
            ).all()
        ),
    }


def audit_importers(catalog: Path, master_directory: Path) -> dict[str, Any]:
    if sha256(catalog) != EXPECTED[CATALOG_FILE]:
        raise ImportCoverageError("Field-catalog workbook hash changed")
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            catalog_result = import_catalog(session, catalog)
            session.commit()
            master_result = ingest_masters(
                session,
                master_directory,
                only=("active_ingredients", "medications", "specialties"),
            )
            if not master_result.ok:
                raise ImportCoverageError("At least one source master failed to import")
            results = [
                _audit_workbook(session, master_directory / filename)
                for filename in WORKBOOKS
            ]
            return {
                "status": "pass",
                "database": "sqlite-in-memory",
                "catalog_field_definitions": catalog_result.imported_fields,
                "catalog_status": catalog_result.status,
                "master_imports": results,
                "total_source_rows": sum(item["source_rows"] for item in results),
                "total_quarantined_rows": sum(
                    item["rows_in_quarantine"] for item in results
                ),
                "total_source_material_values": sum(
                    item["source_material_values"] for item in results
                ),
                "total_values_in_quarantine": sum(
                    item["values_only_in_quarantine_payload"] for item in results
                ),
                "roundtrip_exported": False,
                "scope": "source-row and literal-field coverage from production importers only",
            }
    finally:
        engine.dispose()


def main() -> int:
    base = ROOT.parent / "Catalogo_campos_clinicos_medicamentos"
    master_directory = base / "base"
    evidence = audit_importers(base / CATALOG_FILE, master_directory)
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
