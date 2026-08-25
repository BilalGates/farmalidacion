#!/usr/bin/env python3
"""Execute the reversible DEV-008 OOXML round-trip spike."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from import_omeprazole_fixture import SHEET_ROLES, SOURCE_NAME, build_snapshot
    from profile_reference_files import NS_MAIN, TAG, read_cell, shared_strings, stable_id, stable_json, validate_xlsx, workbook_sheets
    from verify_reference_files import EXPECTED, RAW_DIR, sha256
except ModuleNotFoundError:
    from scripts.import_omeprazole_fixture import SHEET_ROLES, SOURCE_NAME, build_snapshot
    from scripts.profile_reference_files import NS_MAIN, TAG, read_cell, shared_strings, stable_id, stable_json, validate_xlsx, workbook_sheets
    from scripts.verify_reference_files import EXPECTED, RAW_DIR, sha256

SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "DEV-008-1.0.0"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


class RoundTripError(RuntimeError):
    pass


def _zip_write(archive: zipfile.ZipFile, source_info: zipfile.ZipInfo, payload: bytes) -> None:
    info = copy.copy(source_info)
    archive.writestr(info, payload)


def _payload(cell: ET.Element) -> tuple[str | None, str | None, str | None, dict[str, str]]:
    formula = cell.find(TAG("f"))
    value = cell.find(TAG("v"))
    return cell.get("t"), cell.get("s"), None if value is None else value.text, {} if formula is None else dict(formula.attrib)


def _enriched_cells(archive: zipfile.ZipFile, sheet: dict[str, object], strings: list[str]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    root = ET.fromstring(archive.read(str(sheet["path"])))
    for cell in root.iter(TAG("c")):
        observed_type, raw_value, formula, material = read_cell(cell, strings)
        if not material:
            continue
        source_type, style_index, stored_value, formula_attributes = _payload(cell)
        result[str(cell.get("r"))] = {
            "observed_type": observed_type,
            "raw_value": raw_value,
            "formula": formula,
            "source_cell_type": source_type,
            "style_index": style_index,
            "stored_value": stored_value,
            "value_element_present": cell.find(TAG("v")) is not None,
            "formula_attributes": formula_attributes,
        }
    return result


def _structure_fingerprint(archive: zipfile.ZipFile, sheet: dict[str, object], strings: list[str]) -> str:
    root = ET.fromstring(archive.read(str(sheet["path"])))
    for cell in root.iter(TAG("c")):
        _kind, _value, _formula, material = read_cell(cell, strings)
        if material:
            for child in list(cell):
                if child.tag in (TAG("v"), TAG("f"), TAG("is")):
                    cell.remove(child)
    return hashlib.sha256(ET.tostring(root, encoding="utf-8")).hexdigest()


def _restore_cell(cell: ET.Element, canonical: dict[str, object], shared_indexes: dict[str, list[int]], original_stored: str | None) -> None:
    for child in list(cell):
        if child.tag in (TAG("v"), TAG("f"), TAG("is")):
            cell.remove(child)
    kind = str(canonical["observed_type"])
    raw = str(canonical["raw_value"])
    formula = canonical.get("formula")
    if kind == "inline_string":
        cell.set("t", "inlineStr")
        inline = ET.SubElement(cell, TAG("is"))
        text = ET.SubElement(inline, TAG("t"), {XML_SPACE: "preserve"})
        text.text = raw
        return
    type_map = {"shared_string": "s", "string": "str", "boolean": "b", "error": "e", "date_iso": "d"}
    if kind in type_map:
        cell.set("t", type_map[kind])
    elif "t" in cell.attrib:
        del cell.attrib["t"]
    if formula is not None:
        ET.SubElement(cell, TAG("f")).text = str(formula)
    if kind == "shared_string":
        candidates = shared_indexes.get(raw, [])
        if original_stored is not None and int(original_stored) in candidates:
            stored = original_stored
        elif len(candidates) == 1:
            stored = str(candidates[0])
        else:
            raise RoundTripError("Shared-string identity is ambiguous")
    else:
        stored = raw
    ET.SubElement(cell, TAG("v")).text = stored


def reconstruct(source: Path, snapshot: dict[str, object], destination: Path) -> None:
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w") as output:
        strings = shared_strings(original)
        shared_indexes: dict[str, list[int]] = defaultdict(list)
        for index, text in enumerate(strings):
            shared_indexes[text].append(index)
        sheets, _date_system = workbook_sheets(original)
        canonical_by_sheet = {str(sheet["name"]): {str(value["coordinate"]): value for occurrence in sheet["occurrences"] for value in occurrence["values"]} for sheet in snapshot["sheets"]}
        sheet_paths = {str(sheet["path"]): sheet for sheet in sheets}
        for info in original.infolist():
            payload = original.read(info.filename)
            if info.filename in sheet_paths:
                sheet = sheet_paths[info.filename]
                root = ET.fromstring(payload)
                expected = canonical_by_sheet[str(sheet["name"])]
                restored: set[str] = set()
                for cell in root.iter(TAG("c")):
                    coordinate = str(cell.get("r"))
                    if coordinate not in expected:
                        continue
                    _cell_type, _style, stored, _formula_attrs = _payload(cell)
                    _restore_cell(cell, expected[coordinate], shared_indexes, stored)
                    restored.add(coordinate)
                if restored != set(expected):
                    raise RoundTripError(f"Cannot align all material cells in {sheet['name']}")
                payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            _zip_write(output, info, payload)
    validate_xlsx(destination)


def compare_packages(source: Path, output: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    differences: list[dict[str, object]] = []
    sheets_report: list[dict[str, object]] = []
    with zipfile.ZipFile(source) as left, zipfile.ZipFile(output) as right:
        left_strings, right_strings = shared_strings(left), shared_strings(right)
        left_sheets, left_dates = workbook_sheets(left)
        right_sheets, right_dates = workbook_sheets(right)
        if [(s["name"], s["ordinal"], s["visibility"]) for s in left_sheets] != [(s["name"], s["ordinal"], s["visibility"]) for s in right_sheets] or left_dates != right_dates:
            differences.append({"difference_id": stable_id("workbook_structure"), "category": "defect", "code": "workbook_structure_changed"})
        left_names, right_names = set(left.namelist()), set(right.namelist())
        if left_names != right_names:
            differences.append({"difference_id": stable_id("package_parts"), "category": "defect", "code": "package_parts_changed"})
        worksheet_paths = {str(sheet["path"]) for sheet in left_sheets}
        for name in sorted(left_names & right_names - worksheet_paths):
            if left.read(name) != right.read(name):
                differences.append({"difference_id": stable_id("part", name), "category": "defect", "code": "auxiliary_part_changed", "part": name})
        for index, source_sheet in enumerate(left_sheets):
            output_sheet = right_sheets[index]
            source_cells = _enriched_cells(left, source_sheet, left_strings)
            output_cells = _enriched_cells(right, output_sheet, right_strings)
            for coordinate in sorted(set(source_cells) | set(output_cells)):
                before, after = source_cells.get(coordinate), output_cells.get(coordinate)
                if before != after:
                    differences.append({"difference_id": stable_id(source_sheet["name"], coordinate), "category": "defect", "code": "material_cell_changed", "location": {"sheet": source_sheet["name"], "coordinate": coordinate}, "source": before, "output": after})
            source_structure = _structure_fingerprint(left, source_sheet, left_strings)
            output_structure = _structure_fingerprint(right, output_sheet, right_strings)
            if source_structure != output_structure:
                differences.append({"difference_id": stable_id("structure", source_sheet["name"]), "category": "defect", "code": "sheet_structure_changed", "sheet": source_sheet["name"]})
            sheets_report.append({"ordinal": source_sheet["ordinal"], "name": source_sheet["name"], "source_values": len(source_cells), "output_values": len(output_cells), "structure_equal": source_structure == output_structure})
    return differences, sheets_report


def run_roundtrip(source: Path, output_dir: Path, expected_sha: str = EXPECTED[SOURCE_NAME], sheet_roles: dict[str, tuple[str, str]] = SHEET_ROLES) -> dict[str, object]:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise RoundTripError(f"Output directory already exists: {output_dir}")
    before = sha256(source)
    if before != expected_sha:
        raise RoundTripError("Source hash does not match the approved fixture")
    snapshot = build_snapshot(source.resolve(), expected_sha, sheet_roles)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    try:
        reconstructed = staging / "reconstructed.xlsx"
        reconstruct(source, snapshot, reconstructed)
        differences, sheets = compare_packages(source, reconstructed)
        after = sha256(source)
        if after != before:
            raise RoundTripError("Source changed during round-trip")
        report = {"schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION, "status": "pass" if not differences else "fail", "exit_code": 0 if not differences else 1, "source": {"filename": source.name, "sha256_before": before, "sha256_after": after, "modified": False}, "output": {"filename": reconstructed.name, "sha256": sha256(reconstructed)}, "comparison_scope": "material_cells_and_complete_source_package_structure", "authorized_normalizations": [], "sheets": sheets, "differences": differences, "difference_totals": {"defect": len(differences), "unresolved": 0, "order_only": 0, "format_only": 0, "authorized_normalization": 0}}
        report_path = staging / "omeprazole-roundtrip-report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        lines = ["# DEV-008 — Round-trip semántico de omeprazol", "", f"- Resultado: `{report['status']}`", f"- Hojas: {len(sheets)}/22", f"- Diferencias: {len(differences)}", "- Normalizaciones aplicadas: 0", "- Original modificado: no", "", "| # | Hoja | Valores origen/salida | Estructura |", "|---:|---|---:|---|"]
        lines.extend(f"| {item['ordinal']} | {item['name']} | {item['source_values']}/{item['output_values']} | {'igual' if item['structure_equal'] else 'diferente'} |" for item in sheets)
        markdown = staging / "omeprazole-roundtrip-report.md"
        markdown.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        structural = [reconstructed, report_path, markdown]
        reproducible_hash = hashlib.sha256(stable_json([(path.name, sha256(path)) for path in structural]).encode()).hexdigest()
        manifest = {"schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION, "status": report["status"], "exit_code": report["exit_code"], "difference_count": len(differences), "reproducible_content_hash": reproducible_hash, "outputs": [path.name for path in structural]}
        (staging / "run-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        staging.replace(output_dir)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=RAW_DIR / SOURCE_NAME)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_roundtrip(args.source, args.output)
    except (OSError, ET.ParseError, zipfile.BadZipFile, RoundTripError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"{result['status'].upper()} differences={result['difference_count']}")
    print(f"reproducible_content_hash={result['reproducible_content_hash']}")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
