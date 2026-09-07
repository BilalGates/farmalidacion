from pathlib import Path

from sqlalchemy import text

from pharma_validator_api.config import Settings
from pharma_validator_api.database import create_database_engine


def test_sqlite_connection_reserves_cache_and_keeps_foreign_keys(tmp_path: Path) -> None:
    """La caché por defecto de SQLite hace inviable la carga REAL de 1,7 GB.

    Reservar caché y mmap deja las páginas residentes: el recuento de
    `value_provenance` pasa de 11,3 s en frío a 10 ms. La integridad referencial
    no se sacrifica por ello: ambas cosas conviven.
    """
    engine = create_database_engine(Settings(database_url=f"sqlite:///{tmp_path / 'probe.db'}"))

    with engine.connect() as connection:
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        cache_size = connection.execute(text("PRAGMA cache_size")).scalar_one()
        mmap_size = connection.execute(text("PRAGMA mmap_size")).scalar_one()

    assert foreign_keys == 1
    # Negativo: kibibytes reservados, no número de páginas.
    assert cache_size == -(256 * 1024)
    # SQLite trunca mmap_size al límite de página: importa que quede activo y
    # con el orden de magnitud pedido, no el byte exacto.
    assert mmap_size >= 2 * 1024 * 1024 * 1024 - 65536
