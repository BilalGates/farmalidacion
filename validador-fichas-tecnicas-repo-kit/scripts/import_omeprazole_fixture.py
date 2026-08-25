#!/usr/bin/env python3
"""Import the omeprazole workbook into a reversible canonical spike snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from profile_reference_files import TAG, column_index, column_letter, read_cell, shared_strings, stable_id, stable_json, validate_xlsx, workbook_sheets
    from verify_reference_files import EXPECTED, RAW_DIR, sha256
except ModuleNotFoundError:
    from scripts.profile_reference_files import TAG, column_index, column_letter, read_cell, shared_strings, stable_id, stable_json, validate_xlsx, workbook_sheets
    from scripts.verify_reference_files import EXPECTED, RAW_DIR, sha256

SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "DEV-007-1.0.0"
SOURCE_NAME = "OMEPRAZOL 20 MGrelleno.xlsx"

SHEET_ROLES = {
    "Principio activo - General+DMAX": ("principio_activo", "general_dosis_maxima"),
    "Principio activo - Frecuencias": ("principio_activo", "frecuencia"),
    "Principio activo - Vías": ("principio_activo", "via"),
    "Principio activo - Consejos": ("principio_activo", "consejo"),
    "Principio activo - DAnaliticos": ("principio_activo", "dato_analitico"),
    "Medicamento - General": ("medicamento", "general"),
    "Medicamento - Composición": ("medicamento", "composicion"),
    "Medicamento - Indicaciones": ("medicamento", "indicacion"),
    "Medicamento - Frecuencias": ("medicamento", "frecuencia"),
    "Medicamento - Vías": ("medicamento", "via"),
    "Medicamento - Info prescripción": ("medicamento", "informacion_prescripcion"),
    "Medicamento - Links": ("medicamento", "link"),
    "Especialidad - General": ("especialidad", "general"),
    "Especialidad - Excipientes": ("especialidad", "excipiente"),
    "Grupo Terapéutico": ("transversal", "grupo_terapeutico"),
    "Alergias": ("transversal", "alergia"),
    "Enf.Congénita": ("transversal", "enfermedad_congenita"),
    "Enf.Crónica": ("transversal", "enfermedad_cronica"),
    "Est. Riesgo": ("transversal", "estado_riesgo"),
    "Intolerancia": ("transversal", "intolerancia"),
    "Interacciones": ("interaccion", "general"),
    "Interacciones - GP": ("interaccion", "grupo_poblacional"),
}


class FixtureImportError(RuntimeError):
    pass


def import_sheet(archive: zipfile.ZipFile, sheet: dict[str, object], strings: list[str], version_id: str, entity: str, block: str) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    current_row = 0
    current_cells: list[dict[str, object]] = []
    material_ordinal = 0
    formula_count = 0
    with archive.open(str(sheet["path"])) as handle:
        for event, element in ET.iterparse(handle, events=("start", "end")):
            if event == "start" and element.tag == TAG("row"):
                current_row = int(element.get("r", "0"))
                current_cells = []
            elif event == "end" and element.tag == TAG("c"):
                reference = element.get("r", "")
                value_type, value, formula, material = read_cell(element, strings)
                if material:
                    index = column_index(reference)
                    current_cells.append({
                        "coordinate": reference,
                        "column_index": index,
                        "column_letter": column_letter(index),
                        "observed_type": value_type,
                        "raw_value": value,
                        "formula": formula,
                        "source_fragment_id": stable_id(version_id, sheet["ordinal"], current_row, index),
                    })
                    formula_count += int(formula is not None)
                element.clear()
            elif event == "end" and element.tag == TAG("row"):
                if current_cells:
                    material_ordinal += 1
                    rows.append({
                        "occurrence_id": stable_id(version_id, sheet["ordinal"], current_row),
                        "occurrence_identity": "technical_provisional_not_natural_key",
                        "material_row_ordinal": material_ordinal,
                        "source_row": current_row,
                        "values": current_cells,
                    })
                current_cells = []
                element.clear()
    return {
        "sheet_id": stable_id(version_id, sheet["ordinal"], sheet["name"]),
        "name": sheet["name"],
        "ordinal": sheet["ordinal"],
        "entity_role": entity,
        "block_role": block,
        "occurrence_semantics": "source_material_row_pending_domain_alignment",
        "material_rows": len(rows),
        "material_values": sum(len(row["values"]) for row in rows),
        "formula_values": formula_count,
        "occurrences": rows,
    }


def build_snapshot(source: Path, expected_sha: str, sheet_roles: dict[str, tuple[str, str]]) -> dict[str, object]:
    if not source.is_file() or source.is_symlink() or sha256(source) != expected_sha:
        raise FixtureImportError("Missing, unsafe or changed omeprazole fixture")
    validate_xlsx(source)
    document_id = stable_id("documento_fuente", source.name)
    version_id = stable_id(document_id, expected_sha)
    with zipfile.ZipFile(source) as archive:
        strings = shared_strings(archive)
        sheets, date_system = workbook_sheets(archive)
        actual_names = [str(sheet["name"]) for sheet in sheets]
        if actual_names != list(sheet_roles):
            raise FixtureImportError("Sheet names/order differ from the explicit DEV-007 contract")
        imported = [import_sheet(archive, sheet, strings, version_id, *sheet_roles[str(sheet["name"])]) for sheet in sheets]
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "documento_fuente": {"document_id": document_id, "logical_name": source.name, "source_kind": "excel_reference_fixture"},
        "documento_fuente_version": {"version_id": version_id, "sha256": expected_sha, "date_system": date_system, "immutable": True},
        "model_status": "canonical_spike_not_physical_schema",
        "identity_policy": "source_coordinates_only_no_business_identity_inference",
        "sheets": imported,
        "totals": {
            "sheets": len(imported),
            "material_rows": sum(int(sheet["material_rows"]) for sheet in imported),
            "material_values": sum(int(sheet["material_values"]) for sheet in imported),
            "formula_values": sum(int(sheet["formula_values"]) for sheet in imported),
        },
    }


def run_import(source: Path, output_dir: Path, expected_sha: str = EXPECTED[SOURCE_NAME], sheet_roles: dict[str, tuple[str, str]] = SHEET_ROLES) -> dict[str, object]:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FixtureImportError(f"Output directory already exists: {output_dir}")
    snapshot = build_snapshot(source.resolve(), expected_sha, sheet_roles)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    try:
        canonical_path = staging / "canonical-snapshot.json"
        canonical_path.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        content_hash = hashlib.sha256(stable_json(snapshot).encode()).hexdigest()
        lines = [
            "# DEV-007 — Importación canónica temporal de omeprazol", "",
            f"- Hash canónico reproducible: `{content_hash}`",
            f"- Hojas: {snapshot['totals']['sheets']}/22",
            f"- Filas materiales conservadas: {snapshot['totals']['material_rows']}",
            f"- Valores materiales conservados: {snapshot['totals']['material_values']}",
            f"- Fórmulas conservadas: {snapshot['totals']['formula_values']}",
            "- Identidades de negocio inferidas: no", "- Original modificado: no", "",
            "| # | Hoja | Entidad | Bloque | Filas | Valores | Fórmulas |", "|---:|---|---|---|---:|---:|---:|",
        ]
        lines.extend(f"| {sheet['ordinal']} | {sheet['name']} | {sheet['entity_role']} | {sheet['block_role']} | {sheet['material_rows']} | {sheet['material_values']} | {sheet['formula_values']} |" for sheet in snapshot["sheets"])
        (staging / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "input": {"filename": source.name, "sha256": expected_sha},
            "outputs": ["canonical-snapshot.json", "summary.md"],
            "canonical_content_hash": content_hash,
            "source_files_modified": False,
            "status": "pass" if snapshot["totals"]["sheets"] == len(sheet_roles) else "fail",
        }
        (staging / "run-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        if sha256(source) != expected_sha:
            raise FixtureImportError("Source changed during import")
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
        manifest = run_import(args.source, args.output)
    except (OSError, ET.ParseError, zipfile.BadZipFile, FixtureImportError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK sheets=22/22")
    print(f"canonical_content_hash={manifest['canonical_content_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
