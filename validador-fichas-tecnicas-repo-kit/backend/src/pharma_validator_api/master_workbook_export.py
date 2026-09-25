"""Rebuild source master workbooks without flattening their Excel structure."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import posixpath
import re
import tempfile
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from pharma_validator_api.active_ingredient_importer import (
    SOURCE_FILENAME as ACTIVE_INGREDIENT_FILENAME,
)
from pharma_validator_api.medication_importer import SOURCE_FILENAME as MEDICATION_FILENAME
from pharma_validator_api.models import (
    BlockInstance,
    FieldMaintenanceRevision,
    FieldValue,
    ImportBatch,
    QuarantinedFieldMaintenanceRevision,
    QuarantinedSourceRow,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
)
from pharma_validator_api.specialty_importer import SOURCE_FILENAME as SPECIALTY_FILENAME

MASTER_WORKBOOKS = (
    ACTIVE_INGREDIENT_FILENAME,
    MEDICATION_FILENAME,
    SPECIALTY_FILENAME,
)
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
def _tag(name: str) -> str:
    return f"{{{MAIN_NS}}}{name}"


TAG = _tag


class MasterWorkbookExportError(RuntimeError):
    """The source workbook cannot be safely rebuilt from current provenance."""


@dataclass(frozen=True)
class MasterWorkbookExportResult:
    filename: str
    output: Path
    source_sha256: str
    output_sha256: str
    changed_cells: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _register_namespaces(payload: bytes) -> None:
    for _event, (prefix, uri) in ET.iterparse(io.BytesIO(payload), events=("start-ns",)):
        if prefix != "xml":
            ET.register_namespace(prefix, uri)


def _workbook_sheets(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        item.get("Id", ""): item.get("Target", "")
        for item in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    sheets = workbook.find(TAG("sheets"))
    if sheets is None:
        raise MasterWorkbookExportError("El XLSX no declara hojas.")
    result: dict[str, str] = {}
    for sheet in list(sheets):
        name = sheet.get("name", "")
        relationship_id = sheet.get(f"{{{DOC_REL_NS}}}id", "")
        target = targets.get(relationship_id)
        if not name or not target or name in result:
            raise MasterWorkbookExportError("Nombres o relaciones de hoja ambiguos.")
        path = target.lstrip("/")
        if not path.startswith("xl/"):
            path = posixpath.normpath(posixpath.join("xl", path))
        if path not in archive.namelist():
            raise MasterWorkbookExportError(f"No existe la hoja OOXML {name!r}.")
        result[name] = path
    return result


def _shared_strings(archive: zipfile.ZipFile) -> tuple[str | None, ET.Element | None, list[str]]:
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return None, None, []
    payload = archive.read(path)
    _register_namespaces(payload)
    root = ET.fromstring(payload)
    values = [
        "".join(text.text or "" for text in item.iter(TAG("t")))
        for item in root.findall(TAG("si"))
    ]
    return path, root, values


def _shared_string_index(
    root: ET.Element,
    values: list[str],
    value: str,
    indexes: dict[str, list[int]],
) -> int:
    candidates = indexes.get(value)
    if candidates:
        return candidates[0]
    item = ET.SubElement(root, TAG("si"))
    text_attributes = {f"{{{XML_NS}}}space": "preserve"} if value != value.strip() else {}
    ET.SubElement(item, TAG("t"), text_attributes).text = value
    index = len(values)
    values.append(value)
    indexes[value] = [index]
    return index


def _column_number(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha()).upper()
    if not letters:
        raise MasterWorkbookExportError(f"Coordenada Excel inválida: {reference!r}.")
    result = 0
    for character in letters:
        result = result * 26 + ord(character) - ord("A") + 1
    return result


def _reference(column: int, row: int) -> str:
    if column < 1 or row < 1:
        raise MasterWorkbookExportError("Fila o columna Excel fuera de rango.")
    label = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        label = chr(ord("A") + remainder) + label
    return f"{label}{row}"


def _cell_value(cell: ET.Element | None, shared_strings: list[str]) -> str | None:
    if cell is None:
        return None
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(TAG("is"))
        return "" if inline is None else "".join(item.text or "" for item in inline.iter(TAG("t")))
    value = cell.find(TAG("v"))
    if value is None:
        return None
    raw = value.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError) as error:
            raise MasterWorkbookExportError("Índice shared-string inválido.") from error
    return raw


def _set_cell_value(
    cell: ET.Element,
    value: str | None,
    shared_root: ET.Element | None,
    shared_strings: list[str],
    shared_indexes: dict[str, list[int]],
) -> bool:
    if cell.find(TAG("f")) is not None:
        raise MasterWorkbookExportError(
            f"La exportación no sobrescribe celdas con fórmula ({cell.get('r')})."
        )
    if value is None or value == "":
        if cell.get("t") == "s":
            for child in list(cell):
                if child.tag in (TAG("v"), TAG("is"), TAG("f")):
                    cell.remove(child)
            cell.attrib.pop("t", None)
            return True
        changed = False
        for child in list(cell):
            if child.tag in (TAG("v"), TAG("is"), TAG("f")):
                cell.remove(child)
                changed = True
        if cell.get("t") is not None:
            cell.attrib.pop("t", None)
            changed = True
        return changed

    cell_type = cell.get("t")
    for child in list(cell):
        if child.tag in (TAG("v"), TAG("is"), TAG("f")):
            cell.remove(child)
    if cell_type == "s":
        if shared_root is None:
            raise MasterWorkbookExportError("La celda usa shared strings sin tabla sharedStrings.")
        index = _shared_string_index(shared_root, shared_strings, value, shared_indexes)
        cell.set("t", "s")
        ET.SubElement(cell, TAG("v")).text = str(index)
        return True
    if cell_type == "inlineStr":
        cell.set("t", "inlineStr")
        inline = ET.SubElement(cell, TAG("is"))
        text_attributes = {f"{{{XML_NS}}}space": "preserve"} if value != value.strip() else {}
        ET.SubElement(inline, TAG("t"), text_attributes).text = value
        return True
    if cell_type == "n" or cell_type is None:
        try:
            number = Decimal(value)
        except InvalidOperation:
            number = None
        if number is not None and number.is_finite():
            cell.attrib.pop("t", None)
            ET.SubElement(cell, TAG("v")).text = value
            return True
        cell.set("t", "inlineStr")
        inline = ET.SubElement(cell, TAG("is"))
        text_attributes = {f"{{{XML_NS}}}space": "preserve"} if value != value.strip() else {}
        ET.SubElement(inline, TAG("t"), text_attributes).text = value
        return True
    if cell_type == "b":
        normalized = value.strip().lower()
        if normalized not in {"0", "1", "true", "false"}:
            raise MasterWorkbookExportError("El valor booleano debe ser 0/1 o true/false.")
        cell.set("t", "b")
        ET.SubElement(cell, TAG("v")).text = "1" if normalized in {"1", "true"} else "0"
        return True
    if cell_type in {"str", "d"}:
        cell.set("t", cell_type)
        ET.SubElement(cell, TAG("v")).text = value
        return True
    raise MasterWorkbookExportError(
        f"No se puede mantener una celda de tipo {cell_type!r} ({cell.get('r')})."
    )


def _locate_cell(root: ET.Element, reference: str, *, create: bool) -> ET.Element | None:
    sheet_data = root.find(TAG("sheetData"))
    if sheet_data is None:
        raise MasterWorkbookExportError("La hoja no contiene sheetData.")
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", reference)
    if match is None:
        raise MasterWorkbookExportError(f"Coordenada Excel inválida: {reference!r}.")
    row_number = int(match.group(2))
    row = next(
        (item for item in sheet_data.findall(TAG("row")) if item.get("r") == str(row_number)),
        None,
    )
    if row is None:
        if not create:
            return None
        row = ET.Element(TAG("row"), {"r": str(row_number)})
        next_row = next(
            (
                item
                for item in sheet_data.findall(TAG("row"))
                if int(item.get("r", "0")) > row_number
            ),
            None,
        )
        if next_row is None:
            sheet_data.append(row)
        else:
            sheet_data.insert(list(sheet_data).index(next_row), row)
    cell = next((item for item in row.findall(TAG("c")) if item.get("r") == reference), None)
    if cell is not None or not create:
        return cell
    cell = ET.Element(TAG("c"), {"r": reference})
    column = _column_number(reference)
    next_cell = next(
        (item for item in row.findall(TAG("c")) if _column_number(item.get("r", "")) > column),
        None,
    )
    if next_cell is None:
        row.append(cell)
    else:
        row.insert(list(row).index(next_cell), cell)
    return cell


def _apply_patches(
    sheet_path: str,
    payload: bytes,
    patches: dict[str, str | None],
    shared_strings: list[str],
    shared_root: ET.Element | None,
    shared_indexes: dict[str, list[int]],
) -> tuple[bytes, int]:
    if not patches:
        return payload, 0
    _register_namespaces(payload)
    root = ET.fromstring(payload)
    changed = 0
    for reference, value in patches.items():
        cell = _locate_cell(root, reference, create=value not in (None, ""))
        before = _cell_value(cell, shared_strings)
        if before == value or (before is None and value == ""):
            continue
        if cell is None:
            continue
        changed += int(
            _set_cell_value(cell, value, shared_root, shared_strings, shared_indexes)
        )
    if not changed:
        return payload, 0
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), changed


def _locator_coordinates(locator: str) -> tuple[str, int]:
    try:
        parsed = json.loads(locator)
        sheet = str(parsed["sheet"])
        row = int(parsed["row"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise MasterWorkbookExportError(f"Localizador de fuente inválido: {locator!r}.") from error
    if not sheet or row < 1:
        raise MasterWorkbookExportError(f"Localizador de fuente inválido: {locator!r}.")
    return sheet, row


def _source_batch(session: Session, source: Path) -> tuple[ImportBatch, str]:
    source_hash = _sha256(source)
    candidates = session.scalars(
        select(ImportBatch).where(
            ImportBatch.source_locator == source.name,
            ImportBatch.content_hash == source_hash,
            ImportBatch.status == "completed",
        )
    ).all()
    if len(candidates) != 1 or candidates[0].source_document_version_id is None:
        raise MasterWorkbookExportError(
            f"Debe existir un único lote completado con el hash actual para {source.name}."
        )
    version = session.get(SourceDocumentVersion, candidates[0].source_document_version_id)
    document = session.get(SourceDocument, version.document_id) if version else None
    if (
        version is None
        or document is None
        or version.content_hash != source_hash
        or document.name != source.name
    ):
        raise MasterWorkbookExportError(
            f"La versión importada no corresponde al libro {source.name}."
        )
    return candidates[0], source_hash


def _maintenance_patches(
    session: Session, batch: ImportBatch, filename: str
) -> dict[tuple[str, int, int], str | None]:
    patches: dict[tuple[str, int, int], str | None] = {}
    latest_field_revision = (
        select(
            FieldMaintenanceRevision.field_value_id.label("field_value_id"),
            func.max(FieldMaintenanceRevision.sequence).label("sequence"),
        )
        .group_by(FieldMaintenanceRevision.field_value_id)
        .subquery()
    )
    field_rows = session.execute(
        select(
            SourceFragment.locator,
            FieldValue.source_column_index,
            FieldMaintenanceRevision.after_value,
        )
        .join(BlockInstance, BlockInstance.source_fragment_id == SourceFragment.id)
        .join(FieldValue, FieldValue.block_instance_id == BlockInstance.id)
        .join(SourceDocumentVersion, SourceDocumentVersion.id == SourceFragment.document_version_id)
        .join(SourceDocument, SourceDocument.id == SourceDocumentVersion.document_id)
        .join(latest_field_revision, latest_field_revision.c.field_value_id == FieldValue.id)
        .join(
            FieldMaintenanceRevision,
            and_(
                FieldMaintenanceRevision.field_value_id == latest_field_revision.c.field_value_id,
                FieldMaintenanceRevision.sequence == latest_field_revision.c.sequence,
            ),
        )
        .where(
            SourceFragment.document_version_id == batch.source_document_version_id,
            SourceDocument.name == filename,
        )
    )
    for locator, column, value in field_rows:
        if column is None:
            raise MasterWorkbookExportError("Un campo mantenido no tiene columna fuente.")
        sheet, row = _locator_coordinates(locator)
        key = (sheet, row, int(column))
        if key in patches:
            raise MasterWorkbookExportError(f"Hay varias revisiones para la misma celda: {key}.")
        patches[key] = value

    quarantine_rows = session.execute(
        select(
            QuarantinedSourceRow.source_locator,
            QuarantinedFieldMaintenanceRevision.source_column_index,
            QuarantinedFieldMaintenanceRevision.after_value,
        )
        .join(ImportBatch, ImportBatch.id == QuarantinedSourceRow.import_batch_id)
        .join(
            QuarantinedFieldMaintenanceRevision,
            QuarantinedFieldMaintenanceRevision.quarantined_row_id == QuarantinedSourceRow.id,
        )
        .where(ImportBatch.id == batch.id)
        .order_by(
            QuarantinedFieldMaintenanceRevision.quarantined_row_id,
            QuarantinedFieldMaintenanceRevision.source_column_index,
            QuarantinedFieldMaintenanceRevision.sequence,
        )
    )
    latest_quarantine: dict[tuple[str, int, int], str | None] = {}
    for locator, column, value in quarantine_rows:
        if "!" not in locator:
            raise MasterWorkbookExportError(
                f"Localizador de cuarentena inválido: {locator}."
            )
        sheet, row = locator.rsplit("!", 1)
        try:
            row_number = int(row)
        except ValueError as error:
            raise MasterWorkbookExportError(
                f"Localizador de cuarentena inválido: {locator}."
            ) from error
        if not sheet or row_number < 1:
            raise MasterWorkbookExportError(
                f"Localizador de cuarentena inválido: {locator}."
            )
        latest_quarantine[(sheet, row_number, int(column))] = value
    for key, value in latest_quarantine.items():
        existing = patches.get(key)
        if key in patches and existing != value:
            raise MasterWorkbookExportError(f"Conflicto de mantenimiento en la celda {key}.")
        patches[key] = value
    return patches


def export_master_workbook(
    session: Session,
    source: Path,
    destination: Path,
) -> MasterWorkbookExportResult:
    """Write a new workbook, preserving the source package and applying revisions only."""
    if source.is_symlink():
        raise MasterWorkbookExportError("No se aceptan enlaces simbólicos como origen.")
    source = source.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if not source.is_file() or source == destination:
        raise MasterWorkbookExportError("Origen inseguro o destino igual al original.")
    if source.name not in MASTER_WORKBOOKS:
        raise MasterWorkbookExportError(
            f"No es uno de los tres maestros soportados: {source.name}."
        )
    batch, source_hash = _source_batch(session, source)
    patches_by_cell = _maintenance_patches(session, batch, source.name)
    if destination.exists():
        raise MasterWorkbookExportError(f"No se sobrescribe un archivo existente: {destination}.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet_patches: defaultdict[str, dict[str, str | None]] = defaultdict(dict)
    for (sheet, row, column), value in patches_by_cell.items():
        sheet_patches[sheet][_reference(column, row)] = value

    try:
        with zipfile.ZipFile(source, "r") as original:
            sheet_paths = _workbook_sheets(original)
            unknown_sheets = set(sheet_patches) - set(sheet_paths)
            if unknown_sheets:
                raise MasterWorkbookExportError(
                    f"Hay cambios para hojas inexistentes: {sorted(unknown_sheets)}."
                )
            shared_path, shared_root, strings = _shared_strings(original)
            original_shared_count = len(strings)
            if shared_root is None and any(
                value not in (None, "")
                for group in sheet_patches.values()
                for value in group.values()
            ):
                # Missing cells are emitted as inline strings; shared-string cells cannot exist
                # without a shared-string table, so the source remains structurally valid.
                shared_indexes: dict[str, list[int]] = {}
            else:
                shared_indexes = defaultdict(list)
                for index, value in enumerate(strings):
                    shared_indexes[value].append(index)
            changed_by_path: dict[str, bytes] = {}
            changed_cells = 0
            for sheet_name, cell_patches in sheet_patches.items():
                path = sheet_paths[sheet_name]
                payload, changed = _apply_patches(
                    path,
                    original.read(path),
                    cell_patches,
                    strings,
                    shared_root,
                    shared_indexes,
                )
                changed_by_path[path] = payload
                changed_cells += changed

            shared_table_changed = len(strings) != original_shared_count or (
                changed_cells > 0
                and any(
                    value in (None, "")
                    for group in sheet_patches.values()
                    for value in group.values()
                )
            )
            if shared_root is not None and shared_table_changed:
                shared_references = 0
                for sheet_path in sheet_paths.values():
                    payload = changed_by_path.get(sheet_path) or original.read(sheet_path)
                    _register_namespaces(payload)
                    root = ET.fromstring(payload)
                    shared_references += sum(
                        1
                        for cell in root.iter(TAG("c"))
                        if cell.get("t") == "s" and cell.find(TAG("v")) is not None
                    )
                shared_root.set("count", str(shared_references))
                shared_root.set("uniqueCount", str(len(strings)))

            with zipfile.ZipFile(destination, "w") as output:
                for info in original.infolist():
                    payload = original.read(info.filename)
                    if info.filename in changed_by_path:
                        payload = changed_by_path[info.filename]
                    elif (
                        shared_path == info.filename
                        and shared_root is not None
                        and shared_table_changed
                    ):
                        payload = ET.tostring(shared_root, encoding="utf-8", xml_declaration=True)
                    output.writestr(copy.copy(info), payload)
    except MasterWorkbookExportError:
        destination.unlink(missing_ok=True)
        raise
    except (ET.ParseError, zipfile.BadZipFile, KeyError, OSError) as error:
        destination.unlink(missing_ok=True)
        raise MasterWorkbookExportError(f"No se pudo reconstruir {source.name}: {error}") from error

    if _sha256(source) != source_hash:
        destination.unlink(missing_ok=True)
        raise MasterWorkbookExportError("El libro original cambió durante la exportación.")
    try:
        with zipfile.ZipFile(destination) as output:
            bad_member = output.testzip()
            if bad_member is not None:
                raise MasterWorkbookExportError(
                    f"El paquete XLSX generado está dañado: {bad_member}."
                )
    except zipfile.BadZipFile as error:
        destination.unlink(missing_ok=True)
        raise MasterWorkbookExportError("El resultado no es un XLSX válido.") from error
    return MasterWorkbookExportResult(
        filename=source.name,
        output=destination,
        source_sha256=source_hash,
        output_sha256=_sha256(destination),
        changed_cells=changed_cells,
    )


def export_master_workbooks(
    session: Session,
    source_directory: Path,
    destination_directory: Path,
) -> tuple[MasterWorkbookExportResult, ...]:
    """Export all three masters to a new directory; never replace prior artifacts."""
    destination_directory = destination_directory.resolve(strict=False)
    if destination_directory.exists():
        raise MasterWorkbookExportError(
            f"No se sobrescribe el directorio de exportación existente: {destination_directory}."
        )
    source_directory = source_directory.resolve(strict=True)
    destination_directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".master-export-", dir=destination_directory.parent
    ) as temporary_directory:
        staging_directory = Path(temporary_directory) / "books"
        staging_directory.mkdir()
        results = tuple(
            export_master_workbook(
                session,
                source_directory / filename,
                staging_directory / filename,
            )
            for filename in MASTER_WORKBOOKS
        )
        # The destination is still required to be absent; rename publishes the
        # three-file set as one complete unit on the same filesystem.
        for attempt in range(5):
            try:
                staging_directory.rename(destination_directory)
                break
            except PermissionError as error:
                if destination_directory.exists() or attempt == 4:
                    raise MasterWorkbookExportError(
                        f"No se pudo publicar el conjunto de tres libros: {error}"
                    ) from error
                time.sleep(0.2 * (attempt + 1))
    return tuple(
        MasterWorkbookExportResult(
            filename=result.filename,
            output=destination_directory / result.filename,
            source_sha256=result.source_sha256,
            output_sha256=result.output_sha256,
            changed_cells=result.changed_cells,
        )
        for result in results
    )
