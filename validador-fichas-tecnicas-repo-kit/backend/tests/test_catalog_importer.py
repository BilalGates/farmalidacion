import hashlib
import json
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config

from pharma_validator_api.catalog_importer import CATALOG_FILENAME, import_catalog
from pharma_validator_api.models import CatalogFieldDefinition, ImportBatch, ImportDiagnostic

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "reference" / "raw" / CATALOG_FILENAME
EXPECTED_HASH = "a10160ebe5c7fe0b5d2a35a12d4597c982bacdafe04cb0f8d98c437183d19eac"


def migrated_session(tmp_path: Path) -> Session:
    database_path = tmp_path / "catalog.db"
    command.upgrade(alembic_config(database_path), "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    return Session(engine)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.slow
@pytest.mark.reference
def test_real_catalog_import_is_lossless_and_idempotent(tmp_path: Path) -> None:
    before = file_hash(CATALOG)
    assert before == EXPECTED_HASH

    with migrated_session(tmp_path) as session:
        first = import_catalog(session, CATALOG)
        session.commit()
        second = import_catalog(session, CATALOG)
        session.commit()

        assert first.created is True
        assert first.status == "completed"
        assert first.imported_fields == 353
        assert first.diagnostics == 7
        assert second.created is False
        assert second.batch_id == first.batch_id
        assert second.imported_fields == 353
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 1
        assert session.scalar(select(func.count()).select_from(CatalogFieldDefinition)) == 353
        assert session.scalar(select(func.count()).select_from(ImportDiagnostic)) == 7

    assert file_hash(CATALOG) == before


def test_overrides_preserve_declared_type_and_source_literals(tmp_path: Path) -> None:
    with migrated_session(tmp_path) as session:
        result = import_catalog(session, CATALOG)
        session.commit()
        rows = session.scalars(
            select(CatalogFieldDefinition)
            .where(
                CatalogFieldDefinition.import_batch_id == result.batch_id,
                CatalogFieldDefinition.field_name_literal.in_(
                    ["EX_DESCRIPCION", "ME_DESCRIPCION"]
                ),
            )
            .order_by(CatalogFieldDefinition.field_name_literal)
        ).all()

        assert len(rows) == 2
        for row in rows:
            assert row.declared_type_literal == "CHAR(20)"
            assert row.effective_type == "CHAR(100)"
            assert row.override_decision == "D-021"
            assert row.required_literal == "N*"
            payload = json.loads(row.raw_payload)
            projected_type = next(
                cell["literal_value"] for cell in payload if cell["header"] == "Tipo"
            )
            assert projected_type == "CHAR(20)"


def test_repeated_identities_and_conflicting_types_are_not_collapsed(tmp_path: Path) -> None:
    with migrated_session(tmp_path) as session:
        result = import_catalog(session, CATALOG)
        session.commit()
        composition_descriptions = session.scalars(
            select(CatalogFieldDefinition).where(
                CatalogFieldDefinition.import_batch_id == result.batch_id,
                CatalogFieldDefinition.block_literal == "Medicamento - Composición",
                CatalogFieldDefinition.field_name_literal == "DESCRIPCION",
            )
        ).all()

        assert len(composition_descriptions) == 2
        assert {row.declared_type_literal for row in composition_descriptions} == {
            "CHAR(50)",
            "CHAR(100)",
        }
        assert {row.effective_type for row in composition_descriptions} == {"CHAR(100)"}
        assert {row.override_decision for row in composition_descriptions} == {"D-026"}
        assert len({row.source_row_number for row in composition_descriptions}) == 2

        link_descriptions = session.scalars(
            select(CatalogFieldDefinition).where(
                CatalogFieldDefinition.import_batch_id == result.batch_id,
                CatalogFieldDefinition.block_literal == "Medicamento - Links",
                CatalogFieldDefinition.field_name_literal == "DESCRIPCION",
            )
        ).all()
        assert {row.declared_type_literal for row in link_descriptions} == {
            "CHAR(100)",
            "CHAR(255)",
        }
        assert {row.effective_type for row in link_descriptions} == {"CHAR(255)"}
        assert {row.override_decision for row in link_descriptions} == {"D-026"}


def test_missing_catalog_sheet_fails_batch_and_keeps_diagnostic(tmp_path: Path) -> None:
    copied = tmp_path / "invalid.xlsx"
    copied.write_bytes(b"not an OOXML workbook")
    with migrated_session(tmp_path) as session:
        result = import_catalog(session, copied)
        session.commit()

        batch = session.get(ImportBatch, result.batch_id)
        diagnostic = session.scalar(
            select(ImportDiagnostic).where(ImportDiagnostic.import_batch_id == result.batch_id)
        )
        assert result.status == "failed"
        assert result.imported_fields == 0
        assert batch is not None and batch.status == "failed"
        assert diagnostic is not None
        assert diagnostic.code == "CATALOG_IMPORT_INVALID"
        assert diagnostic.message
