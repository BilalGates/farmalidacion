import json
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_validator_api.import_batches import (
    ImportBatchRequest,
    complete_import_batch,
    fail_import_batch,
    get_or_create_import_batch,
    record_diagnostic,
)
from pharma_validator_api.models import CatalogFieldDefinition

CATALOG_FILENAME = "Catalogo_campos_clinicos_medicamentos.xlsx"
CATALOG_SHEET = "Eval. solo Ficha Técnica"
CATALOG_FIELD_COUNT = 353
IMPORTER_NAME = "catalog_fields"
IMPORTER_VERSION = "1.0.0"
TYPE_OVERRIDES = {
    "EX_DESCRIPCION": ("CHAR(100)", "D-021"),
    "ME_DESCRIPCION": ("CHAR(100)", "D-021"),
}
BLOCK_TYPE_OVERRIDES = {
    ("Medicamento - Composición", "DESCRIPCION"): ("CHAR(100)", "D-026"),
    ("Medicamento - Links", "DESCRIPCION"): ("CHAR(255)", "D-026"),
}

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
MAX_ZIP_MEMBERS = 10_000
MAX_MEMBER_SIZE = 512 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1_000


def tag(name: str) -> str:
    return f"{{{NS_MAIN}}}{name}"


class CatalogImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class Cell:
    column: int
    observed_type: str
    literal_value: str
    formula: str | None


@dataclass(frozen=True)
class CatalogImportResult:
    batch_id: str
    created: bool
    status: str
    imported_fields: int
    diagnostics: int


def _column_index(reference: str) -> int:
    match = re.match(r"[A-Z]+", reference.upper())
    if match is None:
        raise CatalogImportError(f"Referencia de celda inválida: {reference}")
    result = 0
    for character in match.group(0):
        result = result * 26 + ord(character) - 64
    return result


def _validate_archive(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise CatalogImportError("La fuente no es un fichero regular.")
    total = 0
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            raise CatalogImportError("El XLSX contiene demasiadas entradas ZIP.")
        names = {member.filename for member in members}
        for member in members:
            pure = PurePosixPath(member.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in member.filename:
                raise CatalogImportError("El XLSX contiene una ruta ZIP insegura.")
            total += member.file_size
            ratio = member.file_size / member.compress_size if member.compress_size else 0
            if (
                member.file_size > MAX_MEMBER_SIZE
                or total > MAX_TOTAL_UNCOMPRESSED
                or ratio > MAX_COMPRESSION_RATIO
            ):
                raise CatalogImportError("El XLSX supera los límites de descompresión.")
            lower = member.filename.lower()
            if (
                lower.endswith("vbaproject.bin")
                or "/embeddings/" in lower
                or "/activex/" in lower
                or "/oleobjects/" in lower
                or lower.endswith(".ole")
            ):
                raise CatalogImportError("El XLSX contiene contenido activo no permitido.")
        if any(name.startswith("xl/externalLinks/") for name in names):
            raise CatalogImportError("El XLSX contiene vínculos externos no permitidos.")


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    result: list[str] = []
    with archive.open("xl/sharedStrings.xml") as handle:
        for _event, element in ET.iterparse(handle, events=("end",)):
            if element.tag == tag("si"):
                result.append("".join(node.text or "" for node in element.iter(tag("t"))))
                element.clear()
    return result


def _sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        item.get("Id"): item.get("Target", "")
        for item in relationships.findall(f"{{{NS_PKG_REL}}}Relationship")
    }
    sheets = workbook.find(tag("sheets"))
    matches = []
    for sheet in [] if sheets is None else sheets:
        if sheet.get("name") == sheet_name:
            target = targets.get(sheet.get(f"{{{NS_REL}}}id"), "")
            matches.append(str(PurePosixPath("xl") / target).replace("xl/../", ""))
    if len(matches) != 1:
        raise CatalogImportError(
            f"Se esperaba una hoja '{sheet_name}' y se encontraron {len(matches)}."
        )
    return matches[0]


def _read_cell(cell: ET.Element, strings: list[str]) -> Cell | None:
    cell_type = cell.get("t")
    formula_element = cell.find(tag("f"))
    value_element = cell.find(tag("v"))
    formula = formula_element.text if formula_element is not None else None
    cached = value_element.text if value_element is not None else None
    if cell_type == "inlineStr":
        value_type, value = "inline_string", "".join(
            node.text or "" for node in cell.iter(tag("t"))
        )
    elif cell_type == "s" and cached is not None:
        try:
            value_type, value = "shared_string", strings[int(cached)]
        except (ValueError, IndexError) as error:
            raise CatalogImportError("Índice shared string inválido.") from error
    elif cell_type == "str":
        value_type, value = "string", cached or ""
    elif cell_type == "b":
        value_type, value = "boolean", cached or ""
    elif cell_type == "e":
        value_type, value = "error", cached or ""
    elif cell_type == "d":
        value_type, value = "date_iso", cached or ""
    elif formula is not None:
        value_type, value = "formula", cached or ""
    elif cached is None:
        return None
    else:
        value_type, value = "number", cached
    return Cell(_column_index(cell.get("r", "")), value_type, value, formula)


def _iter_rows(
    archive: zipfile.ZipFile, sheet_path: str, strings: list[str]
) -> list[tuple[int, dict[int, Cell]]]:
    rows: list[tuple[int, dict[int, Cell]]] = []
    current_number = 0
    current: dict[int, Cell] = {}
    with archive.open(sheet_path) as handle:
        for event, element in ET.iterparse(handle, events=("start", "end")):
            if event == "start" and element.tag == tag("row"):
                current_number = int(element.get("r", "0"))
                current = {}
            elif event == "end" and element.tag == tag("c"):
                parsed = _read_cell(element, strings)
                if parsed is not None:
                    current[parsed.column] = parsed
                element.clear()
            elif event == "end" and element.tag == tag("row"):
                if current:
                    rows.append((current_number, current))
                element.clear()
    return rows


def _parse_catalog(path: Path, sheet_name: str) -> list[tuple[int, dict[str, Cell], str]]:
    _validate_archive(path)
    with zipfile.ZipFile(path) as archive:
        strings = _shared_strings(archive)
        rows = _iter_rows(archive, _sheet_path(archive, sheet_name), strings)
    candidates = []
    for index, (_row_number, row) in enumerate(rows):
        values = {cell.literal_value for cell in row.values()}
        if {"Entidad", "Campo", "Tipo"} <= values:
            candidates.append((index, row))
    if len(candidates) != 1:
        raise CatalogImportError(
            f"Se esperaba una cabecera Entidad/Campo/Tipo y se encontraron {len(candidates)}."
        )
    header_index, header_row = candidates[0]
    headers = {column: cell.literal_value for column, cell in header_row.items()}
    number_column = min(headers)
    parsed: list[tuple[int, dict[str, Cell], str]] = []
    for row_number, row in rows[header_index + 1 :]:
        number = row.get(number_column)
        if number is None or not number.literal_value.isdigit():
            continue
        sequence = int(number.literal_value)
        if not 1 <= sequence <= CATALOG_FIELD_COUNT:
            continue
        mapped = {headers[column]: cell for column, cell in row.items() if column in headers}
        payload = json.dumps(
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
        parsed.append((row_number, mapped, payload))
    sequences = [
        int(row[next(key for key in row if key.startswith("N"))].literal_value)
        for _, row, _ in parsed
    ]
    if sequences != list(range(1, CATALOG_FIELD_COUNT + 1)):
        raise CatalogImportError("La secuencia activa del catálogo no es exactamente 1..353.")
    return parsed


def _literal(row: dict[str, Cell], name: str) -> str:
    cell = row.get(name)
    return "" if cell is None else cell.literal_value


def import_catalog(
    session: Session,
    source_path: Path,
    *,
    source_version: str | None = None,
) -> CatalogImportResult:
    source_bytes = source_path.read_bytes()
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
        imported = session.scalar(
            select(func.count()).select_from(CatalogFieldDefinition).where(
                CatalogFieldDefinition.import_batch_id == batch.id
            )
        )
        return CatalogImportResult(batch.id, False, batch.status, int(imported or 0), 0)
    try:
        parsed = _parse_catalog(source_path, CATALOG_SHEET)
    except (CatalogImportError, ET.ParseError, zipfile.BadZipFile, KeyError, OSError) as error:
        record_diagnostic(
            session,
            batch=batch,
            severity="error",
            code="CATALOG_IMPORT_INVALID",
            message=str(error),
        )
        fail_import_batch(batch)
        return CatalogImportResult(batch.id, True, batch.status, 0, 1)

    identities: Counter[tuple[str, str]] = Counter()
    types: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for row_number, row, payload in parsed:
        field_name = _literal(row, "Campo")
        declared_type = _literal(row, "Tipo")
        block = _literal(row, "Bloque origen")
        identity = (block, field_name)
        override = BLOCK_TYPE_OVERRIDES.get(identity) or TYPE_OVERRIDES.get(field_name)
        identities[identity] += 1
        types[identity].add(declared_type)
        definition_id = sha256(f"{batch.id}:{row_number}".encode()).hexdigest()
        session.add(
            CatalogFieldDefinition(
                id=definition_id,
                import_batch_id=batch.id,
                sheet_name=CATALOG_SHEET,
                source_row_number=row_number,
                sequence_literal=_literal(row, next(key for key in row if key.startswith("N"))),
                entity_literal=_literal(row, "Entidad"),
                block_literal=block,
                field_name_literal=field_name,
                declared_type_literal=declared_type,
                effective_type=override[0] if override else declared_type,
                override_decision=override[1] if override else None,
                required_literal=_literal(row, "Obl.") or None,
                from_ft_literal=_literal(row, "¿Desde la FT?") or None,
                ft_section_literal=_literal(row, "Sección FT") or None,
                comment_literal=_literal(row, "Comentario") or None,
                raw_payload=payload,
            )
        )
    diagnostics = 0
    for (block, field_name), count in sorted(identities.items()):
        if count > 1:
            record_diagnostic(
                session,
                batch=batch,
                severity="warning",
                code="CATALOG_FIELD_IDENTITY",
                message=f"Identidad repetida conservada: {block}/{field_name}",
                occurrence_count=count,
            )
            diagnostics += 1
    for (block, field_name), declared_types in sorted(types.items()):
        if len(declared_types) > 1:
            record_diagnostic(
                session,
                batch=batch,
                severity="error",
                code="CATALOG_TYPE_CONFLICT",
                message=f"Tipos en conflicto conservados: {block}/{field_name}",
                details_literal=json.dumps(sorted(declared_types), ensure_ascii=False),
                occurrence_count=len(declared_types),
            )
            diagnostics += 1
    complete_import_batch(batch)
    session.flush()
    return CatalogImportResult(batch.id, True, batch.status, len(parsed), diagnostics)
