import hashlib
import json
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config

from pharma_validator_api.active_ingredient_importer import (
    SOURCE_FILENAME,
    SOURCE_HASH,
    import_active_ingredients,
)
from pharma_validator_api.models import (
    BlockInstance,
    DocumentRecordLink,
    FieldValue,
    ImportBatch,
    ImportDiagnostic,
    ImportedSourceSheet,
    SourceDocument,
    SourceDocumentVersion,
    SourceFragment,
    TargetRecord,
    ValueProvenance,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "reference" / "raw" / SOURCE_FILENAME


def migrated_session(tmp_path: Path) -> Session:
    database_path = tmp_path / "active-ingredients.db"
    command.upgrade(alembic_config(database_path), "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    return Session(engine)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.slow
@pytest.mark.reference
def test_real_master_import_is_lossless_idempotent_and_provenanced(tmp_path: Path) -> None:
    before = file_hash(SOURCE)
    assert before == SOURCE_HASH

    with migrated_session(tmp_path) as session:
        first = import_active_ingredients(session, SOURCE)
        session.commit()
        second = import_active_ingredients(session, SOURCE)
        session.commit()

        assert first.created is True
        assert first.status == "completed"
        assert first.sheets == 5
        assert first.occurrences == 7_189
        assert first.values == 35_945
        assert first.quarantined_rows == 0
        assert first.diagnostics == 4
        assert second.created is False
        assert second.batch_id == first.batch_id
        assert second.occurrences == 7_189
        assert second.values == 35_945
        assert second.quarantined_rows == 0
        assert second.diagnostics == 4

        expected_counts = {
            ImportBatch: 1,
            ImportedSourceSheet: 5,
            SourceDocument: 1,
            SourceDocumentVersion: 1,
            TargetRecord: 7_189,
            DocumentRecordLink: 7_189,
            SourceFragment: 7_189,
            BlockInstance: 7_189,
            FieldValue: 35_945,
            ValueProvenance: 35_945,
            ImportDiagnostic: 4,
        }
        for model, expected in expected_counts.items():
            assert session.scalar(select(func.count()).select_from(model)) == expected

        empty_sheets = session.scalars(
            select(ImportedSourceSheet)
            .where(ImportedSourceSheet.data_row_count == 0)
            .order_by(ImportedSourceSheet.sheet_ordinal)
        ).all()
        assert [sheet.sheet_name for sheet in empty_sheets] == [
            "Frecuencia",
            "Via",
            "ConsejosAdministracion",
            "DatosAnaliticos",
        ]
        assert all(sheet.material_value_count == 0 for sheet in empty_sheets)
        header_payload = json.loads(empty_sheets[0].header_payload)
        assert header_payload
        assert all(cell["observed_type"] != "header" for cell in header_payload)

        sample = session.scalar(
            select(FieldValue).where(FieldValue.field_name == "IDEXTERNO").limit(1)
        )
        assert sample is not None
        provenance = session.scalar(
            select(ValueProvenance).where(ValueProvenance.field_value_id == sample.id)
        )
        assert provenance is not None
        assert provenance.provenance_role == "master_baseline"

    assert file_hash(SOURCE) == before


def test_invalid_workbook_fails_batch_and_keeps_diagnostic(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid-active-ingredients.xlsx"
    invalid.write_bytes(b"not an OOXML workbook")
    with migrated_session(tmp_path) as session:
        result = import_active_ingredients(session, invalid)
        session.commit()

        diagnostic = session.scalar(
            select(ImportDiagnostic).where(ImportDiagnostic.import_batch_id == result.batch_id)
        )
        assert result.status == "failed"
        assert result.occurrences == 0
        assert diagnostic is not None
        assert diagnostic.code == "ACTIVE_INGREDIENT_IMPORT_INVALID"
