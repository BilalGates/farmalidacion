import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast
from xml.etree import ElementTree as ET

from sqlalchemy import Table, func, insert, select
from sqlalchemy.orm import Session

from pharma_validator_api.active_ingredient_importer import (
    _ensure_document_version,
    _payload,
    _stable_uuid,
)
from pharma_validator_api.catalog_importer import (
    Cell,
    _iter_rows,
    _shared_strings,
    _sheet_path,
    _validate_archive,
)
from pharma_validator_api.import_batches import (
    ImportBatchRequest,
    complete_import_batch,
    fail_import_batch,
    get_or_create_import_batch,
    quarantine_source_row,
    record_diagnostic,
)
from pharma_validator_api.models import (
    BlockInstance,
    DocumentRecordLink,
    FieldValue,
    ImportBatch,
    ImportDiagnostic,
    ImportedSourceSheet,
    QuarantinedSourceRow,
    SourceFragment,
    TargetRecord,
    TargetRecordLink,
    ValueProvenance,
)

SOURCE_FILENAME = "Medicamento-cargaMaster25062026.xlsx"
SOURCE_HASH = "4b87aeac96ea220126c090d755fa5bfbaabe7aec304cfccb2e15537bd96cbf1b"
IMPORTER_NAME = "medication_master"
IMPORTER_VERSION = "1.0.0"
SHEETS = (
    ("General", "medication_general"),
    ("Composicion", "medication_composition"),
    ("Indicacion", "medication_indication"),
    ("Frecuencia", "medication_frequency"),
    ("Via", "medication_route"),
    ("Prescripcion", "medication_prescription"),
    ("Links", "medication_link"),
)
BULK_OCCURRENCES = 500

ParsedSheet = tuple[
    int,
    str,
    str,
    int,
    dict[int, str],
    dict[int, Cell],
    list[tuple[int, dict[int, Cell]]],
]


@dataclass(frozen=True)
class MedicationImportResult:
    batch_id: str
    created: bool
    status: str
    sheets: int
    occurrences: int
    values: int
    quarantined_rows: int
    diagnostics: int
    composition_links: int


class MedicationImportError(RuntimeError):
    pass


def _parse_workbook(path: Path) -> list[ParsedSheet]:
    _validate_archive(path)
    parsed: list[ParsedSheet] = []
    with zipfile.ZipFile(path) as archive:
        strings = _shared_strings(archive)
        for ordinal, (sheet_name, block_type) in enumerate(SHEETS, start=1):
            rows = _iter_rows(archive, _sheet_path(archive, sheet_name), strings)
            if not rows:
                raise MedicationImportError(f"La hoja {sheet_name} no contiene cabecera.")
            header_row_number, header_cells = rows[0]
            headers = {column: cell.literal_value for column, cell in header_cells.items()}
            if not headers or any(not header for header in headers.values()):
                raise MedicationImportError(
                    f"La hoja {sheet_name} contiene cabeceras vacías."
                )
            parsed.append(
                (
                    ordinal,
                    sheet_name,
                    block_type,
                    header_row_number,
                    headers,
                    header_cells,
                    rows[1:],
                )
            )
    return parsed


def _active_ingredient_targets(session: Session) -> dict[str, list[str]]:
    rows = session.execute(
        select(FieldValue.literal_value, BlockInstance.target_record_id)
        .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
        .join(TargetRecord, BlockInstance.target_record_id == TargetRecord.id)
        .where(
            TargetRecord.entity_type == "active_ingredient",
            BlockInstance.block_type == "active_ingredient_general",
            FieldValue.field_name == "IDEXTERNO",
        )
    )
    result: defaultdict[str, list[str]] = defaultdict(list)
    for literal, target_id in rows:
        result[literal or ""].append(target_id)
    return dict(result)


def _existing_result(session: Session, batch: ImportBatch) -> MedicationImportResult:
    sheets = session.scalar(
        select(func.count()).select_from(ImportedSourceSheet).where(
            ImportedSourceSheet.import_batch_id == batch.id
        )
    )
    occurrences = session.scalar(
        select(func.sum(ImportedSourceSheet.data_row_count)).where(
            ImportedSourceSheet.import_batch_id == batch.id
        )
    )
    values = session.scalar(
        select(func.sum(ImportedSourceSheet.material_value_count)).where(
            ImportedSourceSheet.import_batch_id == batch.id
        )
    )
    quarantined = session.scalar(
        select(func.count()).select_from(QuarantinedSourceRow).where(
            QuarantinedSourceRow.import_batch_id == batch.id
        )
    )
    diagnostics = session.scalar(
        select(func.count()).select_from(ImportDiagnostic).where(
            ImportDiagnostic.import_batch_id == batch.id
        )
    )
    links = 0
    if batch.source_document_version_id is not None:
        links = int(
            session.scalar(
                select(func.count())
                .select_from(TargetRecordLink)
                .join(SourceFragment, TargetRecordLink.source_fragment_id == SourceFragment.id)
                .where(
                    SourceFragment.document_version_id == batch.source_document_version_id,
                    TargetRecordLink.link_type == "composition_active_ingredient",
                )
            )
            or 0
        )
    return MedicationImportResult(
        batch.id,
        False,
        batch.status,
        int(sheets or 0),
        int(occurrences or 0),
        int(values or 0),
        int(quarantined or 0),
        int(diagnostics or 0),
        links,
    )


def _flush_rows(session: Session, buffers: dict[str, list[dict[str, object]]]) -> None:
    table_order = (
        ("targets", TargetRecord.__table__),
        ("document_links", DocumentRecordLink.__table__),
        ("fragments", SourceFragment.__table__),
        ("blocks", BlockInstance.__table__),
        ("values", FieldValue.__table__),
        ("provenances", ValueProvenance.__table__),
        ("target_links", TargetRecordLink.__table__),
    )
    for name, table in table_order:
        rows = buffers[name]
        if rows:
            session.execute(insert(cast(Table, table)), rows)
            rows.clear()


def import_medications(
    session: Session,
    source_path: Path,
    *,
    source_version: str | None = None,
) -> MedicationImportResult:
    source_bytes = source_path.read_bytes()
    content_hash = sha256(source_bytes).hexdigest()
    batch, created = get_or_create_import_batch(
        session,
        ImportBatchRequest(
            source_system="master_excel",
            source_locator=source_path.name,
            source_bytes=source_bytes,
            importer_name=IMPORTER_NAME,
            importer_version=IMPORTER_VERSION,
            source_version=source_version,
        ),
    )
    if not created:
        return _existing_result(session, batch)
    try:
        parsed = _parse_workbook(source_path)
    except (MedicationImportError, ET.ParseError, zipfile.BadZipFile, KeyError, OSError) as error:
        record_diagnostic(
            session,
            batch=batch,
            severity="error",
            code="MEDICATION_IMPORT_INVALID",
            message=str(error),
        )
        fail_import_batch(batch)
        return MedicationImportResult(batch.id, True, batch.status, 0, 0, 0, 0, 1, 0)

    version = _ensure_document_version(
        session,
        batch_id=batch.id,
        source_path=source_path,
        content_hash=content_hash,
        source_version=source_version,
    )
    session.flush()
    active_targets = _active_ingredient_targets(session)
    medication_targets: defaultdict[str, list[str]] = defaultdict(list)
    child_ordinals: Counter[tuple[str, str]] = Counter()
    buffers: dict[str, list[dict[str, object]]] = {
        "targets": [],
        "document_links": [],
        "fragments": [],
        "blocks": [],
        "values": [],
        "provenances": [],
        "target_links": [],
    }
    occurrences = 0
    values = 0
    quarantined = 0
    diagnostics = 0
    composition_links = 0

    for (
        sheet_ordinal,
        sheet_name,
        block_type,
        header_row_number,
        headers,
        header_cells,
        rows,
    ) in parsed:
        session.add(
            ImportedSourceSheet(
                id=sha256(f"{batch.id}:{sheet_ordinal}".encode()).hexdigest(),
                import_batch_id=batch.id,
                sheet_name=sheet_name,
                sheet_ordinal=sheet_ordinal,
                header_row_number=header_row_number,
                header_payload=_payload(headers, header_cells),
                data_row_count=len(rows),
                material_value_count=sum(len(row) for _, row in rows),
            )
        )
        if not rows:
            record_diagnostic(
                session,
                batch=batch,
                severity="info",
                code="EMPTY_SOURCE_SHEET",
                message=f"La hoja {sheet_name} solo contiene cabecera en esta versión.",
                source_locator=sheet_name,
            )
            diagnostics += 1
            continue

        header_columns = {value: column for column, value in headers.items()}
        for row_number, row in rows:
            parent_column = header_columns.get("MED_IDEXTERNO")
            parent_literal = (
                ""
                if parent_column is None or parent_column not in row
                else row[parent_column].literal_value
            )
            if sheet_name == "General":
                target_id = _stable_uuid(batch.id, sheet_name, row_number, "target")
                buffers["targets"].append(
                    {"id": target_id, "entity_type": "medication"}
                )
                buffers["document_links"].append(
                    {
                        "id": _stable_uuid(version.id, target_id, "master_baseline"),
                        "document_version_id": version.id,
                        "target_record_id": target_id,
                        "link_type": "master_baseline",
                    }
                )
                medication_targets[parent_literal].append(target_id)
                block_ordinal = 1
            else:
                candidates = medication_targets.get(parent_literal, [])
                if len(candidates) != 1:
                    quarantine_source_row(
                        session,
                        batch=batch,
                        source_locator=f"{sheet_name}!{row_number}",
                        reason_code="MISSING_PARENT" if not candidates else "AMBIGUOUS_PARENT",
                        reason="No existe un único medicamento padre en esta versión.",
                        raw_payload=_payload(headers, row),
                    )
                    quarantined += 1
                    continue
                target_id = candidates[0]
                child_ordinals[(target_id, sheet_name)] += 1
                block_ordinal = child_ordinals[(target_id, sheet_name)]

            fragment_id = _stable_uuid(version.id, sheet_name, row_number)
            block_id = _stable_uuid(batch.id, sheet_name, row_number, "block")
            buffers["fragments"].append(
                {
                    "id": fragment_id,
                    "document_version_id": version.id,
                    "locator_type": "excel_row",
                    "locator": json.dumps(
                        {"row": row_number, "sheet": sheet_name},
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    "literal_text": _payload(headers, row),
                }
            )
            buffers["blocks"].append(
                {
                    "id": block_id,
                    "target_record_id": target_id,
                    "block_type": block_type,
                    "ordinal": block_ordinal,
                    "source_fragment_id": fragment_id,
                }
            )
            for column, cell in sorted(row.items()):
                field_id = _stable_uuid(block_id, column, "field")
                buffers["values"].append(
                    {
                        "id": field_id,
                        "block_instance_id": block_id,
                        "field_name": headers.get(column, f"__COLUMN_{column}"),
                        "literal_value": cell.literal_value,
                        "observed_type": cell.observed_type,
                        "logical_state": "empty" if cell.literal_value == "" else "valued",
                    }
                )
                buffers["provenances"].append(
                    {
                        "id": _stable_uuid(field_id, fragment_id, "baseline"),
                        "field_value_id": field_id,
                        "source_fragment_id": fragment_id,
                        "provenance_role": "master_baseline",
                    }
                )
                values += 1

            if sheet_name == "Composicion":
                active_column = header_columns.get("PA_IDEXTERNO")
                active_literal = (
                    ""
                    if active_column is None or active_column not in row
                    else row[active_column].literal_value
                )
                active_candidates = active_targets.get(active_literal, [])
                if len(active_candidates) == 1:
                    buffers["target_links"].append(
                        {
                            "id": _stable_uuid(fragment_id, "composition_active_ingredient"),
                            "source_record_id": target_id,
                            "target_record_id": active_candidates[0],
                            "link_type": "composition_active_ingredient",
                            "source_fragment_id": fragment_id,
                        }
                    )
                    composition_links += 1
                else:
                    quarantine_source_row(
                        session,
                        batch=batch,
                        source_locator=f"{sheet_name}!{row_number}",
                        reason_code=(
                            "MISSING_ACTIVE_INGREDIENT"
                            if not active_candidates
                            else "AMBIGUOUS_ACTIVE_INGREDIENT"
                        ),
                        reason="No existe un único principio activo relacionado.",
                        raw_payload=_payload(headers, row),
                    )
                    quarantined += 1
            occurrences += 1
            if occurrences % BULK_OCCURRENCES == 0:
                _flush_rows(session, buffers)

    _flush_rows(session, buffers)
    for external_id, target_ids in sorted(medication_targets.items()):
        if external_id == "" or len(target_ids) > 1:
            record_diagnostic(
                session,
                batch=batch,
                severity="warning",
                code="MEDICATION_SOURCE_IDENTITY",
                message="Identificador externo vacío o repetido; no se fusionan registros.",
                details_literal=json.dumps(
                    {"identifier": external_id, "occurrences": len(target_ids)},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                occurrence_count=len(target_ids),
            )
            diagnostics += 1
    complete_import_batch(batch)
    session.flush()
    return MedicationImportResult(
        batch.id,
        True,
        batch.status,
        len(parsed),
        occurrences,
        values,
        quarantined,
        diagnostics,
        composition_links,
    )
