"""Orquestación de la ingesta de maestros (Fase 3, mitad ejecutable).

Los importadores por fichero ya tenían pruebas propias. Lo que aquí se
comprueba es la composición: el orden de dependencia, la selección parcial, la
idempotencia de la reejecución y el rechazo de entradas ausentes.

Las pruebas que recorren los maestros grandes reales son lentas por naturaleza
(el maestro de especialidades ronda los 8 MB), así que sólo se ejercitan los
ficheros pequeños salvo donde el enlace entre entidades es justamente lo que se
afirma.
"""

from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from test_database_migrations import alembic_config

from pharma_validator_api.master_ingestion import (
    MASTER_SOURCES,
    MasterIngestionError,
    ingest_masters,
    resolve_sources,
)
from pharma_validator_api.models import (
    BlockInstance,
    CatalogFieldDefinition,
    FieldValue,
    ImportBatch,
    TargetRecord,
)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "reference" / "raw"


def migrated_session(tmp_path: Path) -> Session:
    database_path = tmp_path / "masters.db"
    command.upgrade(alembic_config(database_path), "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    return Session(engine)


def test_declared_order_matches_the_data_dependency() -> None:
    """Los enlaces se resuelven contra lo ya importado, así que el orden importa."""
    keys = [source.key for source in MASTER_SOURCES]
    assert keys.index("active_ingredients") < keys.index("medications")
    assert keys.index("medications") < keys.index("specialties")


def test_partial_selection_preserves_dependency_order() -> None:
    """Pedirlos al revés no los importa al revés."""
    selected = resolve_sources(RAW, only=["specialties", "active_ingredients"])
    assert [source.key for source in selected] == ["active_ingredients", "specialties"]


def test_unknown_source_is_rejected_by_name() -> None:
    with pytest.raises(MasterIngestionError, match="Maestros desconocidos"):
        resolve_sources(RAW, only=["inexistente"])


def test_missing_file_is_reported_before_touching_the_database(tmp_path: Path) -> None:
    """Un directorio sin maestros falla al resolver, no a mitad de la ingesta."""
    with pytest.raises(MasterIngestionError, match="Faltan ficheros maestros"):
        resolve_sources(tmp_path, only=["catalog"])


def test_catalog_ingestion_reports_metrics_and_batch(tmp_path: Path) -> None:
    with migrated_session(tmp_path) as session:
        report = ingest_masters(session, RAW, only=["catalog"])

    assert report.ok
    assert [item.key for item in report.sources] == ["catalog"]
    catalog = report.sources[0]
    assert catalog.created is True
    assert catalog.skipped_as_duplicate is False
    assert catalog.batch_id
    assert len(catalog.content_hash) == 64
    assert catalog.metrics["imported_fields"] > 0


def test_reingesting_the_same_files_does_not_duplicate(tmp_path: Path) -> None:
    """La segunda pasada reutiliza el lote: es la puerta de salida de la Fase 3."""
    with migrated_session(tmp_path) as session:
        first = ingest_masters(session, RAW, only=["catalog", "active_ingredients"])
        second = ingest_masters(session, RAW, only=["catalog", "active_ingredients"])

    assert first.ok and second.ok
    assert all(item.created for item in first.sources)
    assert all(item.skipped_as_duplicate for item in second.sources)
    assert [item.batch_id for item in first.sources] == [
        item.batch_id for item in second.sources
    ]
    # Sólo se comparan las métricas que cuentan filas persistidas. Al reutilizar
    # un lote los importadores recuentan lo almacenado, pero no reproducen los
    # contadores transitorios de la pasada original (diagnósticos, cuarentena):
    # ésos describen el trabajo de importar, no el contenido importado.
    persisted = ("imported_fields", "occurrences", "values", "sheets")
    for before, after in zip(first.sources, second.sources, strict=True):
        for name in persisted:
            assert before.metrics.get(name) == after.metrics.get(name), name


def test_reingestion_leaves_the_stored_rows_untouched(tmp_path: Path) -> None:
    """La afirmación de la puerta de salida se mide en la base, no en el informe."""
    counted = (CatalogFieldDefinition, TargetRecord, BlockInstance, FieldValue, ImportBatch)
    with migrated_session(tmp_path) as session:
        ingest_masters(session, RAW, only=["catalog", "active_ingredients"])
        before = {
            model.__name__: session.scalar(select(func.count()).select_from(model))
            for model in counted
        }
        ingest_masters(session, RAW, only=["catalog", "active_ingredients"])
        after = {
            model.__name__: session.scalar(select(func.count()).select_from(model))
            for model in counted
        }

    assert before == after
    assert before["CatalogFieldDefinition"] > 0
    assert before["TargetRecord"] > 0
