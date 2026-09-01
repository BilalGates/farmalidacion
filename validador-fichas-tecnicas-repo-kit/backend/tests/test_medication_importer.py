import hashlib
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config

from pharma_validator_api.active_ingredient_importer import (
    SOURCE_FILENAME as ACTIVE_SOURCE_FILENAME,
)
from pharma_validator_api.active_ingredient_importer import import_active_ingredients
from pharma_validator_api.medication_importer import (
    SOURCE_FILENAME,
    SOURCE_HASH,
    import_medications,
)
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

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "reference" / "raw"
SOURCE = RAW / SOURCE_FILENAME
ACTIVE_SOURCE = RAW / ACTIVE_SOURCE_FILENAME


def migrated_session(tmp_path: Path) -> Session:
    database_path = tmp_path / "medications.db"
    command.upgrade(alembic_config(database_path), "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    return Session(engine)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_master_import_is_lossless_linked_and_idempotent(tmp_path: Path) -> None:
    before = file_hash(SOURCE)
    assert before == SOURCE_HASH

    with migrated_session(tmp_path) as session:
        active = import_active_ingredients(session, ACTIVE_SOURCE)
        session.commit()
        assert active.status == "completed"

        first = import_medications(session, SOURCE)
        session.commit()
        second = import_medications(session, SOURCE)
        session.commit()

        assert first.created is True
        assert first.status == "completed"
        assert first.sheets == 7
        assert first.occurrences == 58_256
        assert first.values == 509_496
        assert first.quarantined_rows == 0
        assert first.diagnostics == 2
        assert first.composition_links == 4_211
        assert second.created is False
        assert second.batch_id == first.batch_id
        assert second.occurrences == 58_256
        assert second.values == 509_496
        assert second.quarantined_rows == 0
        assert second.diagnostics == 2
        assert second.composition_links == 4_211

        medication_targets = select(TargetRecord.id).where(
            TargetRecord.entity_type == "medication"
        )
        assert session.scalar(
            select(func.count()).select_from(TargetRecord).where(
                TargetRecord.entity_type == "medication"
            )
        ) == 6_342
        assert session.scalar(
            select(func.count()).select_from(BlockInstance).where(
                BlockInstance.target_record_id.in_(medication_targets)
            )
        ) == 58_256
        assert session.scalar(
            select(func.count())
            .select_from(FieldValue)
            .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
            .where(BlockInstance.target_record_id.in_(medication_targets))
        ) == 509_496
        assert session.scalar(
            select(func.count())
            .select_from(ValueProvenance)
            .join(FieldValue, ValueProvenance.field_value_id == FieldValue.id)
            .join(BlockInstance, FieldValue.block_instance_id == BlockInstance.id)
            .where(BlockInstance.target_record_id.in_(medication_targets))
        ) == 509_496
        assert session.scalar(
            select(func.count()).select_from(TargetRecordLink).where(
                TargetRecordLink.link_type == "composition_active_ingredient"
            )
        ) == 4_211
        assert session.scalar(
            select(func.count()).select_from(QuarantinedSourceRow).where(
                QuarantinedSourceRow.import_batch_id == first.batch_id
            )
        ) == 0

        empty_sheets = session.scalars(
            select(ImportedSourceSheet)
            .where(
                ImportedSourceSheet.import_batch_id == first.batch_id,
                ImportedSourceSheet.data_row_count == 0,
            )
            .order_by(ImportedSourceSheet.sheet_ordinal)
        ).all()
        assert [sheet.sheet_name for sheet in empty_sheets] == [
            "Frecuencia",
            "Prescripcion",
        ]
        assert session.scalar(
            select(func.count()).select_from(ImportDiagnostic).where(
                ImportDiagnostic.import_batch_id == first.batch_id
            )
        ) == 2

        link_block = session.scalar(
            select(BlockInstance).where(BlockInstance.block_type == "medication_link").limit(1)
        )
        assert link_block is not None
        assert session.scalar(
            select(func.count()).select_from(FieldValue).where(
                FieldValue.block_instance_id == link_block.id,
                FieldValue.field_name == "DESCRIPCION",
            )
        ) == 2

    assert file_hash(SOURCE) == before


def test_invalid_workbook_fails_batch_and_keeps_diagnostic(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid-medications.xlsx"
    invalid.write_bytes(b"not an OOXML workbook")
    with migrated_session(tmp_path) as session:
        result = import_medications(session, invalid)
        session.commit()
        diagnostic = session.scalar(
            select(ImportDiagnostic).where(ImportDiagnostic.import_batch_id == result.batch_id)
        )
        assert result.status == "failed"
        assert result.occurrences == 0
        assert diagnostic is not None
        assert diagnostic.code == "MEDICATION_IMPORT_INVALID"
