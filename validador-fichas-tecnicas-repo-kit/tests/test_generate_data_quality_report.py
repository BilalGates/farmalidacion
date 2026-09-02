from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from scripts.generate_data_quality_report import (
    DataQualityError,
    generate_report,
    sha256,
)
from scripts.profile_reference_files import stable_json

FIELDS = [
    "workbook_id",
    "sheet_name",
    "column_index",
    "header_raw",
    "material_value_count",
    "null_count",
    "formula_count",
    "error_count",
    "type_counts",
    "max_length",
    "cardinality",
    "cardinality_method",
    "duplicate_value_count",
    "candidate_key",
]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def evidence(tmp_path: Path) -> tuple[Path, Path]:
    profile = tmp_path / "profile"
    integrity = tmp_path / "integrity"
    profile.mkdir()
    integrity.mkdir()
    columns = profile / "columns.csv"
    incidents = profile / "incidents-summary.csv"
    base = {
        "workbook_id": "fixture",
        "sheet_name": "General",
        "formula_count": 0,
        "error_count": 0,
        "cardinality_method": "exact_sha256_64",
    }
    write_csv(
        columns,
        FIELDS,
        [
            {
                **base,
                "column_index": 1,
                "header_raw": "ID",
                "material_value_count": 3,
                "null_count": 0,
                "type_counts": json.dumps({"number": 3}),
                "max_length": 1,
                "cardinality": 3,
                "duplicate_value_count": 0,
                "candidate_key": "true",
            },
            {
                **base,
                "column_index": 2,
                "header_raw": "VALUE",
                "material_value_count": 2,
                "null_count": 1,
                "formula_count": 1,
                "type_counts": json.dumps({"shared_string": 2}),
                "max_length": 5,
                "cardinality": 1,
                "duplicate_value_count": 1,
                "candidate_key": "false",
            },
        ],
    )
    incident_fields = [
        "workbook_id",
        "sheet_name",
        "code",
        "severity",
        "count",
        "evidence",
    ]
    write_csv(
        incidents,
        incident_fields,
        [
            {
                "workbook_id": "fixture",
                "sheet_name": "General",
                "code": "DUPLICATE_ROW",
                "severity": "info",
                "count": 1,
                "evidence": "exact",
            }
        ],
    )
    extra = profile / "workbook.json"
    extra.write_text("{}\n", encoding="utf-8")
    outputs = [
        {"path": item.name, "sha256": sha256(item)}
        for item in (columns, incidents, extra)
    ]
    (profile / "run-manifest.json").write_text(
        json.dumps(
            {
                "source_files_modified": False,
                "reproducible_content_hash": "profile-hash",
                "outputs": outputs,
            }
        ),
        encoding="utf-8",
    )

    payload = {
        "catalog": {
            "active_rows": 353,
            "incidents": [{"code": "CATALOG_TYPE_INCONSISTENCY"}],
        },
        "duplicates": [{"workbook": "fixture", "count": 2}],
        "lengths": [
            {"status": "exceeds", "field": "A"},
            {"status": "at_limit", "field": "B"},
        ],
        "orphan_excipients": {"orphan_rows": 3, "orphan_distinct_keys": 2},
    }
    payload["reproducible_content_hash"] = hashlib.sha256(
        stable_json(payload).encode("utf-8")
    ).hexdigest()
    (integrity / "integrity-report.json").write_text(
        stable_json(payload) + "\n", encoding="utf-8"
    )
    return profile, integrity


def test_report_is_aggregate_and_reproducible(tmp_path: Path) -> None:
    profile, integrity = evidence(tmp_path)
    first = generate_report(profile, integrity, tmp_path / "first")
    second = generate_report(profile, integrity, tmp_path / "second")
    assert first == second
    payload = json.loads(
        (tmp_path / "first" / "quality-report.json").read_text(encoding="utf-8")
    )
    assert payload["columns"] == {
        "candidate_keys": 1,
        "columns": 2,
        "errors": 0,
        "formulas": 1,
        "material_values": 5,
        "nulls": 1,
        "type_counts": {"number": 3, "shared_string": 2},
    }
    assert payload["lengths"] == {"at_limit": 1, "evaluated": 2, "exceeded": 1}
    assert payload["orphans"] == {"distinct_keys": 2, "rows": 3}
    summary = (tmp_path / "first" / "summary.md").read_text(encoding="utf-8")
    assert "Catálogo activo" in summary and "al límite" in summary
    assert not (tmp_path / "first" / "cells.csv").exists()


def test_modified_profile_artifact_is_rejected(tmp_path: Path) -> None:
    profile, integrity = evidence(tmp_path)
    with (profile / "columns.csv").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    with pytest.raises(DataQualityError, match="modificada"):
        generate_report(profile, integrity, tmp_path / "output")


def test_existing_output_is_not_overwritten(tmp_path: Path) -> None:
    profile, integrity = evidence(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(DataQualityError, match="existe"):
        generate_report(profile, integrity, output)
    assert marker.read_text(encoding="utf-8") == "keep"
