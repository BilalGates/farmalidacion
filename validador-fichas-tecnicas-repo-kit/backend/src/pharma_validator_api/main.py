from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from pharma_validator_api.config import Settings, get_settings
from pharma_validator_api.database import create_database_engine, create_session_factory
from pharma_validator_api.errors import register_error_handlers
from pharma_validator_api.fixtures import load_demo_fixture
from pharma_validator_api.logging import configure_logging
from pharma_validator_api.records import router as records_router


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


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
    register_error_handlers(application)
    application.include_router(records_router)

    @application.get("/health", response_model=HealthResponse, tags=["sistema"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service=active.app_name, environment=active.env)

    return application


app = create_app()
