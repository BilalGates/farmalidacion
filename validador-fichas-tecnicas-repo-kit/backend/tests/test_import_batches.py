from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config

from pharma_validator_api.import_batches import (
    ImportBatchRequest,
    complete_import_batch,
    fail_import_batch,
    get_or_create_import_batch,
    quarantine_source_row,
    record_diagnostic,
)
from pharma_validator_api.models import ImportBatch, ImportDiagnostic, QuarantinedSourceRow


def migrated_session(tmp_path: Path) -> Session:
    database_path = tmp_path / "imports.db"
    command.upgrade(alembic_config(database_path), "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    return Session(engine)


def test_same_source_and_importer_reuses_batch_without_duplicates(tmp_path: Path) -> None:
    request = ImportBatchRequest(
        source_system="master_excel",
        source_locator="catalog.xlsx",
        source_bytes=b"exact workbook bytes",
        importer_name="catalog",
        importer_version="1",
    )
    with migrated_session(tmp_path) as session:
        first, first_created = get_or_create_import_batch(session, request)
        complete_import_batch(first, now=datetime(2026, 8, 31, tzinfo=UTC))
        session.commit()
        second, second_created = get_or_create_import_batch(session, request)
        assert first_created is True
        assert second_created is False
        assert second.id == first.id
        assert second.status == "completed"
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 1


def test_changed_source_bytes_create_a_new_batch(tmp_path: Path) -> None:
    common = {
        "source_system": "master_excel",
        "source_locator": "catalog.xlsx",
        "importer_name": "catalog",
        "importer_version": "1",
    }
    with migrated_session(tmp_path) as session:
        first, _ = get_or_create_import_batch(
            session, ImportBatchRequest(source_bytes=b"version one", **common)
        )
        second, _ = get_or_create_import_batch(
            session, ImportBatchRequest(source_bytes=b"version two", **common)
        )
        session.commit()
        assert first.id != second.id
        assert first.content_hash != second.content_hash


def test_literal_source_version_is_part_of_batch_identity(tmp_path: Path) -> None:
    common = {
        "source_system": "master_excel",
        "source_locator": "catalog.xlsx",
        "source_bytes": b"same exact bytes",
        "importer_name": "catalog",
        "importer_version": "1",
    }
    with migrated_session(tmp_path) as session:
        first, _ = get_or_create_import_batch(
            session, ImportBatchRequest(source_version="entrega-1", **common)
        )
        second, _ = get_or_create_import_batch(
            session, ImportBatchRequest(source_version="entrega-2", **common)
        )
        session.commit()
        assert first.id != second.id
        assert first.source_version == "entrega-1"
        assert second.source_version == "entrega-2"


def test_diagnostic_and_quarantine_are_idempotent_and_lossless(tmp_path: Path) -> None:
    raw_payload = '{"A":"  S*  ","B":null}'
    with migrated_session(tmp_path) as session:
        batch, _ = get_or_create_import_batch(
            session,
            ImportBatchRequest(
                source_system="master_excel",
                source_locator="catalog.xlsx",
                source_bytes=b"workbook",
                importer_name="catalog",
                importer_version="1",
            ),
        )
        diagnostic, diagnostic_created = record_diagnostic(
            session,
            batch=batch,
            severity="warning",
            code="ORPHAN_REFERENCE",
            message="Referencia no resuelta",
            source_locator="Excipientes!42",
            details_literal='{"identifier":"0007"}',
            occurrence_count=184,
        )
        repeated_diagnostic, repeated_diagnostic_created = record_diagnostic(
            session,
            batch=batch,
            severity="warning",
            code="ORPHAN_REFERENCE",
            message="Referencia no resuelta",
            source_locator="Excipientes!42",
            details_literal='{"identifier":"0007"}',
            occurrence_count=184,
        )
        quarantined, quarantined_created = quarantine_source_row(
            session,
            batch=batch,
            source_locator="Excipientes!42",
            reason_code="ORPHAN_REFERENCE",
            reason="No existe destino reconciliado",
            raw_payload=raw_payload,
        )
        repeated_quarantine, repeated_quarantine_created = quarantine_source_row(
            session,
            batch=batch,
            source_locator="Excipientes!42",
            reason_code="ORPHAN_REFERENCE",
            reason="No existe destino reconciliado",
            raw_payload=raw_payload,
        )
        session.commit()
        assert diagnostic_created is True
        assert repeated_diagnostic_created is False
        assert repeated_diagnostic.id == diagnostic.id
        assert quarantined_created is True
        assert repeated_quarantine_created is False
        assert repeated_quarantine.id == quarantined.id
        assert quarantined.raw_payload == raw_payload
        assert session.scalar(select(func.count()).select_from(ImportDiagnostic)) == 1
        assert session.scalar(select(func.count()).select_from(QuarantinedSourceRow)) == 1


def test_failed_batch_keeps_diagnostics(tmp_path: Path) -> None:
    with migrated_session(tmp_path) as session:
        batch, _ = get_or_create_import_batch(
            session,
            ImportBatchRequest(
                source_system="master_excel",
                source_locator="broken.xlsx",
                source_bytes=b"broken",
                importer_name="catalog",
                importer_version="1",
            ),
        )
        record_diagnostic(
            session,
            batch=batch,
            severity="error",
            code="INVALID_HEADER",
            message="No se encontró la cabecera declarada",
        )
        fail_import_batch(batch, now=datetime(2026, 8, 31, tzinfo=UTC))
        session.commit()
        stored = session.get(ImportBatch, batch.id)
        assert stored is not None
        assert stored.status == "failed"
        assert session.scalar(select(func.count()).select_from(ImportDiagnostic)) == 1
