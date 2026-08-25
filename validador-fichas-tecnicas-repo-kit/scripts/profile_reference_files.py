#!/usr/bin/env python3
"""Generate an aggregate, reproducible profile of the seven reference XLSX files."""

from __future__ import annotations

import argparse
from array import array
import csv
import hashlib
import json
import math
import os
import platform
import re
import shutil
import sys
import tempfile
import uuid
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

try:
    from verify_reference_files import EXPECTED, RAW_DIR, sha256
except ModuleNotFoundError:
    from scripts.verify_reference_files import EXPECTED, RAW_DIR, sha256

CONTRACT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
TOOL_VERSION = "1.0.0"
XLSX_NAMES = tuple(name for name in EXPECTED if name.lower().endswith(".xlsx"))
MAX_ZIP_MEMBERS = 20_000
MAX_MEMBER_SIZE = 1_500_000_000
MAX_TOTAL_UNCOMPRESSED = 3_000_000_000
MAX_COMPRESSION_RATIO = 2_000
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
TAG = lambda name: f"{{{NS_MAIN}}}{name}"

WORKBOOK_IDS = {
    "Catalogo_campos_clinicos_medicamentos.xlsx": "catalogo_campos_clinicos",
    "Estudio carga maestros con IA.xlsx": "estudio_carga_maestros",
    "PrincipioActivoCargaMaster-22062026.xlsx": "principio_activo",
    "Medicamento-cargaMaster25062026.xlsx": "medicamento",
    "Especialidades-CargaMaster190626.xlsx": "especialidades",
    "Interacciones-cargaMaster250626.xlsx": "interacciones",
    "OMEPRAZOL 20 MGrelleno.xlsx": "omeprazol_roundtrip",
}

COLUMN_FIELDS = [
    "workbook_id", "sheet_id", "sheet_name", "column_index", "column_letter",
    "header_coordinate", "header_raw", "duplicate_header_ordinal", "first_observed_row",
    "last_observed_row", "material_value_count", "null_count", "formula_count", "error_count",
    "type_counts", "max_length", "cardinality", "cardinality_method", "duplicate_value_count",
    "candidate_key", "candidate_evidence",
]
INCIDENT_FIELDS = ["workbook_id", "sheet_id", "sheet_name", "code", "severity", "count", "evidence"]


class ProfilingError(RuntimeError):
    pass


def stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_id(*parts: object) -> str:
    return hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:24]


def column_index(reference: str) -> int:
    match = re.match(r"[A-Z]+", reference.upper())
    if not match:
        raise ProfilingError(f"Invalid cell reference: {reference}")
    result = 0
    for char in match.group(0):
        result = result * 26 + ord(char) - 64
    return result


def column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def csv_safe(value: object) -> tuple[str, bool]:
    text = "" if value is None else str(value)
    dangerous = bool(text) and text[0] in "=+-@\t\r"
    return (("'" + text) if dangerous else text, dangerous)


@dataclass
class Cardinality:
    exact: set[int] | None = field(default_factory=set)
    bitmap: bytearray | None = None
    count: int = 0

    def add(self, value: str) -> None:
        digest = int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big")
        self.count += 1
        if self.exact is not None:
            self.exact.add(digest)
            if len(self.exact) <= 100_000:
                return
            self.bitmap = bytearray((1 << 20) // 8)
            for item in self.exact:
                self._set(item % (1 << 20))
            self.exact = None
        self._set(digest % (1 << 20))

    def _set(self, bit: int) -> None:
        assert self.bitmap is not None
        self.bitmap[bit // 8] |= 1 << (bit % 8)

    def result(self) -> tuple[int, str]:
        if self.exact is not None:
            return len(self.exact), "exact_sha256_64"
        assert self.bitmap is not None
        occupied = sum(value.bit_count() for value in self.bitmap)
        zero = (1 << 20) - occupied
        estimate = (1 << 20) if zero == 0 else round(-(1 << 20) * math.log(zero / (1 << 20)))
        return estimate, "linear_counting_1048576_bits"


@dataclass
class ColumnStats:
    index: int
    first_row: int | None = None
    last_row: int | None = None
    material_count: int = 0
    formula_count: int = 0
    error_count: int = 0
    type_counts: Counter[str] = field(default_factory=Counter)
    max_length: int = 0
    cardinality: Cardinality = field(default_factory=Cardinality)

    def observe(self, row: int, observed_type: str, value: str, formula: str | None) -> None:
        self.first_row = row if self.first_row is None else min(self.first_row, row)
        self.last_row = row if self.last_row is None else max(self.last_row, row)
        self.material_count += 1
        self.type_counts[observed_type] += 1
        self.formula_count += int(formula is not None)
        self.error_count += int(observed_type == "error")
        self.max_length = max(self.max_length, len(value))
        self.cardinality.add(observed_type + "\x1e" + value)


def validate_xlsx(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ProfilingError(f"Input is not a regular file: {path.name}")
    total = 0
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            raise ProfilingError(f"Too many ZIP members: {path.name}")
        names = {member.filename for member in members}
        for member in members:
            pure = PurePosixPath(member.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in member.filename:
                raise ProfilingError(f"Unsafe ZIP path: {path.name}:{member.filename}")
            total += member.file_size
            if member.file_size > MAX_MEMBER_SIZE or total > MAX_TOTAL_UNCOMPRESSED:
                raise ProfilingError(f"Uncompressed size limit exceeded: {path.name}")
            if member.compress_size and member.file_size / member.compress_size > MAX_COMPRESSION_RATIO:
                raise ProfilingError(f"Compression ratio limit exceeded: {path.name}:{member.filename}")
            lower = member.filename.lower()
            if lower.endswith("vbaproject.bin") or "/embeddings/" in lower or "/activex/" in lower or "/oleobjects/" in lower or lower.endswith(".ole"):
                raise ProfilingError(f"Active content rejected: {path.name}:{member.filename}")
        if any(name.startswith("xl/externalLinks/") for name in names):
            raise ProfilingError(f"External workbook relationships rejected: {path.name}")


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    result: list[str] = []
    with archive.open("xl/sharedStrings.xml") as handle:
        for _event, element in ET.iterparse(handle, events=("end",)):
            if element.tag == TAG("si"):
                result.append("".join(node.text or "" for node in element.iter(TAG("t"))))
                element.clear()
    return result


def workbook_sheets(archive: zipfile.ZipFile) -> tuple[list[dict[str, object]], str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    properties = workbook.find(TAG("workbookPr"))
    date_system = "1904" if properties is not None and properties.get("date1904") == "1" else "1900"
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {item.get("Id"): item.get("Target", "") for item in relationships.findall(f"{{{NS_PKG_REL}}}Relationship")}
    sheets_element = workbook.find(TAG("sheets"))
    sheets: list[dict[str, object]] = []
    for ordinal, sheet in enumerate([] if sheets_element is None else sheets_element, start=1):
        target = targets.get(sheet.get(f"{{{NS_REL}}}id"), "")
        path = str(PurePosixPath("xl") / target).replace("xl/../", "")
        sheets.append({"name": sheet.get("name", ""), "ordinal": ordinal, "visibility": sheet.get("state", "visible"), "path": path})
    return sheets, date_system


def read_cell(cell: ET.Element, strings: list[str]) -> tuple[str, str, str | None, bool]:
    cell_type = cell.get("t")
    formula_element = cell.find(TAG("f"))
    value_element = cell.find(TAG("v"))
    formula = formula_element.text if formula_element is not None else None
    cached = value_element.text if value_element is not None else None
    if cell_type == "inlineStr":
        return "inline_string", "".join(node.text or "" for node in cell.iter(TAG("t"))), formula, True
    if cell_type == "s" and cached is not None:
        try:
            return "shared_string", strings[int(cached)], formula, True
        except (ValueError, IndexError) as error:
            raise ProfilingError(f"Invalid shared string index: {cached}") from error
    if cell_type == "str":
        return "string", cached or "", formula, True
    if cell_type == "b":
        return "boolean", cached or "", formula, True
    if cell_type == "e":
        return "error", cached or "", formula, True
    if cell_type == "d":
        return "date_iso", cached or "", formula, True
    if formula is not None:
        return "formula", cached or "", formula, True
    if cached is None:
        return "styled_blank", "", None, False
    return "number", cached, None, True


def profile_sheet(archive: zipfile.ZipFile, workbook_id: str, sheet: dict[str, object], strings: list[str]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    sheet_name = str(sheet["name"])
    sheet_id = stable_id(workbook_id, sheet_name, sheet["ordinal"])
    columns: dict[int, ColumnStats] = {}
    material_rows = 0
    physical_rows = 0
    dimension: str | None = None
    merged_count = 0
    header_row: int | None = None
    headers: dict[int, str] = {}
    header_counts: Counter[str] = Counter()
    formula_without_cache = 0
    row_fingerprints = Cardinality()
    current_row = 0
    row_values: list[tuple[int, str, str]] = []

    def finish_row() -> None:
        nonlocal material_rows, header_row, headers
        if not row_values:
            return
        material_rows += 1
        row_fingerprints.add(stable_json(row_values))
        if header_row is None and len(row_values) >= 2:
            header_row = current_row
            headers = {index: value for index, observed_type, value in row_values if observed_type in ("shared_string", "inline_string", "string")}
            header_counts.update(headers.values())

    with archive.open(str(sheet["path"])) as handle:
        for event, element in ET.iterparse(handle, events=("start", "end")):
            if event == "start" and element.tag == TAG("row"):
                current_row = int(element.get("r", "0"))
                row_values = []
                physical_rows += 1
            elif event == "end" and element.tag == TAG("row"):
                finish_row()
                row_values = []
                element.clear()
            elif event == "end" and element.tag == TAG("dimension"):
                dimension = element.get("ref")
            elif event == "end" and element.tag == TAG("mergeCell"):
                merged_count += 1
            elif event == "end" and element.tag == TAG("c"):
                reference = element.get("r", "")
                observed_type, value, formula, material = read_cell(element, strings)
                if material:
                    index = column_index(reference)
                    columns.setdefault(index, ColumnStats(index)).observe(current_row, observed_type, value, formula)
                    row_values.append((index, observed_type, value))
                    formula_without_cache += int(formula is not None and not value)
                element.clear()

    distinct_rows, row_method = row_fingerprints.result()
    sheet_summary = {
        "sheet_id": sheet_id, "name": sheet_name, "ordinal": sheet["ordinal"], "visibility": sheet["visibility"],
        "dimension_declared": dimension, "physical_rows": physical_rows, "material_rows": material_rows,
        "observed_columns": len(columns), "header_candidate_row": header_row, "merged_ranges_count": merged_count,
        "duplicate_rows": max(0, material_rows - distinct_rows), "duplicate_rows_method": row_method,
    }
    column_rows: list[dict[str, object]] = []
    duplicate_ordinals: Counter[str] = Counter()
    for index in sorted(columns):
        stats = columns[index]
        header = headers.get(index, "")
        duplicate_ordinals[header] += 1
        cardinality, method = stats.cardinality.result()
        null_count = max(0, material_rows - stats.material_count)
        candidate = null_count == 0 and cardinality == stats.material_count and method.startswith("exact")
        column_rows.append({
            "workbook_id": workbook_id, "sheet_id": sheet_id, "sheet_name": sheet_name, "column_index": index,
            "column_letter": column_letter(index), "header_coordinate": f"{column_letter(index)}{header_row}" if header_row else "",
            "header_raw": header, "duplicate_header_ordinal": duplicate_ordinals[header], "first_observed_row": stats.first_row,
            "last_observed_row": stats.last_row, "material_value_count": stats.material_count, "null_count": null_count,
            "formula_count": stats.formula_count, "error_count": stats.error_count,
            "type_counts": stable_json(dict(sorted(stats.type_counts.items()))), "max_length": stats.max_length,
            "cardinality": cardinality, "cardinality_method": method,
            "duplicate_value_count": max(0, stats.material_count - cardinality), "candidate_key": str(candidate).lower(),
            "candidate_evidence": "observation_only_not_D004_decision" if candidate else "",
        })
    incidents: list[dict[str, object]] = []
    for code, severity, count, evidence in (
        ("FORMULA_WITHOUT_CACHE", "warning", formula_without_cache, "formulas_not_recalculated"),
        ("DUPLICATE_HEADER", "warning", sum(value - 1 for value in header_counts.values() if value > 1), "headers_preserved_with_ordinal"),
        ("DUPLICATE_ROW", "info", sheet_summary["duplicate_rows"], row_method),
    ):
        if count:
            incidents.append({"workbook_id": workbook_id, "sheet_id": sheet_id, "sheet_name": sheet_name, "code": code, "severity": severity, "count": count, "evidence": evidence})
    return sheet_summary, column_rows, incidents


def verify_inputs(raw_dir: Path) -> list[dict[str, object]]:
    inputs = []
    for ordinal, name in enumerate(XLSX_NAMES, start=1):
        path = raw_dir / name
        if not path.is_file() or path.is_symlink() or sha256(path) != EXPECTED[name]:
            raise ProfilingError(f"Missing, unsafe or changed input: {name}")
        inputs.append({"workbook_id": WORKBOOK_IDS[name], "path": f"data/reference/raw/{name}", "size": path.stat().st_size, "sha256": EXPECTED[name], "ordinal": ordinal})
    return inputs


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            safe_row = dict(row)
            for key, value in safe_row.items():
                if isinstance(value, str):
                    safe_row[key] = csv_safe(value)[0]
            writer.writerow(safe_row)


def artifact_hashes(root: Path, paths: list[Path]) -> list[dict[str, object]]:
    return [{"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": sha256(path)} for path in paths]


def run_profile(raw_dir: Path, output_dir: Path) -> dict[str, object]:
    inputs_before = verify_inputs(raw_dir)
    config = {"contract_version": CONTRACT_VERSION, "inputs": [(item["workbook_id"], item["sha256"]) for item in inputs_before], "cardinality": "exact_to_100000_then_linear_counting", "relations": "deferred_DEV004_DEV006"}
    configuration_hash = hashlib.sha256(stable_json(config).encode()).hexdigest()
    run_id = str(uuid.UUID(hashlib.md5(configuration_hash.encode(), usedforsecurity=False).hexdigest()))
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ProfilingError(f"Output directory already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    started = datetime.now(UTC)
    try:
        workbook_dir = staging / "workbooks"
        workbook_dir.mkdir()
        all_columns: list[dict[str, object]] = []
        all_incidents: list[dict[str, object]] = []
        workbook_summaries: list[dict[str, object]] = []
        structural_paths: list[Path] = []
        for item in inputs_before:
            source = raw_dir / Path(str(item["path"])).name
            validate_xlsx(source)
            with zipfile.ZipFile(source) as archive:
                strings = shared_strings(archive)
                sheets, date_system = workbook_sheets(archive)
                summaries = []
                workbook_columns = []
                for sheet in sheets:
                    summary, columns, incidents = profile_sheet(archive, str(item["workbook_id"]), sheet, strings)
                    summaries.append(summary)
                    workbook_columns.extend(columns)
                    all_incidents.extend(incidents)
                payload = {"schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION, "workbook_id": item["workbook_id"], "filename": source.name, "sha256": item["sha256"], "date_system": date_system, "sheets": summaries, "columns": workbook_columns, "relations_detail": "deferred_to_DEV004_DEV006"}
                path = workbook_dir / f"{item['workbook_id']}.json"
                path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
                structural_paths.append(path)
                all_columns.extend(workbook_columns)
                workbook_summaries.append({"workbook_id": item["workbook_id"], "filename": source.name, "sheets": summaries})
        columns_path = staging / "columns.csv"
        incidents_path = staging / "incidents-summary.csv"
        write_csv(columns_path, COLUMN_FIELDS, all_columns)
        write_csv(incidents_path, INCIDENT_FIELDS, all_incidents)
        structural_paths.extend([columns_path, incidents_path])
        reproducible_hash = hashlib.sha256(stable_json([(path.relative_to(staging).as_posix(), sha256(path)) for path in structural_paths]).encode()).hexdigest()
        summary_lines = ["# Resumen del perfilado agregado", "", f"- Hash reproducible: `{reproducible_hash}`", "- Libros: 7", f"- Columnas perfiladas: {len(all_columns)}", f"- Incidencias agregadas: {sum(int(item['count']) for item in all_incidents)}", "- Originales modificados: no", "- Relaciones detalladas y huérfanos: pendientes de DEV-004/DEV-006.", ""]
        for workbook in workbook_summaries:
            summary_lines.extend([f"## {workbook['filename']}", "", "| Hoja | Filas físicas | Filas materiales | Columnas | Duplicados |", "|---|---:|---:|---:|---:|"])
            for sheet in workbook["sheets"]:
                summary_lines.append(f"| {sheet['name']} | {sheet['physical_rows']} | {sheet['material_rows']} | {sheet['observed_columns']} | {sheet['duplicate_rows']} |")
            summary_lines.append("")
        summary_path = staging / "summary.md"
        summary_path.write_text("\n".join(summary_lines), encoding="utf-8", newline="\n")
        inputs_after = verify_inputs(raw_dir)
        if inputs_before != inputs_after:
            raise ProfilingError("Reference metadata changed during profiling")
        finished = datetime.now(UTC)
        outputs = artifact_hashes(staging, structural_paths + [summary_path])
        manifest = {"schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION, "run_id": run_id, "started_at": started.isoformat(), "finished_at": finished.isoformat(), "duration_seconds": round((finished - started).total_seconds(), 3), "tool": {"name": "profile_reference_files", "version": TOOL_VERSION, "commit": os.environ.get("GIT_COMMIT", "unavailable")}, "runtime": {"python": platform.python_version(), "os": platform.system()}, "configuration_hash": configuration_hash, "inputs": inputs_before, "outputs": outputs, "status": "completed_with_incidents" if all_incidents else "completed", "exit_code": 0, "source_files_modified": False, "input_hashes_after": [item["sha256"] for item in inputs_after], "reproducible_content_hash": reproducible_hash, "relations_detail": "deferred_to_DEV004_DEV006"}
        (staging / "run-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        staging.replace(output_dir)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = run_profile(args.raw_dir.resolve(), args.output)
    except (OSError, ET.ParseError, zipfile.BadZipFile, ProfilingError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK 7/7 workbooks -> {args.output}")
    print(f"duration_seconds={manifest['duration_seconds']}")
    print(f"reproducible_content_hash={manifest['reproducible_content_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
