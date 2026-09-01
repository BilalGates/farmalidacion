import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree as ET

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)

SOURCE_FILENAME = "PrincipioActivoCargaMaster-22062026.xlsx"
SOURCE_HASH = "89e6806b4cba7d6724533bfdc29ea834056223872385f08c080b72b965448e6c"
IMPORTER_NAME = "active_ingredient_master"
IMPORTER_VERSION = "1.0.0"
SHEETS = (
    ("General", "active_ingredient_general"),
    ("Frecuencia", "active_ingredient_frequency"),
    ("Via", "active_ingredient_route"),
    ("ConsejosAdministracion", "active_ingredient_administration_advice"),
    ("DatosAnaliticos", "active_ingredient_analytical_data"),
)


@dataclass(frozen=True)
class ActiveIngredientImportResult:
    batch_id: str
    created: bool
    status: str
    sheets: int
    occurrences: int
    values: int
    quarantined_rows: int
    diagnostics: int


class ActiveIngredientImportError(RuntimeError):
    pass


def _stable_uuid(*parts: object) -> str:
    return str(uuid5(NAMESPACE_URL, "\\x1f".join(str(part) for part in parts)))


def _payload(headers: dict[int, str], row: dict[int, Cell]) -> str:
    return json.dumps(
        [
            {
                "column": cell.column,
                "formula": cell.formula,
                "header": headers.get(cell.column),
                "literal_value": cell.literal_value,
                "observed_type": cell.observed_type,
            }
            for cell in sorted(row.values(), key=lambda item: item.column)
        ],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


ParsedSheet = tuple[
    int,
    str,
    str,
    int,
    dict[int, str],
    dict[int, Cell],
    list[tuple[int, dict[int, Cell]]],
]


def _parse_workbook(path: Path) -> list[ParsedSheet]:
    _validate_archive(path)
    parsed = []
    with zipfile.ZipFile(path) as archive:
        strings = _shared_strings(archive)
        for ordinal, (sheet_name, block_type) in enumerate(SHEETS, start=1):
            rows = _iter_rows(archive, _sheet_path(archive, sheet_name), strings)
            if not rows:
                raise ActiveIngredientImportError(f"La hoja {sheet_name} no contiene cabecera.")
            header_row_number, header_row = rows[0]
            headers = {column: cell.literal_value for column, cell in header_row.items()}
            if not headers or any(not header for header in headers.values()):
                raise ActiveIngredientImportError(
                    f"La hoja {sheet_name} contiene cabeceras vacías."
                )
            parsed.append(
                (
                    ordinal,
                    sheet_name,
                    block_type,
                    header_row_number,
                    headers,
                    header_row,
                    rows[1:],
                )
            )
    return parsed


def _ensure_document_version(
    session: Session,
    *,
    batch_id: str,
    source_path: Path,
    content_hash: str,
    source_version: str | None,
) -> SourceDocumentVersion:
    document_id = _stable_uuid("master_excel", source_path.name)
    document = session.get(SourceDocument, document_id)
    if document is None:
        document = SourceDocument(
            id=document_id,
            source_type="master_excel",
            name=source_path.name,
        )
        session.add(document)
    version_id = _stable_uuid(document_id, content_hash, source_version or "")
    version = session.get(SourceDocumentVersion, version_id)
    if version is None:
        version = SourceDocumentVersion(
            id=version_id,
            document_id=document_id,
            content_hash=content_hash,
            source_version=source_version,
            source_locator=source_path.name,
            acquired_at=datetime.now(UTC),
        )
        session.add(version)
    batch = session.get(ImportBatch, batch_id)
    assert batch is not None
    batch.source_document_version_id = version.id
    return version


def _persist_occurrence(
    session: Session,
    *,
    batch_id: str,
    document_version_id: str,
    target_record_id: str,
    sheet_name: str,
    block_type: str,
    source_row_number: int,
    ordinal: int,
    headers: dict[int, str],
    row: dict[int, Cell],
) -> int:
    fragment_id = _stable_uuid(document_version_id, sheet_name, source_row_number)
    fragment = SourceFragment(
        id=fragment_id,
        document_version_id=document_version_id,
        locator_type="excel_row",
        locator=json.dumps(
            {"row": source_row_number, "sheet": sheet_name},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        literal_text=_payload(headers, row),
    )
    block_id = _stable_uuid(batch_id, sheet_name, source_row_number, "block")
    session.add(fragment)
    session.add(
        BlockInstance(
            id=block_id,
            target_record_id=target_record_id,
            block_type=block_type,
            ordinal=ordinal,
            source_fragment_id=fragment_id,
        )
    )
    count = 0
    for column, cell in sorted(row.items()):
        field_id = _stable_uuid(block_id, column, "field")
        session.add(
            FieldValue(
                id=field_id,
                block_instance_id=block_id,
                field_name=headers.get(column, f"__COLUMN_{column}"),
                literal_value=cell.literal_value,
                observed_type=cell.observed_type,
                logical_state="empty" if cell.literal_value == "" else "valued",
            )
        )
        session.add(
            ValueProvenance(
                id=_stable_uuid(field_id, fragment_id, "baseline"),
                field_value_id=field_id,
                source_fragment_id=fragment_id,
                provenance_role="master_baseline",
            )
        )
        count += 1
    return count


def _existing_result(session: Session, batch_id: str, status: str) -> ActiveIngredientImportResult:
    sheets = session.scalar(
        select(func.count()).select_from(ImportedSourceSheet).where(
            ImportedSourceSheet.import_batch_id == batch_id
        )
    )
    occurrences = session.scalar(
        select(func.sum(ImportedSourceSheet.data_row_count)).where(
            ImportedSourceSheet.import_batch_id == batch_id
        )
    )
    values = session.scalar(
        select(func.sum(ImportedSourceSheet.material_value_count)).where(
            ImportedSourceSheet.import_batch_id == batch_id
        )
    )
    quarantined = session.scalar(
        select(func.count()).select_from(QuarantinedSourceRow).where(
            QuarantinedSourceRow.import_batch_id == batch_id
        )
    )
    diagnostics = session.scalar(
        select(func.count()).select_from(ImportDiagnostic).where(
            ImportDiagnostic.import_batch_id == batch_id
        )
    )
    return ActiveIngredientImportResult(
        batch_id,
        False,
        status,
        int(sheets or 0),
        int(occurrences or 0),
        int(values or 0),
        int(quarantined or 0),
        int(diagnostics or 0),
    )


def import_active_ingredients(
    session: Session,
    source_path: Path,
    *,
    source_version: str | None = None,
) -> ActiveIngredientImportResult:
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
        return _existing_result(session, batch.id, batch.status)
    try:
        parsed = _parse_workbook(source_path)
    except (
        ActiveIngredientImportError,
        ET.ParseError,
        zipfile.BadZipFile,
        KeyError,
        OSError,
    ) as error:
        record_diagnostic(
            session,
            batch=batch,
            severity="error",
            code="ACTIVE_INGREDIENT_IMPORT_INVALID",
            message=str(error),
        )
        fail_import_batch(batch)
        return ActiveIngredientImportResult(batch.id, True, batch.status, 0, 0, 0, 0, 1)

    version = _ensure_document_version(
        session,
        batch_id=batch.id,
        source_path=source_path,
        content_hash=content_hash,
        source_version=source_version,
    )
    targets_by_external_id: defaultdict[str, list[str]] = defaultdict(list)
    occurrences = 0
    values = 0
    quarantined = 0
    diagnostics = 0
    child_ordinals: Counter[tuple[str, str]] = Counter()

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
            if sheet_name == "General":
                target_id = _stable_uuid(batch.id, sheet_name, row_number, "target")
                session.add(TargetRecord(id=target_id, entity_type="active_ingredient"))
                session.add(
                    DocumentRecordLink(
                        id=_stable_uuid(version.id, target_id, "master_baseline"),
                        document_version_id=version.id,
                        target_record_id=target_id,
                        link_type="master_baseline",
                    )
                )
                external_column = header_columns.get("IDEXTERNO")
                if external_column is not None and external_column in row:
                    targets_by_external_id[row[external_column].literal_value].append(target_id)
                block_ordinal = 1
            else:
                parent_column = header_columns.get("PA_IDEXTERNO")
                parent_literal = (
                    ""
                    if parent_column is None or parent_column not in row
                    else row[parent_column].literal_value
                )
                candidates = targets_by_external_id.get(parent_literal, [])
                if len(candidates) != 1:
                    reason_code = "MISSING_PARENT" if not candidates else "AMBIGUOUS_PARENT"
                    quarantine_source_row(
                        session,
                        batch=batch,
                        source_locator=f"{sheet_name}!{row_number}",
                        reason_code=reason_code,
                        reason="No existe un único principio activo padre en esta versión.",
                        raw_payload=_payload(headers, row),
                    )
                    quarantined += 1
                    continue
                target_id = candidates[0]
                child_ordinals[(target_id, sheet_name)] += 1
                block_ordinal = child_ordinals[(target_id, sheet_name)]
            values += _persist_occurrence(
                session,
                batch_id=batch.id,
                document_version_id=version.id,
                target_record_id=target_id,
                sheet_name=sheet_name,
                block_type=block_type,
                source_row_number=row_number,
                ordinal=block_ordinal,
                headers=headers,
                row=row,
            )
            occurrences += 1

    for external_id, target_ids in sorted(targets_by_external_id.items()):
        if external_id == "" or len(target_ids) > 1:
            record_diagnostic(
                session,
                batch=batch,
                severity="warning",
                code="ACTIVE_INGREDIENT_SOURCE_IDENTITY",
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
    return ActiveIngredientImportResult(
        batch.id,
        True,
        batch.status,
        len(parsed),
        occurrences,
        values,
        quarantined,
        diagnostics,
    )
