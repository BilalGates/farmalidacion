from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from pharma_validator_api.config import Settings

# La caché por defecto de SQLite (~2 MB) obliga a releer del disco casi cada
# página de una base de 1,7 GB. Medido sobre la carga REAL con caché fría, el
# recuento de `value_provenance` (2,17 M filas) baja de 11,3 s a 10 ms una vez
# las páginas quedan residentes. No se alteran datos, esquema ni cardinalidades:
# sólo el acceso de lectura.
_SQLITE_CACHE_BYTES = 256 * 1024 * 1024
_SQLITE_MMAP_BYTES = 2 * 1024 * 1024 * 1024


def create_database_engine(settings: Settings) -> Engine:
    engine = create_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        event.listen(engine, "connect", _configure_sqlite_connection)
    return engine


def _configure_sqlite_connection(
    dbapi_connection: DBAPIConnection,
    _connection_record: ConnectionPoolEntry,
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    # cache_size negativo se interpreta en kibibytes, no en páginas.
    cursor.execute(f"PRAGMA cache_size=-{_SQLITE_CACHE_BYTES // 1024}")
    cursor.execute(f"PRAGMA mmap_size={_SQLITE_MMAP_BYTES}")
    cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
