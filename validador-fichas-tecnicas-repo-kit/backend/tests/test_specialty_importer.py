import hashlib
import json
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config

from pharma_validator_api.active_ingredient_importer import (
    SOURCE_FILENAME as ACTIVE_SOURCE_FILENAME,
)
from pharma_validator_api.active_ingredient_importer import import_active_ingredients
from pharma_validator_api.medication_importer import (
    SOURCE_FILENAME as MEDICATION_SOURCE_FILENAME,
)
from pharma_validator_api.medication_importer import import_medications
from pharma_validator_api.models import (
    BlockInstance,
    FieldValue,
    ImportDiagnostic,
    ImportedSourceSheet,
    QuarantinedSourceRow,
    TargetRecord,
    TargetRecordLink,
    ValueProvenance,
)
from pharma_validator_api.specialty_importer import (
    SOURCE_FILENAME,
    SOURCE_HASH,
    import_specialties,
)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "reference" / "raw"
SOURCE = RAW / SOURCE_FILENAME
ACTIVE_SOURCE = RAW / ACTIVE_SOURCE_FILENAME
MEDICATION_SOURCE = RAW / MEDICATION_SOURCE_FILENAME


def migrated_session(tmp_path: Path) -> Session:
    database_path = tmp_path / "specialties.db"
    command.upgrade(alembic_config(database_path), "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    return Session(engine)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.slow
@pytest.mark.reference
def test_real_master_import_preserves_valid_rows_and_quarantines_orphans(
    tmp_path: Path,
) -> None:
    before = file_hash(SOURCE)
    assert before == SOURCE_HASH

    with migrated_session(tmp_path) as session:
        assert import_active_ingredients(session, ACTIVE_SOURCE).status == "completed"
        session.commit()
        assert import_medications(session, MEDICATION_SOURCE).status == "completed"
        session.commit()

        first = import_specialties(session, SOURCE)
        session.commit()
        second = import_specialties(session, SOURCE)
        session.commit()

        assert first.created is True
        assert first.status == "completed"
        assert first.sheets == 2
        assert first.source_rows == 48_470
        assert first.occurrences == 48_195
        assert first.values == 1_623_810
        assert first.occurrences + first.quarantined_rows == first.source_rows
        assert first.quarantined_rows == 275
        assert first.orphan_parent_identifiers == 184
        assert first.diagnostics == 0
        assert first.medication_links == 29_850
        assert second.created is False
        assert second.batch_id == first.batch_id
        assert second.source_rows == first.source_rows
        assert second.occurrences == first.occurrences
        assert second.values == first.values
        assert second.quarantined_rows == first.quarantined_rows
        assert second.orphan_parent_identifiers == first.orphan_parent_identifiers
        assert second.medication_links == first.medication_links

        specialty_targets = select(TargetRecord.id).where(
            TargetRecord.entity_type == "specialty"
        )
        assert session.scalar(
            select(func.count()).select_from(TargetRecord).where(
                TargetRecord.entity_type == "specialty"
            )
        ) == 29_850
        assert session.scalar(
            select(func.count()).select_from(BlockInstance).where(
                BlockInstance.target_record_id.in_(specialty_targets)
            )
        ) == first.occurrences
        assert session.scalar(
            select(func.count())
            .select_from(FieldValue)
            .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
            .where(BlockInstance.target_record_id.in_(specialty_targets))
        ) == first.values
        assert session.scalar(
            select(func.count())
            .select_from(ValueProvenance)
            .join(FieldValue, ValueProvenance.field_value_id == FieldValue.id)
            .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
            .where(BlockInstance.target_record_id.in_(specialty_targets))
        ) == first.values
        assert session.scalar(
            select(func.count()).select_from(TargetRecordLink).where(
                TargetRecordLink.link_type == "specialty_medication"
            )
        ) == 29_850

        sheets = session.scalars(
            select(ImportedSourceSheet)
            .where(ImportedSourceSheet.import_batch_id == first.batch_id)
            .order_by(ImportedSourceSheet.sheet_ordinal)
        ).all()
        assert [sheet.sheet_name for sheet in sheets] == ["General", "Excipientes"]
        assert [sheet.data_row_count for sheet in sheets] == [29_850, 18_620]

        quarantined = session.scalars(
            select(QuarantinedSourceRow).where(
                QuarantinedSourceRow.import_batch_id == first.batch_id
            )
        ).all()
        assert len(quarantined) == 275
        assert {row.reason_code for row in quarantined} == {"MISSING_PARENT"}
        orphan_identifiers = {
            next(
                value["literal_value"]
                for value in json.loads(row.raw_payload)
                if value["header"] == "BN_IDEXTERNO"
            )
            for row in quarantined
        }
        assert len(orphan_identifiers) == 184

    assert file_hash(SOURCE) == before


def test_invalid_workbook_fails_batch_and_keeps_diagnostic(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid-specialties.xlsx"
    invalid.write_bytes(b"not an OOXML workbook")
    with migrated_session(tmp_path) as session:
        result = import_specialties(session, invalid)
        session.commit()
        diagnostic = session.scalar(
            select(ImportDiagnostic).where(ImportDiagnostic.import_batch_id == result.batch_id)
        )
        assert result.status == "failed"
        assert result.occurrences == 0
        assert diagnostic is not None
        assert diagnostic.code == "SPECIALTY_IMPORT_INVALID"
