from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from pharma_validator_api.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    engine = create_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
