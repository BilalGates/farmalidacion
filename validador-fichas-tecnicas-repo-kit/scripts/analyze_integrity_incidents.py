#!/usr/bin/env python3
"""Reproduce aggregate integrity incidents for DEV-009 without changing sources."""

from __future__ import annotations
import argparse, hashlib, json, re, shutil, sys, tempfile, zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from analyze_reference_relationships import RelationSpec, iter_rows, read_selected_sheets, relation_result
    from profile_reference_files import XLSX_NAMES, stable_json, validate_xlsx, workbook_sheets, shared_strings
    from verify_reference_files import EXPECTED, RAW_DIR, sha256
except ModuleNotFoundError:
    from scripts.analyze_reference_relationships import RelationSpec, iter_rows, read_selected_sheets, relation_result
    from scripts.profile_reference_files import XLSX_NAMES, stable_json, validate_xlsx, workbook_sheets, shared_strings
    from scripts.verify_reference_files import EXPECTED, RAW_DIR, sha256

SCHEMA_VERSION = "1.0.0"
CATALOG = "Catalogo_campos_clinicos_medicamentos.xlsx"
CATALOG_SHEET = "Eval. solo Ficha Técnica"
CATALOG_FIELDS = 353
OVERRIDES = {"EX_DESCRIPCION": (100, "D-021"), "ME_DESCRIPCION": (100, "D-021")}
BLOCK_SOURCES = {
    "Principio activo - General+DMAX": ("PrincipioActivoCargaMaster-22062026.xlsx", "General"),
    "Principio activo - Frecuencias": ("PrincipioActivoCargaMaster-22062026.xlsx", "Frecuencia"),
    "Principio activo - Vías": ("PrincipioActivoCargaMaster-22062026.xlsx", "Via"),
    "Principio activo - Consejos": ("PrincipioActivoCargaMaster-22062026.xlsx", "ConsejosAdministracion"),
    "Principio activo - DAnaliticos": ("PrincipioActivoCargaMaster-22062026.xlsx", "DatosAnaliticos"),
    "Medicamento - General": ("Medicamento-cargaMaster25062026.xlsx", "General"),
    "Medicamento - Composición": ("Medicamento-cargaMaster25062026.xlsx", "Composicion"),
    "Medicamento - Indicaciones": ("Medicamento-cargaMaster25062026.xlsx", "Indicacion"),
    "Medicamento - Frecuencias": ("Medicamento-cargaMaster25062026.xlsx", "Frecuencia"),
    "Medicamento - Vías": ("Medicamento-cargaMaster25062026.xlsx", "Via"),
    "Medicamento - Info prescripción": ("Medicamento-cargaMaster25062026.xlsx", "Prescripcion"),
    "Medicamento - Links": ("Medicamento-cargaMaster25062026.xlsx", "Links"),
    "Especialidad - General": ("Especialidades-CargaMaster190626.xlsx", "General"),
    "Especialidad - Excipientes": ("Especialidades-CargaMaster190626.xlsx", "Excipientes"),
    "Interacciones": ("Interacciones-cargaMaster250626.xlsx", "General"),
    "Interacciones - GP": ("Interacciones-cargaMaster250626.xlsx", "AplicaA"),
}
DUPLICATE_EVIDENCE = [
    {"code":"DUPLICATE_ROW","severity":"info","workbook":"Interacciones-cargaMaster250626.xlsx","sheet":"General","count":17440,"evidence":"DEV-002 linear_counting_1048576_bits"},
    {"code":"DUPLICATE_ROW","severity":"info","workbook":"Interacciones-cargaMaster250626.xlsx","sheet":"AplicaA","count":16858,"evidence":"DEV-002 linear_counting_1048576_bits"},
    {"code":"DUPLICATE_ROW","severity":"info","workbook":"Medicamento-cargaMaster25062026.xlsx","sheet":"Indicacion","count":9,"evidence":"DEV-002 exact_sha256_64"},
    {"code":"DUPLICATE_ROW","severity":"info","workbook":"Medicamento-cargaMaster25062026.xlsx","sheet":"Via","count":5,"evidence":"DEV-002 exact_sha256_64"},
    {"code":"DUPLICATE_HEADER","severity":"warning","workbook":"Medicamento-cargaMaster25062026.xlsx","sheet":"Links","count":1,"evidence":"DEV-002 headers_preserved_with_ordinal"},
    {"code":"DUPLICATE_ROW","severity":"info","workbook":"OMEPRAZOL 20 MGrelleno.xlsx","sheet":"Medicamento - General","count":2,"evidence":"DEV-002 exact_sha256_64"},
]

class IntegrityError(RuntimeError): pass

def literal(encoded: str) -> str:
    return encoded.split("\x1e", 1)[1]

def parse_char_limit(type_text: str) -> int | None:
    match = re.fullmatch(r"CHAR\s*\(\s*(\d+)\s*\)", type_text.strip(), re.IGNORECASE)
    return int(match.group(1)) if match else None

def read_catalog(path: Path) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    validate_xlsx(path)
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive); sheets, _ = workbook_sheets(archive)
        sheet = next((item for item in sheets if item["name"] == CATALOG_SHEET), None)
        if sheet is None: raise IntegrityError("Catalog sheet not found")
        rows = list(iter_rows(archive, sheet, strings))
    candidates = []
    for index, row in enumerate(rows):
        values = {literal(value) for value in row.values()}
        if {"Entidad", "Campo", "Tipo"} <= values: candidates.append((index, row))
    if len(candidates) != 1: raise IntegrityError(f"Expected one catalog header, found {len(candidates)}")
    header_index, header_row = candidates[0]
    headers = {column: literal(value) for column, value in header_row.items()}
    number_column = min(headers)
    records, incidents = [], []
    for row in rows[header_index + 1:]:
        raw_number = literal(row[number_column]) if number_column in row else ""
        if not raw_number.isdigit(): continue
        number = int(raw_number)
        if not 1 <= number <= CATALOG_FIELDS: continue
        record = {headers[column]: literal(value) for column, value in row.items() if column in headers}
        records.append(record)
    numbers = [int(row[next(key for key in row if key.startswith("N"))]) for row in records]
    if numbers != list(range(1, CATALOG_FIELDS + 1)):
        incidents.append({"code":"CATALOG_SEQUENCE", "severity":"error", "count":1, "evidence":"expected 1..353"})
    field_counts = Counter((row.get("Bloque origen", ""), row.get("Campo", "")) for row in records)
    for (block, field), count in sorted(field_counts.items()):
        if not block or not field or count > 1:
            incidents.append({"code":"CATALOG_FIELD_IDENTITY", "severity":"warning", "count":count, "evidence":f"{block}/{field}" if block or field else "blank"})
    types_by_identity: dict[tuple[str, str], set[str]] = {}
    for row in records:
        identity = (row.get("Bloque origen", ""), row.get("Campo", ""))
        types_by_identity.setdefault(identity, set()).add(row.get("Tipo", ""))
    for (block, field), types in sorted(types_by_identity.items()):
        if len(types) > 1:
            incidents.append({"code":"CATALOG_TYPE_CONFLICT", "severity":"error", "count":len(types), "evidence":f"{block}/{field}: {' | '.join(sorted(types))}"})
    for row in records:
        declared = row.get("Tipo", "")
        if not declared:
            incidents.append({"code":"CATALOG_TYPE_BLANK", "severity":"warning", "count":1, "evidence":row.get("Campo", "")})
        elif parse_char_limit(declared) is None and not (declared.startswith("ENTERO") or declared.startswith("DECIMAL")):
            incidents.append({"code":"CATALOG_TYPE_UNRECOGNIZED", "severity":"warning", "count":1, "evidence":f"{row.get('Campo','')}={declared}"})
    return records, incidents

def scan_workbooks(raw_dir: Path) -> tuple[dict[tuple[str, str, str], dict[str, object]], list[dict[str, object]]]:
    observed: dict[tuple[str, str, str], dict[str, object]] = {}
    duplicates: list[dict[str, object]] = list(DUPLICATE_EVIDENCE)
    for name in sorted({workbook for workbook, _sheet in BLOCK_SOURCES.values()}):
        path = raw_dir / name; validate_xlsx(path)
        with zipfile.ZipFile(path) as archive:
            strings = shared_strings(archive); sheets, _ = workbook_sheets(archive)
            for sheet in sheets:
                rows = iter_rows(archive, sheet, strings)
                try: header = next(rows)
                except StopIteration: continue
                headers = {column: literal(value) for column, value in header.items()}
                for row_number, row in enumerate(rows, start=2):
                    for column, encoded in row.items():
                        if column not in headers: continue
                        field, value = headers[column], literal(encoded)
                        current = observed.setdefault((name, str(sheet["name"]), field), {"max_length":0,"examples":[],"locations":set()})
                        length = len(value)
                        if length > current["max_length"]:
                            current["max_length"] = length; current["examples"] = [value[:160]]; current["locations"] = {f"{name}/{sheet['name']}/row{row_number}"}
                        elif length == current["max_length"] and len(current["examples"]) < 3:
                            current["examples"].append(value[:160]); current["locations"].add(f"{name}/{sheet['name']}/row{row_number}")
    for value in observed.values(): value["locations"] = sorted(value["locations"])
    return observed, duplicates

def run_analysis(raw_dir: Path, output_dir: Path) -> dict[str, object]:
    if output_dir.exists(): raise IntegrityError(f"Output exists: {output_dir}")
    inputs = [{"filename":name,"sha256":EXPECTED[name]} for name in EXPECTED]
    if any(sha256(raw_dir/item["filename"]) != item["sha256"] for item in inputs): raise IntegrityError("Missing or changed input")
    catalog, catalog_incidents = read_catalog(raw_dir/CATALOG)
    observed, duplicates = scan_workbooks(raw_dir)
    lengths=[]
    for row in catalog:
        field, declared = row.get("Campo",""), row.get("Tipo","")
        catalog_limit = parse_char_limit(declared); override = OVERRIDES.get(field)
        effective = override[0] if override else catalog_limit
        if effective is None: continue
        source_key = BLOCK_SOURCES.get(row.get("Bloque origen", ""))
        observation = {} if source_key is None else observed.get((*source_key, field), {})
        maximum = int(observation.get("max_length", 0))
        status = "exceeds" if maximum > effective else "at_limit" if maximum == effective and maximum else "within" if maximum else "not_observed"
        lengths.append({"block":row.get("Bloque origen",""),"field":field,"declared_type":declared,"catalog_limit":catalog_limit,"effective_limit":effective,"override_decision":override[1] if override else None,"observed_max_length":maximum,"status":status,"examples":observation.get("examples",[]),"locations":observation.get("locations",[])})
    spec=RelationSpec("esp_excipiente", "Especialidades-CargaMaster190626.xlsx", "General", "Excipientes", ("BN_IDEXTERNO",), ("BN_IDEXTERNO",))
    sheets=read_selected_sheets(raw_dir/spec.workbook,{spec.parent_sheet,spec.child_sheet}); orphan=relation_result(spec,sheets)
    payload={"schema_version":SCHEMA_VERSION,"inputs":inputs,"catalog":{"header_rule":"unique row containing Entidad+Campo+Tipo","active_rows":len(catalog),"incidents":catalog_incidents},"orphan_excipients":orphan,"duplicates":duplicates,"lengths":lengths}
    content_hash=hashlib.sha256(stable_json(payload).encode()).hexdigest(); payload["reproducible_content_hash"]=content_hash
    staging=Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-",dir=output_dir.parent))
    try:
        (staging/"integrity-report.json").write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
        exceeded=[x for x in lengths if x["status"]=="exceeds"]; exact=[x for x in lengths if x["status"]=="at_limit"]
        lines=["# DEV-009 — Incidencias de integridad","",f"- Hash reproducible: `{content_hash}`",f"- Catálogo activo: {len(catalog)}/353 campos",f"- Huérfanos de excipientes: {orphan['orphan_rows']} filas / {orphan['orphan_distinct_keys']} claves",f"- Incidencias de duplicado: {len(duplicates)}",f"- Campos que exceden longitud: {len(exceeded)}",f"- Campos exactamente en límite: {len(exact)}","","## Excesos","","| Campo | Tipo efectivo | Máximo | Estado |","|---|---:|---:|---|"]
        lines.extend(f"| {x['block']} / {x['field']} | {x['effective_limit']} | {x['observed_max_length']} | {x['status']} |" for x in exceeded+exact)
        (staging/"summary.md").write_text("\n".join(lines)+"\n",encoding="utf-8",newline="\n")
        manifest={"schema_version":SCHEMA_VERSION,"outputs":["integrity-report.json","summary.md"],"reproducible_content_hash":content_hash,"source_files_modified":False}
        (staging/"run-manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
        if any(sha256(raw_dir/item["filename"]) != item["sha256"] for item in inputs): raise IntegrityError("Input changed")
        staging.replace(output_dir); return manifest
    except Exception: shutil.rmtree(staging,ignore_errors=True); raise

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--raw-dir",type=Path,default=RAW_DIR); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args(argv)
    try: result=run_analysis(args.raw_dir.resolve(),args.output.resolve())
    except (OSError,ET.ParseError,zipfile.BadZipFile,IntegrityError) as error: print(f"ERROR: {error}",file=sys.stderr); return 1
    print(f"OK hash={result['reproducible_content_hash']}"); return 0
if __name__=="__main__": raise SystemExit(main())
