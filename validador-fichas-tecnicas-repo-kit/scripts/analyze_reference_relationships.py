#!/usr/bin/env python3
"""Analyze configured Excel keys and parent-child cardinalities without row dumps."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from profile_reference_files import TAG, column_index, read_cell, shared_strings, stable_json, validate_xlsx, workbook_sheets
    from verify_reference_files import EXPECTED, RAW_DIR, sha256
except ModuleNotFoundError:
    from scripts.profile_reference_files import TAG, column_index, read_cell, shared_strings, stable_json, validate_xlsx, workbook_sheets
    from scripts.verify_reference_files import EXPECTED, RAW_DIR, sha256

SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class SheetSpec:
    workbook: str
    sheet: str
    key_candidates: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class RelationSpec:
    relation_id: str
    workbook: str
    parent_sheet: str
    child_sheet: str
    parent_columns: tuple[str, ...]
    child_columns: tuple[str, ...]


SHEET_SPECS = (
    SheetSpec("PrincipioActivoCargaMaster-22062026.xlsx", "General", (("IDEXTERNO",), ("ID_PRINCIPIO_ACTIVO",), ("IDEXTERNO", "ID_PRINCIPIO_ACTIVO"))),
    SheetSpec("PrincipioActivoCargaMaster-22062026.xlsx", "Frecuencia", (("PA_IDEXTERNO", "FQ_IDEXTERNO"), ("ID_PRINCIPIO_ACTIVO", "FQ_ID_FRECUENCIA"))),
    SheetSpec("PrincipioActivoCargaMaster-22062026.xlsx", "Via", (("PA_IDEXTERNO", "VIA_IDEXTERNO"), ("ID_PRINCIPIO_ACTIVO", "VIA_ID_VIA"))),
    SheetSpec("PrincipioActivoCargaMaster-22062026.xlsx", "ConsejosAdministracion", (("PA_IDEXTERNO", "VIA_IDEXTERNO", "FF_IDEXTERNO", "TIP_IDEXTERNO"),)),
    SheetSpec("PrincipioActivoCargaMaster-22062026.xlsx", "DatosAnaliticos", (("PA_IDEXTERNO", "DA_IDEXTERNO", "AD_IDEXTERNO"),)),
    SheetSpec("Medicamento-cargaMaster25062026.xlsx", "General", (("MED_IDEXTERNO",), ("ID_MEDICAMENTO",), ("MED_IDEXTERNO", "ID_MEDICAMENTO"))),
    SheetSpec("Medicamento-cargaMaster25062026.xlsx", "Composicion", (("MED_IDEXTERNO", "PA_IDEXTERNO"), ("ID_MEDICAMENTO", "PA_ID_PRINCIPIO_ACTIVO"))),
    SheetSpec("Medicamento-cargaMaster25062026.xlsx", "Indicacion", (("MED_IDEXTERNO", "IN_IDEXTERNO"), ("ID_MEDICAMENTO", "IN_ID_INDICACION"))),
    SheetSpec("Medicamento-cargaMaster25062026.xlsx", "Frecuencia", (("MED_IDEXTERNO", "FQ_IDEXTERNO"), ("ID_MEDICAMENTO", "FQ_ID_FRECUENCIA"))),
    SheetSpec("Medicamento-cargaMaster25062026.xlsx", "Via", (("MED_IDEXTERNO", "VIA_IDEXTERNO"), ("ID_MEDICAMENTO", "VIA_ID_VIA"))),
    SheetSpec("Medicamento-cargaMaster25062026.xlsx", "Prescripcion", (("GRUPO_POBLACIONAL", "MED_IDEXTERNO", "FQ_IDEXTERNO", "VIA_IDEXTERNO"),)),
    SheetSpec("Medicamento-cargaMaster25062026.xlsx", "Links", (("LI_IDEXTERNO",), ("MED_IDEXTERNO", "LI_IDEXTERNO"))),
    SheetSpec("Especialidades-CargaMaster190626.xlsx", "General", (("BN_IDEXTERNO",), ("ID_ESPECIALIDAD",), ("CODIGO_NACIONAL",), ("BN_IDEXTERNO", "ID_ESPECIALIDAD"))),
    SheetSpec("Especialidades-CargaMaster190626.xlsx", "Excipientes", (("BN_IDEXTERNO", "EX_IDEXTERNO"), ("ID_ESPECIALIDAD", "EX_ID_EXCIPIENTE"), ("CODIGO_NACIONAL", "EX_IDEXTERNO"))),
    SheetSpec("Interacciones-cargaMaster250626.xlsx", "General", (("IDEXTERNO",), ("ID_INTERACCION",), ("IDEXTERNO", "ID_INTERACCION"))),
    SheetSpec("Interacciones-cargaMaster250626.xlsx", "AplicaA", (("IN_IDEXTERNO", "IDEXTERNO"), ("IN_ID_INTERACCION", "ID_INTERACCION_GRUPO_POBLACIONAL"))),
)

RELATION_SPECS = (
    RelationSpec("pa_frecuencia", "PrincipioActivoCargaMaster-22062026.xlsx", "General", "Frecuencia", ("IDEXTERNO",), ("PA_IDEXTERNO",)),
    RelationSpec("pa_via", "PrincipioActivoCargaMaster-22062026.xlsx", "General", "Via", ("IDEXTERNO",), ("PA_IDEXTERNO",)),
    RelationSpec("pa_consejo", "PrincipioActivoCargaMaster-22062026.xlsx", "General", "ConsejosAdministracion", ("IDEXTERNO",), ("PA_IDEXTERNO",)),
    RelationSpec("pa_dato_analitico", "PrincipioActivoCargaMaster-22062026.xlsx", "General", "DatosAnaliticos", ("IDEXTERNO",), ("PA_IDEXTERNO",)),
    RelationSpec("med_composicion", "Medicamento-cargaMaster25062026.xlsx", "General", "Composicion", ("MED_IDEXTERNO",), ("MED_IDEXTERNO",)),
    RelationSpec("med_indicacion", "Medicamento-cargaMaster25062026.xlsx", "General", "Indicacion", ("MED_IDEXTERNO",), ("MED_IDEXTERNO",)),
    RelationSpec("med_frecuencia", "Medicamento-cargaMaster25062026.xlsx", "General", "Frecuencia", ("MED_IDEXTERNO",), ("MED_IDEXTERNO",)),
    RelationSpec("med_via", "Medicamento-cargaMaster25062026.xlsx", "General", "Via", ("MED_IDEXTERNO",), ("MED_IDEXTERNO",)),
    RelationSpec("med_prescripcion", "Medicamento-cargaMaster25062026.xlsx", "General", "Prescripcion", ("MED_IDEXTERNO",), ("MED_IDEXTERNO",)),
    RelationSpec("med_link", "Medicamento-cargaMaster25062026.xlsx", "General", "Links", ("MED_IDEXTERNO",), ("MED_IDEXTERNO",)),
    RelationSpec("esp_excipiente", "Especialidades-CargaMaster190626.xlsx", "General", "Excipientes", ("BN_IDEXTERNO",), ("BN_IDEXTERNO",)),
    RelationSpec("interaccion_aplica_a", "Interacciones-cargaMaster250626.xlsx", "General", "AplicaA", ("IDEXTERNO",), ("IN_IDEXTERNO",)),
)


class RelationshipAnalysisError(RuntimeError):
    pass


def iter_rows(archive: zipfile.ZipFile, sheet: dict[str, object], strings: list[str]):
    with archive.open(str(sheet["path"])) as handle:
        row: dict[int, str] = {}
        for event, element in ET.iterparse(handle, events=("start", "end")):
            if event == "start" and element.tag == TAG("row"):
                row = {}
            elif event == "end" and element.tag == TAG("c"):
                value_type, value, _formula, material = read_cell(element, strings)
                if material:
                    row[column_index(element.get("r", ""))] = value_type + "\x1e" + value
                element.clear()
            elif event == "end" and element.tag == TAG("row"):
                if row:
                    yield row
                element.clear()


def read_selected_sheets(path: Path, names: set[str]) -> dict[str, list[dict[str, str]]]:
    validate_xlsx(path)
    result: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        sheets, _date_system = workbook_sheets(archive)
        for sheet in sheets:
            name = str(sheet["name"])
            if name not in names:
                continue
            rows = iter_rows(archive, sheet, strings)
            try:
                header_row = next(rows)
            except StopIteration:
                result[name] = []
                continue
            headers = {index: value.split("\x1e", 1)[1] for index, value in header_row.items()}
            header_counts = Counter(headers.values())
            if any(count > 1 for count in header_counts.values()):
                headers = {index: (f"{value}#{sum(1 for previous in headers if previous <= index and headers[previous] == value)}" if header_counts[value] > 1 else value) for index, value in headers.items()}
            result[name] = [{headers[index]: encoded.split("\x1e", 1)[1] for index, encoded in row.items() if index in headers} for row in rows]
    return result


def key_result(workbook: str, sheet: str, rows: list[dict[str, str]], columns: tuple[str, ...]) -> dict[str, object]:
    values = [tuple(row.get(column, "") for column in columns) for row in rows]
    complete = [value for value in values if all(part != "" for part in value)]
    distinct = len(set(complete))
    return {
        "workbook": workbook, "sheet": sheet, "columns": "+".join(columns), "rows": len(rows),
        "complete_rows": len(complete), "incomplete_rows": len(rows) - len(complete),
        "distinct_complete": distinct, "duplicate_complete": len(complete) - distinct,
        "candidate": "observed_unique" if len(rows) > 0 and len(complete) == len(rows) and distinct == len(rows) else "rejected_by_observation",
        "decision_status": "hypothesis_not_D004_accepted",
    }


def relation_result(spec: RelationSpec, sheets: dict[str, list[dict[str, str]]]) -> dict[str, object]:
    parents = [tuple(row.get(column, "") for column in spec.parent_columns) for row in sheets[spec.parent_sheet]]
    children = [tuple(row.get(column, "") for column in spec.child_columns) for row in sheets[spec.child_sheet]]
    parent_complete = [key for key in parents if all(key)]
    child_complete = [key for key in children if all(key)]
    parent_set = set(parent_complete)
    counts = Counter(key for key in child_complete if key in parent_set)
    distribution = Counter(counts.get(key, 0) for key in parent_set)
    maximum = max(distribution, default=0)
    minimum = min(distribution, default=0)
    orphan_keys = [key for key in child_complete if key not in parent_set]
    return {
        "relation_id": spec.relation_id, "workbook": spec.workbook, "parent_sheet": spec.parent_sheet,
        "child_sheet": spec.child_sheet, "parent_columns": "+".join(spec.parent_columns),
        "child_columns": "+".join(spec.child_columns), "parent_rows": len(parents),
        "parent_complete": len(parent_complete), "parent_duplicate_keys": len(parent_complete) - len(parent_set),
        "child_rows": len(children), "child_complete": len(child_complete),
        "child_incomplete": len(children) - len(child_complete),
        "orphan_rows": len(orphan_keys), "orphan_distinct_keys": len(set(orphan_keys)),
        "parents_without_children": distribution.get(0, 0), "min_children_observed": minimum,
        "max_children_observed": maximum, "parents_with_multiple_children": sum(count for size, count in distribution.items() if size > 1),
        "observed_cardinality": f"{minimum}..{maximum}", "decision_status": "observation_not_canonical_decision",
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)


def run_analysis(raw_dir: Path, output_dir: Path) -> dict[str, object]:
    if output_dir.exists():
        raise RelationshipAnalysisError(f"Output directory already exists: {output_dir}")
    required = sorted({spec.workbook for spec in SHEET_SPECS})
    inputs = []
    all_sheets: dict[str, dict[str, list[dict[str, str]]]] = {}
    for workbook in required:
        path = raw_dir / workbook
        if not path.is_file() or sha256(path) != EXPECTED[workbook]:
            raise RelationshipAnalysisError(f"Missing or changed input: {workbook}")
        names = {spec.sheet for spec in SHEET_SPECS if spec.workbook == workbook}
        all_sheets[workbook] = read_selected_sheets(path, names)
        inputs.append({"filename": workbook, "sha256": EXPECTED[workbook]})
    keys = [key_result(spec.workbook, spec.sheet, all_sheets[spec.workbook][spec.sheet], columns) for spec in SHEET_SPECS for columns in spec.key_candidates]
    relations = [relation_result(spec, all_sheets[spec.workbook]) for spec in RELATION_SPECS]
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    try:
        keys_path, relations_path = staging / "candidate-keys.csv", staging / "relations-summary.csv"
        write_csv(keys_path, keys)
        write_csv(relations_path, relations)
        content_hash = hashlib.sha256(stable_json({"inputs": inputs, "keys": keys, "relations": relations}).encode()).hexdigest()
        summary = ["# DEV-004 — Cardinalidades y claves observadas", "", f"- Hash reproducible: `{content_hash}`", f"- Hipótesis de clave evaluadas: {len(keys)}", f"- Relaciones dirigidas evaluadas: {len(relations)}", f"- Claves únicas observadas: {sum(row['candidate'] == 'observed_unique' for row in keys)}", f"- Huérfanos observados: {sum(int(row['orphan_rows']) for row in relations)}", "- Estado: evidencia reproducible; ninguna clave queda aceptada automáticamente.", "", "| Relación | Cardinalidad observada | Huérfanos | Padres sin hijos |", "|---|---:|---:|---:|"]
        summary.extend(f"| {row['relation_id']} | {row['observed_cardinality']} | {row['orphan_rows']} | {row['parents_without_children']} |" for row in relations)
        (staging / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8", newline="\n")
        manifest = {"schema_version": SCHEMA_VERSION, "inputs": inputs, "outputs": ["candidate-keys.csv", "relations-summary.csv", "summary.md"], "reproducible_content_hash": content_hash, "source_files_modified": False, "decision_status": "D-004_proposed_not_accepted"}
        (staging / "run-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        if any(sha256(raw_dir / item["filename"]) != item["sha256"] for item in inputs):
            raise RelationshipAnalysisError("Input changed during analysis")
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
        manifest = run_analysis(args.raw_dir.resolve(), args.output.resolve())
    except (OSError, ET.ParseError, zipfile.BadZipFile, RelationshipAnalysisError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK relations={len(RELATION_SPECS)} keys={sum(len(spec.key_candidates) for spec in SHEET_SPECS)}")
    print(f"reproducible_content_hash={manifest['reproducible_content_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
