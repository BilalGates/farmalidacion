from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import PurePosixPath

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from pharma_validator_api.config import Settings, get_settings
from pharma_validator_api.data_origin import DataOrigin, apply_origin_filter
from pharma_validator_api.database import create_database_engine, create_session_factory
from pharma_validator_api.errors import register_error_handlers
from pharma_validator_api.fixtures import load_demo_fixture, load_showcase_fixture
from pharma_validator_api.insights import router as insights_router
from pharma_validator_api.logging import configure_logging
from pharma_validator_api.models import ImportBatch, TargetRecord
from pharma_validator_api.records import router as records_router


def _database_label(database_url: str) -> str:
    """Nombre corto de la base, sin revelar la ruta que la contiene.

    Para SQLite interesa el nombre del fichero (`real`, `demo`, `validator`),
    que es justo lo que distingue un arranque de otro; para el resto de motores,
    el nombre de la base. El directorio no se publica.
    """
    url = make_url(database_url)
    name = url.database or ""
    stem = PurePosixPath(name.replace("\\", "/")).stem
    return stem or url.get_backend_name()


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class DatabaseInfoResponse(BaseModel):
    """Diagnóstico de qué base está sirviendo realmente el proceso.

    Existe porque el fallo operativo que motivó este endpoint no era de código:
    el backend servía datos de demostración desde un volumen de Docker mientras
    el código nuevo ya estaba desplegado, y nada en pantalla lo delataba.

    `mode` es lo que declara quien arranca el servicio; `records_real` y
    `records_demo` son lo que hay de verdad en la base. Se exponen los dos para
    que puedan contradecirse: `consistent` en falso significa que el modo
    prometido no se corresponde con lo almacenado.

    No se expone la URL de conexión ni ninguna ruta del sistema de ficheros:
    sólo el motor y el nombre del fichero, que es lo que hace falta para saber
    si dos procesos miran la misma base.
    """

    mode: str
    backend: str
    database: str
    records_total: int
    records_real: int
    records_demo: int
    import_batches: int
    consistent: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings or get_settings()
    configure_logging(active.log_level)
    engine = create_database_engine(active)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if active.load_demo_fixture:
            with session_factory() as session:
                load_demo_fixture(session, active.demo_fixture_path)
        if active.load_showcase_fixture:
            with session_factory() as session:
                load_showcase_fixture(session, active.showcase_fixture_path)
        yield
        engine.dispose()

    application = FastAPI(
        title=active.app_name,
        version="0.1.0",
        docs_url="/docs" if active.env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.session_factory = session_factory
    application.state.settings = active
    if active.cors_allow_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(active.cors_allow_origins),
            allow_methods=['GET', 'POST'],
            allow_headers=['Content-Type'],
        )
    register_error_handlers(application)
    application.include_router(records_router)
    application.include_router(insights_router)

    @application.get("/health", response_model=HealthResponse, tags=["sistema"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service=active.app_name, environment=active.env)

    @application.get(
        "/database-info", response_model=DatabaseInfoResponse, tags=["sistema"]
    )
    def database_info() -> DatabaseInfoResponse:
        with session_factory() as session:
            total = session.scalar(select(func.count()).select_from(TargetRecord)) or 0
            demo = (
                session.scalar(
                    select(func.count()).select_from(
                        apply_origin_filter(
                            select(TargetRecord.id), DataOrigin.DEMO
                        ).subquery()
                    )
                )
                or 0
            )
            batches = session.scalar(select(func.count()).select_from(ImportBatch)) or 0
        real = total - demo
        # Un modo REAL sin ningún registro real es la avería concreta que se
        # quiere poder ver: la base está migrada pero la ingesta no se ha
        # ejecutado. Se declara inconsistente en lugar de responder «ok».
        consistent = real > 0 if active.data_mode == "real" else demo > 0
        return DatabaseInfoResponse(
            mode=active.data_mode,
            backend=make_url(active.database_url).get_backend_name(),
            database=_database_label(active.database_url),
            records_total=total,
            records_real=real,
            records_demo=demo,
            import_batches=batches,
            consistent=consistent,
        )

    return application


app = create_app()
