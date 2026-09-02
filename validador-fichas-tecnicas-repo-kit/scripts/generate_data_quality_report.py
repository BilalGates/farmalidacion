#!/usr/bin/env python3
"""Consolidate reproducible aggregate profiling and integrity evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

try:
    from profile_reference_files import stable_json, write_csv
except ModuleNotFoundError:
    from scripts.profile_reference_files import stable_json, write_csv

SCHEMA_VERSION = "1.0.0"
QUALITY_COLUMN_FIELDS = [
    "workbook_id",
    "sheet_name",
    "column_index",
    "header_raw",
    "material_value_count",
    "null_count",
    "type_counts",
    "max_length",
    "cardinality",
    "cardinality_method",
    "duplicate_value_count",
    "candidate_key",
]
INCIDENT_FIELDS = ["source", "code", "severity", "count", "scope", "evidence"]


class DataQualityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataQualityError(f"No se puede leer {path.name}: {error}") from error
    if not isinstance(payload, dict):
        raise DataQualityError(f"{path.name} no contiene un objeto JSON.")
    return payload


def validate_profile(profile_dir: Path) -> dict[str, object]:
    manifest = read_json(profile_dir / "run-manifest.json")
    if manifest.get("source_files_modified") is not False:
        raise DataQualityError("El perfil no acredita originales intactos.")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        raise DataQualityError("El manifiesto de perfil no enumera salidas.")
    for output in outputs:
        if not isinstance(output, dict):
            raise DataQualityError("Salida de perfil inválida.")
        relative = output.get("path")
        expected_hash = output.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise DataQualityError("Salida de perfil sin ruta o hash.")
        target = (profile_dir / relative).resolve()
        if profile_dir.resolve() not in target.parents:
            raise DataQualityError("Ruta de salida de perfil fuera del directorio.")
        if not target.is_file() or sha256(target) != expected_hash:
            raise DataQualityError(f"Salida de perfil ausente o modificada: {relative}")
    return manifest


def validate_integrity(integrity_dir: Path) -> dict[str, object]:
    report = read_json(integrity_dir / "integrity-report.json")
    expected_hash = report.get("reproducible_content_hash")
    if not isinstance(expected_hash, str):
        raise DataQualityError(
            "El informe de integridad no contiene hash reproducible."
        )
    content = dict(report)
    del content["reproducible_content_hash"]
    actual_hash = hashlib.sha256(stable_json(content).encode()).hexdigest()
    if actual_hash != expected_hash:
        raise DataQualityError("El informe de integridad fue modificado.")
    return report


def read_profile_columns(profile_dir: Path) -> list[dict[str, str]]:
    try:
        with (profile_dir / "columns.csv").open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as error:
        raise DataQualityError(f"No se puede leer columns.csv: {error}") from error


def _integer(row: dict[str, str], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, ValueError) as error:
        raise DataQualityError(
            f"Valor entero inválido en columns.csv: {field}"
        ) from error


def summarize_columns(columns: list[dict[str, str]]) -> dict[str, object]:
    type_counts: Counter[str] = Counter()
    for row in columns:
        try:
            observed = json.loads(row["type_counts"])
        except (KeyError, json.JSONDecodeError) as error:
            raise DataQualityError("type_counts inválido en columns.csv.") from error
        if not isinstance(observed, dict):
            raise DataQualityError("type_counts debe ser un objeto.")
        for observed_type, count in observed.items():
            type_counts[str(observed_type)] += int(count)
    return {
        "columns": len(columns),
        "material_values": sum(
            _integer(row, "material_value_count") for row in columns
        ),
        "nulls": sum(_integer(row, "null_count") for row in columns),
        "formulas": sum(_integer(row, "formula_count") for row in columns),
        "errors": sum(_integer(row, "error_count") for row in columns),
        "candidate_keys": sum(row.get("candidate_key") == "true" for row in columns),
        "type_counts": dict(sorted(type_counts.items())),
    }


def quality_columns(columns: list[dict[str, str]]) -> list[dict[str, object]]:
    return [
        {field: row.get(field, "") for field in QUALITY_COLUMN_FIELDS}
        for row in sorted(
            columns,
            key=lambda item: (
                item.get("workbook_id", ""),
                item.get("sheet_name", ""),
                _integer(item, "column_index"),
            ),
        )
    ]


def aggregate_incidents(
    profile_dir: Path, integrity: dict[str, object]
) -> list[dict[str, object]]:
    incidents: list[dict[str, object]] = []
    try:
        with (profile_dir / "incidents-summary.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            for row in csv.DictReader(handle):
                incidents.append(
                    {
                        "source": "DEV-002",
                        "code": row.get("code", ""),
                        "severity": row.get("severity", ""),
                        "count": _integer(row, "count"),
                        "scope": f"{row.get('workbook_id', '')}/{row.get('sheet_name', '')}",
                        "evidence": row.get("evidence", ""),
                    }
                )
    except OSError as error:
        raise DataQualityError(
            f"No se puede leer incidents-summary.csv: {error}"
        ) from error

    catalog = integrity.get("catalog", {})
    if not isinstance(catalog, dict):
        raise DataQualityError("Sección catalog inválida.")
    catalog_incidents = catalog.get("incidents", [])
    duplicates = integrity.get("duplicates", [])
    lengths = integrity.get("lengths", [])
    for item in catalog_incidents if isinstance(catalog_incidents, list) else []:
        incidents.append(
            {
                "source": "DEV-009",
                "code": item.get("code", ""),
                "severity": item.get("severity", ""),
                "count": int(item.get("count", 0)),
                "scope": "catalog",
                "evidence": item.get("evidence", ""),
            }
        )
    for item in duplicates if isinstance(duplicates, list) else []:
        incidents.append(
            {
                "source": "DEV-009",
                "code": item.get("code", ""),
                "severity": item.get("severity", ""),
                "count": int(item.get("count", 0)),
                "scope": f"{item.get('workbook', '')}/{item.get('sheet', '')}",
                "evidence": item.get("evidence", ""),
            }
        )
    for item in lengths if isinstance(lengths, list) else []:
        status = item.get("status")
        if status not in {"exceeds", "at_limit"}:
            continue
        incidents.append(
            {
                "source": "DEV-009",
                "code": "LENGTH_EXCEEDED" if status == "exceeds" else "LENGTH_AT_LIMIT",
                "severity": "error" if status == "exceeds" else "info",
                "count": 1,
                "scope": f"{item.get('block', '')}/{item.get('field', '')}",
                "evidence": (
                    f"effective={item.get('effective_limit')};"
                    f"observed={item.get('observed_max_length')}"
                ),
            }
        )
    orphan = integrity.get("orphan_excipients", {})
    if isinstance(orphan, dict):
        incidents.append(
            {
                "source": "DEV-009",
                "code": "ORPHAN_EXCIPIENT",
                "severity": "warning",
                "count": int(orphan.get("orphan_rows", 0)),
                "scope": "Especialidades/Excipientes",
                "evidence": f"distinct_keys={orphan.get('orphan_distinct_keys', 0)}",
            }
        )
    return sorted(
        incidents,
        key=lambda item: (
            str(item["severity"]),
            str(item["code"]),
            str(item["scope"]),
            str(item["evidence"]),
        ),
    )


def generate_report(
    profile_dir: Path, integrity_dir: Path, output_dir: Path
) -> dict[str, object]:
    profile_dir = profile_dir.resolve()
    integrity_dir = integrity_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise DataQualityError(f"La salida ya existe: {output_dir}")
    profile = validate_profile(profile_dir)
    integrity = validate_integrity(integrity_dir)
    columns = read_profile_columns(profile_dir)
    column_summary = summarize_columns(columns)
    incidents = aggregate_incidents(profile_dir, integrity)
    catalog = integrity.get("catalog", {})
    orphan = integrity.get("orphan_excipients", {})
    lengths = integrity.get("lengths", [])
    duplicates = integrity.get("duplicates", [])
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "profile_hash": profile.get("reproducible_content_hash"),
            "integrity_hash": integrity.get("reproducible_content_hash"),
        },
        "columns": column_summary,
        "catalog": {
            "active_rows": catalog.get("active_rows")
            if isinstance(catalog, dict)
            else None,
            "incident_count": len(catalog.get("incidents", []))
            if isinstance(catalog, dict)
            else 0,
        },
        "lengths": {
            "evaluated": len(lengths) if isinstance(lengths, list) else 0,
            "exceeded": sum(item.get("status") == "exceeds" for item in lengths)
            if isinstance(lengths, list)
            else 0,
            "at_limit": sum(item.get("status") == "at_limit" for item in lengths)
            if isinstance(lengths, list)
            else 0,
        },
        "duplicates": {
            "incident_groups": len(duplicates) if isinstance(duplicates, list) else 0,
            "reported_rows": sum(int(item.get("count", 0)) for item in duplicates)
            if isinstance(duplicates, list)
            else 0,
        },
        "orphans": {
            "rows": orphan.get("orphan_rows") if isinstance(orphan, dict) else None,
            "distinct_keys": orphan.get("orphan_distinct_keys")
            if isinstance(orphan, dict)
            else None,
        },
        "incident_groups": len(incidents),
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)
    )
    try:
        columns_path = staging / "columns-quality.csv"
        incidents_path = staging / "incidents.csv"
        write_csv(columns_path, QUALITY_COLUMN_FIELDS, quality_columns(columns))
        write_csv(incidents_path, INCIDENT_FIELDS, incidents)
        structural_hash = hashlib.sha256(
            stable_json(
                {
                    "payload": payload,
                    "columns_sha256": sha256(columns_path),
                    "incidents_sha256": sha256(incidents_path),
                }
            ).encode()
        ).hexdigest()
        payload["reproducible_content_hash"] = structural_hash
        report_path = staging / "quality-report.json"
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        summary = [
            "# Informe agregado de calidad de datos",
            "",
            f"- Hash reproducible: `{structural_hash}`",
            f"- Columnas: {column_summary['columns']}",
            f"- Valores materiales: {column_summary['material_values']}",
            f"- Nulos agregados: {column_summary['nulls']}",
            f"- Tipos observados: {len(column_summary['type_counts'])}",
            f"- Catálogo activo: {payload['catalog']['active_rows']}/353",
            f"- Excesos de longitud: {payload['lengths']['exceeded']}",
            f"- Valores exactamente al límite: {payload['lengths']['at_limit']}",
            f"- Grupos de duplicados: {payload['duplicates']['incident_groups']}",
            (
                f"- Huérfanos de excipientes: {payload['orphans']['rows']} filas / "
                f"{payload['orphans']['distinct_keys']} claves"
            ),
            f"- Grupos de incidencia consolidados: {len(incidents)}",
            "- Originales modificados: no",
            "",
        ]
        (staging / "summary.md").write_text(
            "\n".join(summary), encoding="utf-8", newline="\n"
        )
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "profile_hash": profile.get("reproducible_content_hash"),
            "integrity_hash": integrity.get("reproducible_content_hash"),
            "outputs": [
                "quality-report.json",
                "columns-quality.csv",
                "incidents.csv",
                "summary.md",
            ],
            "reproducible_content_hash": structural_hash,
            "source_files_modified": False,
        }
        (staging / "run-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        staging.replace(output_dir)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--integrity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = generate_report(args.profile, args.integrity, args.output)
    except (OSError, DataQualityError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK hash={result['reproducible_content_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
