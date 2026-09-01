import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import func, select
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
from pharma_validator_api.medication_importer import _flush_rows
from pharma_validator_api.models import (
    BlockInstance,
    FieldValue,
    ImportBatch,
    ImportDiagnostic,
    ImportedSourceSheet,
    QuarantinedSourceRow,
    SourceFragment,
    TargetRecord,
    TargetRecordLink,
)

SOURCE_FILENAME = "Especialidades-CargaMaster190626.xlsx"
SOURCE_HASH = "2117c3e33c05158dd10f81ce07424dd1ea2d0f36747faea3ad9c630b2d4ab37b"
IMPORTER_NAME = "specialty_master"
IMPORTER_VERSION = "1.0.0"
SHEETS = (
    ("General", "specialty_general"),
    ("Excipientes", "specialty_excipient"),
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
class SpecialtyImportResult:
    batch_id: str
    created: bool
    status: str
    sheets: int
    source_rows: int
    occurrences: int
    values: int
    quarantined_rows: int
    orphan_parent_identifiers: int
    diagnostics: int
    medication_links: int


class SpecialtyImportError(RuntimeError):
    pass


def _parse_workbook(path: Path) -> list[ParsedSheet]:
    _validate_archive(path)
    parsed: list[ParsedSheet] = []
    with zipfile.ZipFile(path) as archive:
        strings = _shared_strings(archive)
        for ordinal, (sheet_name, block_type) in enumerate(SHEETS, start=1):
            rows = _iter_rows(archive, _sheet_path(archive, sheet_name), strings)
            if not rows:
                raise SpecialtyImportError(f"La hoja {sheet_name} no contiene cabecera.")
            header_row_number, header_cells = rows[0]
            headers = {column: cell.literal_value for column, cell in header_cells.items()}
            if not headers or any(not header for header in headers.values()):
                raise SpecialtyImportError(
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


def _medication_targets(session: Session) -> dict[str, list[str]]:
    rows = session.execute(
        select(FieldValue.literal_value, BlockInstance.target_record_id)
        .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
        .join(TargetRecord, BlockInstance.target_record_id == TargetRecord.id)
        .where(
            TargetRecord.entity_type == "medication",
            BlockInstance.block_type == "medication_general",
            FieldValue.field_name == "MED_IDEXTERNO",
        )
    )
    result: defaultdict[str, list[str]] = defaultdict(list)
    for literal, target_id in rows:
        result[literal or ""].append(target_id)
    return dict(result)


def _orphan_identifier_count(session: Session, batch_id: str) -> int:
    payloads = session.scalars(
        select(QuarantinedSourceRow.raw_payload).where(
            QuarantinedSourceRow.import_batch_id == batch_id,
            QuarantinedSourceRow.reason_code == "MISSING_PARENT",
        )
    )
    identifiers: set[str] = set()
    for payload in payloads:
        for value in json.loads(payload):
            if value.get("header") == "BN_IDEXTERNO":
                identifiers.add(str(value.get("literal_value", "")))
                break
    return len(identifiers)


def _existing_result(session: Session, batch: ImportBatch) -> SpecialtyImportResult:
    sheets = int(
        session.scalar(
            select(func.count()).select_from(ImportedSourceSheet).where(
                ImportedSourceSheet.import_batch_id == batch.id
            )
        )
        or 0
    )
    source_rows = int(
        session.scalar(
            select(func.sum(ImportedSourceSheet.data_row_count)).where(
                ImportedSourceSheet.import_batch_id == batch.id
            )
        )
        or 0
    )
    occurrences = int(
        session.scalar(
            select(func.count())
            .select_from(BlockInstance)
            .join(SourceFragment, BlockInstance.source_fragment_id == SourceFragment.id)
            .where(SourceFragment.document_version_id == batch.source_document_version_id)
        )
        or 0
    )
    values = int(
        session.scalar(
            select(func.count())
            .select_from(FieldValue)
            .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
            .join(SourceFragment, BlockInstance.source_fragment_id == SourceFragment.id)
            .where(SourceFragment.document_version_id == batch.source_document_version_id)
        )
        or 0
    )
    quarantined = int(
        session.scalar(
            select(func.count()).select_from(QuarantinedSourceRow).where(
                QuarantinedSourceRow.import_batch_id == batch.id
            )
        )
        or 0
    )
    diagnostics = int(
        session.scalar(
            select(func.count()).select_from(ImportDiagnostic).where(
                ImportDiagnostic.import_batch_id == batch.id
            )
        )
        or 0
    )
    medication_links = int(
        session.scalar(
            select(func.count())
            .select_from(TargetRecordLink)
            .join(SourceFragment, TargetRecordLink.source_fragment_id == SourceFragment.id)
            .where(
                SourceFragment.document_version_id == batch.source_document_version_id,
                TargetRecordLink.link_type == "specialty_medication",
            )
        )
        or 0
    )
    return SpecialtyImportResult(
        batch.id,
        False,
        batch.status,
        sheets,
        source_rows,
        occurrences,
        values,
        quarantined,
        _orphan_identifier_count(session, batch.id),
        diagnostics,
        medication_links,
    )


def import_specialties(
    session: Session,
    source_path: Path,
    *,
    source_version: str | None = None,
) -> SpecialtyImportResult:
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
    except (SpecialtyImportError, ET.ParseError, zipfile.BadZipFile, KeyError, OSError) as error:
        record_diagnostic(
            session,
            batch=batch,
            severity="error",
            code="SPECIALTY_IMPORT_INVALID",
            message=str(error),
        )
        fail_import_batch(batch)
        return SpecialtyImportResult(
            batch.id, True, batch.status, 0, 0, 0, 0, 0, 0, 1, 0
        )

    version = _ensure_document_version(
        session,
        batch_id=batch.id,
        source_path=source_path,
        content_hash=content_hash,
        source_version=source_version,
    )
    session.flush()
    medication_targets = _medication_targets(session)
    specialty_targets: defaultdict[str, list[str]] = defaultdict(list)
    child_ordinals: Counter[str] = Counter()
    buffers: dict[str, list[dict[str, object]]] = {
        "targets": [],
        "document_links": [],
        "fragments": [],
        "blocks": [],
        "values": [],
        "provenances": [],
        "target_links": [],
    }
    source_rows = 0
    occurrences = 0
    values = 0
    quarantined = 0
    diagnostics = 0
    medication_links = 0
    orphan_identifiers: set[str] = set()

    for (
        sheet_ordinal,
        sheet_name,
        block_type,
        header_row_number,
        headers,
        header_cells,
        rows,
    ) in parsed:
        source_rows += len(rows)
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
        header_columns = {value: column for column, value in headers.items()}
        parent_column = header_columns.get("BN_IDEXTERNO")
        for row_number, row in rows:
            parent_literal = (
                ""
                if parent_column is None or parent_column not in row
                else row[parent_column].literal_value
            )
            if sheet_name == "General":
                target_id = _stable_uuid(batch.id, sheet_name, row_number, "target")
                buffers["targets"].append(
                    {"id": target_id, "entity_type": "specialty"}
                )
                buffers["document_links"].append(
                    {
                        "id": _stable_uuid(version.id, target_id, "master_baseline"),
                        "document_version_id": version.id,
                        "target_record_id": target_id,
                        "link_type": "master_baseline",
                    }
                )
                specialty_targets[parent_literal].append(target_id)
                block_ordinal = 1
            else:
                candidates = specialty_targets.get(parent_literal, [])
                if len(candidates) != 1:
                    reason_code = "MISSING_PARENT" if not candidates else "AMBIGUOUS_PARENT"
                    quarantine_source_row(
                        session,
                        batch=batch,
                        source_locator=f"{sheet_name}!{row_number}",
                        reason_code=reason_code,
                        reason="No existe una única especialidad padre en esta versión.",
                        raw_payload=_payload(headers, row),
                    )
                    if reason_code == "MISSING_PARENT":
                        orphan_identifiers.add(parent_literal)
                    quarantined += 1
                    continue
                target_id = candidates[0]
                child_ordinals[target_id] += 1
                block_ordinal = child_ordinals[target_id]

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

            if sheet_name == "General":
                medication_column = header_columns.get("ME_IDEXTERNO")
                medication_literal = (
                    ""
                    if medication_column is None or medication_column not in row
                    else row[medication_column].literal_value
                )
                medication_candidates = medication_targets.get(medication_literal, [])
                if len(medication_candidates) == 1:
                    buffers["target_links"].append(
                        {
                            "id": _stable_uuid(fragment_id, "specialty_medication"),
                            "source_record_id": target_id,
                            "target_record_id": medication_candidates[0],
                            "link_type": "specialty_medication",
                            "source_fragment_id": fragment_id,
                        }
                    )
                    medication_links += 1
                else:
                    record_diagnostic(
                        session,
                        batch=batch,
                        severity="warning",
                        code=(
                            "MISSING_MEDICATION"
                            if not medication_candidates
                            else "AMBIGUOUS_MEDICATION"
                        ),
                        source_locator=f"{sheet_name}!{row_number}",
                        message="No existe un único medicamento relacionado.",
                        details_literal=json.dumps(
                            {"ME_IDEXTERNO": medication_literal},
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    )
                    diagnostics += 1
            occurrences += 1
            if occurrences % BULK_OCCURRENCES == 0:
                _flush_rows(session, buffers)

    _flush_rows(session, buffers)
    for external_id, target_ids in sorted(specialty_targets.items()):
        if external_id == "" or len(target_ids) > 1:
            record_diagnostic(
                session,
                batch=batch,
                severity="warning",
                code="SPECIALTY_SOURCE_IDENTITY",
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
    return SpecialtyImportResult(
        batch.id,
        True,
        batch.status,
        len(parsed),
        source_rows,
        occurrences,
        values,
        quarantined,
        len(orphan_identifiers),
        diagnostics,
        medication_links,
    )
