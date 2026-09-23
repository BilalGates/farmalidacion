#!/usr/bin/env python3
"""Exercise Omeprazol source cells through the application's temporary ORM schema.

This is a technical gate, not a business-identity mapping: each populated
source row is represented as a provisional TargetRecord and each source column
is identified only by its Excel column number.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.import_omeprazole_fixture import SHEET_ROLES, SOURCE_NAME, build_snapshot
from scripts.profile_reference_files import column_letter, stable_id, stable_json
from scripts.roundtrip_omeprazole_fixture import compare_packages, reconstruct
from scripts.verify_reference_files import EXPECTED, sha256

BACKEND_SOURCE = Path(__file__).resolve().parents[1] / "backend" / "src"
sys.path.insert(0, str(BACKEND_SOURCE))
from pharma_validator_api.models import (  # type: ignore[import-untyped]
    Base,
    BlockInstance,
    FieldMaintenanceRevision,
    FieldValue,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)


class DatabaseRoundTripError(RuntimeError):
    pass


def _persist_snapshot(
    session: Session, snapshot: dict[str, object], source: Path
) -> None:
    document_data = snapshot["documento_fuente"]
    version_data = snapshot["documento_fuente_version"]
    assert isinstance(document_data, dict) and isinstance(version_data, dict)
    document_id = str(document_data["document_id"])
    version_id = str(version_data["version_id"])
    source_hash = str(version_data["sha256"])

    session.add(
        SourceDocument(
            id=document_id,
            source_type="excel_reference_fixture",
            name=source.name,
        )
    )
    session.flush()
    session.add(
        SourceDocumentVersion(
            id=version_id,
            document_id=document_id,
            content_hash=source_hash,
            source_version=source_hash,
            source_locator=str(source),
            acquired_at=datetime.now(UTC),
        )
    )
    session.flush()

    records: list[TargetRecord] = []
    blocks: list[BlockInstance] = []
    fragments: list[SourceFragment] = []
    field_values: list[FieldValue] = []
    provenances: list[ValueProvenance] = []
    sheets = snapshot["sheets"]
    assert isinstance(sheets, list)
    for sheet in sheets:
        assert isinstance(sheet, dict)
        sheet_name = str(sheet["name"])
        occurrences = sheet["occurrences"]
        assert isinstance(occurrences, list)
        for occurrence in occurrences:
            assert isinstance(occurrence, dict)
            row_number = int(occurrence["source_row"])
            occurrence_id = str(occurrence["occurrence_id"])
            record_id = stable_id("target_record", occurrence_id)
            fragment_id = stable_id("source_fragment", occurrence_id)
            records.append(
                TargetRecord(id=record_id, entity_type="fixture_provisional_row")
            )
            fragments.append(
                SourceFragment(
                    id=fragment_id,
                    document_version_id=version_id,
                    locator_type="excel_row",
                    locator=stable_json({"sheet": sheet_name, "row": row_number}),
                    literal_text=stable_json(occurrence["values"]),
                )
            )
            blocks.append(
                BlockInstance(
                    id=occurrence_id,
                    target_record_id=record_id,
                    block_type=sheet_name,
                    ordinal=int(occurrence["material_row_ordinal"]),
                    source_fragment_id=fragment_id,
                )
            )
            values = occurrence["values"]
            assert isinstance(values, list)
            for cell in values:
                assert isinstance(cell, dict)
                column = int(cell["column_index"])
                field_id = stable_id("field_value", occurrence_id, column)
                field_values.append(
                    FieldValue(
                        id=field_id,
                        block_instance_id=occurrence_id,
                        field_name=column_letter(column),
                        source_column_index=column,
                        literal_value=str(cell["raw_value"]),
                        observed_type=str(cell["observed_type"]),
                        logical_state="valued",
                    )
                )
                provenances.append(
                    ValueProvenance(
                        id=stable_id("value_provenance", field_id),
                        field_value_id=field_id,
                        source_fragment_id=fragment_id,
                        provenance_role="master_baseline",
                    )
                )

    session.add_all(records)
    session.flush()
    session.add_all(fragments)
    session.add_all(blocks)
    session.flush()
    session.add_all(field_values)
    session.flush()
    session.add_all(provenances)
    session.commit()


def _snapshot_from_database(
    session: Session, original: dict[str, object]
) -> dict[str, object]:
    snapshot = copy.deepcopy(original)
    sheets = snapshot["sheets"]
    assert isinstance(sheets, list)
    rows: dict[tuple[str, int], dict[str, object]] = {}
    expected_coordinates: set[tuple[str, str]] = set()
    for sheet in sheets:
        assert isinstance(sheet, dict)
        for occurrence in sheet["occurrences"]:
            assert isinstance(occurrence, dict)
            rows[(str(sheet["name"]), int(occurrence["source_row"]))] = occurrence
            for cell in occurrence["values"]:
                expected_coordinates.add((str(sheet["name"]), str(cell["coordinate"])))

    found_coordinates: set[tuple[str, str]] = set()
    maintenance: dict[str, FieldMaintenanceRevision] = {}
    for revision in session.scalars(
        select(FieldMaintenanceRevision).order_by(
            FieldMaintenanceRevision.field_value_id,
            FieldMaintenanceRevision.sequence,
        )
    ):
        maintenance[revision.field_value_id] = revision
    statement = (
        select(FieldValue, SourceFragment)
        .join(BlockInstance, BlockInstance.id == FieldValue.block_instance_id)
        .join(SourceFragment, SourceFragment.id == BlockInstance.source_fragment_id)
        .order_by(FieldValue.id)
    )
    for field, fragment in session.execute(statement):
        locator = json.loads(fragment.locator)
        sheet_name = str(locator["sheet"])
        row_number = int(locator["row"])
        if field.source_column_index is None:
            raise DatabaseRoundTripError(f"Missing source column on {field.id}")
        coordinate = f"{column_letter(field.source_column_index)}{row_number}"
        occurrence = rows.get((sheet_name, row_number))
        if occurrence is None:
            raise DatabaseRoundTripError(
                f"Unmapped source row: {sheet_name}!{row_number}"
            )
        occurrence_values = occurrence["values"]
        if not isinstance(occurrence_values, list):
            raise DatabaseRoundTripError("Malformed occurrence in the source snapshot")
        cell = next(
            (
                item
                for item in occurrence_values
                if isinstance(item, dict) and item.get("coordinate") == coordinate
            ),
            None,
        )
        if cell is None:
            raise DatabaseRoundTripError(
                f"Unmapped source cell: {sheet_name}!{coordinate}"
            )
        revision = maintenance.get(field.id)
        cell["raw_value"] = revision.after_value if revision else field.literal_value
        cell["observed_type"] = field.observed_type
        found_coordinates.add((sheet_name, coordinate))

    if found_coordinates != expected_coordinates:
        missing = sorted(expected_coordinates - found_coordinates)[:5]
        extra = sorted(found_coordinates - expected_coordinates)[:5]
        raise DatabaseRoundTripError(
            f"Cell coverage mismatch; missing={missing}, extra={extra}"
        )
    snapshot["model_status"] = "temporary_database_coordinate_roundtrip"
    return snapshot


def run_database_roundtrip(
    source: Path,
    destination: Path,
    expected_hash: str = EXPECTED[SOURCE_NAME],
    sheet_roles: dict[str, tuple[str, str]] = SHEET_ROLES,
) -> dict[str, object]:
    source = source.resolve()
    destination = destination.resolve()
    if sha256(source) != expected_hash:
        raise DatabaseRoundTripError(
            "The source workbook hash differs from the approved fixture"
        )
    if destination.exists():
        raise DatabaseRoundTripError(f"Output already exists: {destination}")

    original_snapshot = build_snapshot(source, expected_hash, sheet_roles)
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _persist_snapshot(session, original_snapshot, source)
            persisted_snapshot = _snapshot_from_database(session, original_snapshot)
            reconstruct(source, persisted_snapshot, destination)
            differences, sheet_report = compare_packages(source, destination)
            if differences:
                raise DatabaseRoundTripError(
                    f"Database round-trip has {len(differences)} differences"
                )

            editable_value = session.scalar(
                select(FieldValue)
                .where(FieldValue.observed_type == "number")
                .order_by(FieldValue.id)
                .limit(1)
            )
            if editable_value is None or editable_value.literal_value is None:
                raise DatabaseRoundTripError(
                    "No numeric field is available for the edit check"
                )
            original_value = editable_value.literal_value
            corrected_value = "987654321.123"
            if corrected_value == original_value:
                corrected_value = "123456789.987"
            now = datetime.now(UTC)
            session.add(
                FieldMaintenanceRevision(
                    field_value_id=editable_value.id,
                    sequence=1,
                    before_value=original_value,
                    after_value=corrected_value,
                    actor_id="roundtrip-test",
                    actor_assurance="declarada",
                    reason="Comprobación temporal del recorrido de edición.",
                    recorded_at=now,
                )
            )
            session.commit()
            changed_snapshot = _snapshot_from_database(session, original_snapshot)
            changed_output = destination.with_name(
                f"{destination.stem}-edited{destination.suffix}"
            )
            reconstruct(source, changed_snapshot, changed_output)
            changed_differences, _changed_sheets = compare_packages(
                source, changed_output
            )
            if (
                len(changed_differences) != 1
                or changed_differences[0].get("code") != "material_cell_changed"
            ):
                raise DatabaseRoundTripError(
                    "A single maintenance edit must produce exactly one material-cell difference"
                )

            session.add(
                FieldMaintenanceRevision(
                    field_value_id=editable_value.id,
                    sequence=2,
                    before_value=corrected_value,
                    after_value=original_value,
                    actor_id="roundtrip-test",
                    actor_assurance="declarada",
                    reason="Restauración temporal para cerrar la comprobación.",
                    recorded_at=datetime.now(UTC),
                )
            )
            session.commit()
            restored_snapshot = _snapshot_from_database(session, original_snapshot)
            reconstruct(source, restored_snapshot, destination)
            differences, sheet_report = compare_packages(source, destination)
            if differences:
                raise DatabaseRoundTripError(
                    f"Restoring the temporary edit left {len(differences)} differences"
                )
            counts = {
                "target_records": session.query(TargetRecord).count(),
                "blocks": session.query(BlockInstance).count(),
                "field_values": session.query(FieldValue).count(),
                "maintenance_revisions": session.query(
                    FieldMaintenanceRevision
                ).count(),
            }
            changed_output.unlink()
    finally:
        engine.dispose()

    source_hash_after = sha256(source)
    if source_hash_after != expected_hash:
        raise DatabaseRoundTripError("The source workbook changed during the test")
    return {
        "status": "pass",
        "source_sha256_before": expected_hash,
        "source_sha256_after": source_hash_after,
        "totals": original_snapshot["totals"],
        "persisted": counts,
        "sheets_compared": len(sheet_report),
        "equal_sheets": sum(bool(sheet["structure_equal"]) for sheet in sheet_report),
        "difference_count": len(differences),
        "edit_check": {
            "changed_cell_differences": len(changed_differences),
            "restored_differences": 0,
        },
        "output_sha256": sha256(destination),
        "identity_policy": original_snapshot["identity_policy"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    result = run_database_roundtrip(arguments.source, arguments.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
