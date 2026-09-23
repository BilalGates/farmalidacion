from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_validator_api.models import BlockInstance, ExternalIdentifier, FieldValue, TargetRecord

BACKEND = Path(__file__).resolve().parents[1]
DOMAIN_TABLES = {
    "catalog_field_definition",
    "import_batch",
    "import_diagnostic",
    "imported_source_sheet",
    "quarantined_source_row",
    "source_document_artifact",
    "sampling_item",
    "sampling_run",
    "block_instance",
    "document_record_link",
    "external_identifier",
    "field_value",
    "field_maintenance_revision",
    "source_document",
    "source_document_version",
    "source_fragment",
    "target_record",
    "target_record_link",
    "value_provenance",
    "medication_catalog_identity",
    "medication_catalog_relation",
    "medication_catalog_classification",
    "medication_catalog_revision",
}

CATALOG_TABLES = {
    "medication_catalog_identity",
    "medication_catalog_relation",
    "medication_catalog_classification",
    "medication_catalog_revision",
}


def alembic_config(database_path: Path) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_migration_preserves_repeated_occurrences_and_downgrades(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = alembic_config(database_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")

    assert set(inspect(engine).get_table_names()) >= DOMAIN_TABLES
    assert "source_column_index" in {
        column["name"] for column in inspect(engine).get_columns("field_value")
    }

    with Session(engine) as session:
        record = TargetRecord(entity_type="medication")
        session.add(record)
        session.flush()
        first = BlockInstance(target_record_id=record.id, block_type="composition", ordinal=1)
        second = BlockInstance(target_record_id=record.id, block_type="composition", ordinal=1)
        session.add_all([first, second])
        session.flush()
        session.add_all(
            [
                FieldValue(
                    block_instance_id=first.id,
                    field_name="description",
                    literal_value="omeprazol",
                    observed_type="text",
                    logical_state="valued",
                ),
                FieldValue(
                    block_instance_id=second.id,
                    field_name="description",
                    literal_value="omeprazol",
                    observed_type="text",
                    logical_state="valued",
                ),
            ]
        )
        session.commit()
        count = session.scalar(select(func.count()).select_from(BlockInstance))
        assert count == 2

    command.downgrade(config, "base")
    assert DOMAIN_TABLES.isdisjoint(inspect(engine).get_table_names())


def test_external_reference_is_versioned_and_unique(tmp_path: Path) -> None:
    database_path = tmp_path / "identity.db"
    config = alembic_config(database_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")

    with Session(engine) as session:
        first = TargetRecord(entity_type="specialty")
        second = TargetRecord(entity_type="specialty")
        session.add_all([first, second])
        session.flush()
        session.add(
            ExternalIdentifier(
                target_record_id=first.id,
                source_system="master",
                source_identifier="CN-1",
                source_version="2026-08-25",
            )
        )
        session.commit()
        session.add(
            ExternalIdentifier(
                target_record_id=second.id,
                source_system="master",
                source_identifier="CN-1",
                source_version="2026-08-25",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_source_column_migration_backfills_existing_imported_values(tmp_path: Path) -> None:
    database_path = tmp_path / "source-column-backfill.db"
    config = alembic_config(database_path)
    command.upgrade(config, "b8c9d0e1f2a3")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    block_id = "source-block"
    field_id = str(uuid5(NAMESPACE_URL, "\\x1f".join((block_id, "6", "field"))))
    payload = '[{"column":4,"header":"DESCRIPCION"},{"column":6,"header":"DESCRIPCION"}]'

    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO source_document (id, source_type, name) "
                "VALUES ('doc', 'master_excel', 'Medicamentos.xlsx')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO source_document_version "
                "(id, document_id, content_hash, source_version, source_locator, acquired_at) "
                "VALUES ('version', 'doc', 'hash', NULL, 'master.xlsx', '2026-09-23T00:00:00')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO source_fragment "
                "(id, document_version_id, locator_type, locator, literal_text) "
                "VALUES ('fragment', 'version', 'excel_row', '{}', :payload)"
            ),
            {"payload": payload},
        )
        connection.execute(
            sa.text("INSERT INTO target_record (id, entity_type) VALUES ('record', 'medication')")
        )
        connection.execute(
            sa.text(
                "INSERT INTO block_instance "
                "(id, target_record_id, block_type, ordinal, source_fragment_id) "
                "VALUES (:block, 'record', 'medication_link', 1, 'fragment')"
            ),
            {"block": block_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO field_value "
                "(id, block_instance_id, field_name, literal_value, observed_type, logical_state) "
                "VALUES (:field, :block, 'DESCRIPCION', 'texto F', 'text', 'valued')"
            ),
            {"field": field_id, "block": block_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO value_provenance "
                "(id, field_value_id, source_fragment_id, provenance_role) "
                "VALUES ('provenance', :field, 'fragment', 'master_baseline')"
            ),
            {"field": field_id},
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        index = connection.scalar(
            sa.text("SELECT source_column_index FROM field_value WHERE id = :field"),
            {"field": field_id},
        )
    assert index == 6


#: Recorridos que hace el listado de registros. Sin índice, cada uno degenera en
#: un SCAN de la tabla completa: con los maestros reales importados eso convirtió
#: `GET /records` en una petición de horas.
INDEXED_COLUMNS = {
    "block_instance": {"target_record_id"},
    "field_value": {"block_instance_id", "field_name"},
    "value_provenance": {"field_value_id", "source_fragment_id"},
    "external_identifier": {"target_record_id"},
    "validation_decision_record": {"field_value_id"},
}


def indexed_first_columns(engine: Engine, table: str) -> set[str]:
    """Primera columna de cada índice de la tabla.

    Se mira la primera y no todas: un índice compuesto sólo sirve para filtrar
    por su columna inicial, que es lo que aquí se afirma.
    """
    inspector = inspect(engine)
    return {
        index["column_names"][0]
        for index in inspector.get_indexes(table)
        if index["column_names"] and index["column_names"][0] is not None
    }


def test_traversal_columns_are_indexed_after_upgrade(tmp_path: Path) -> None:
    """Las claves por las que se recorre el modelo están indexadas.

    Ninguna lo estaba: el defecto sólo se manifiesta con datos reales, porque
    con cinco registros de demostración un SCAN completo es instantáneo.
    """
    database_path = tmp_path / "indexes.db"
    command.upgrade(alembic_config(database_path), "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        for table, expected in INDEXED_COLUMNS.items():
            missing = expected - indexed_first_columns(engine, table)
            assert missing == set(), f"{table} sin índice en {sorted(missing)}"
    finally:
        engine.dispose()


def test_index_migration_is_reversible(tmp_path: Path) -> None:
    """El gate del proyecto revierte hasta `base`; los índices deben caer."""
    database_path = tmp_path / "indexes-down.db"
    config = alembic_config(database_path)
    command.upgrade(config, "head")
    command.downgrade(config, "d51f7a2c9e04")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        assert "target_record_id" not in indexed_first_columns(engine, "block_instance")
    finally:
        engine.dispose()
    command.downgrade(config, "base")


def test_catalog_migration_is_additive_and_reversible(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog-migration.db"
    config = alembic_config(database_path)
    command.upgrade(config, "d5e6f7a8b9c0")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    before = set(inspect(engine).get_table_names())

    command.upgrade(config, "b8c9d0e1f2a3")
    after = set(inspect(engine).get_table_names())
    assert after == before | CATALOG_TABLES

    command.downgrade(config, "d5e6f7a8b9c0")
    assert set(inspect(engine).get_table_names()) == before
    engine.dispose()


def test_quarantine_maintenance_migration_is_reversible(tmp_path: Path) -> None:
    database_path = tmp_path / "quarantine-maintenance.db"
    config = alembic_config(database_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        assert "quarantined_field_maintenance_revision" in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.downgrade(config, "f7a8b9c0d1e2")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        assert "quarantined_field_maintenance_revision" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
    command.downgrade(config, "base")
