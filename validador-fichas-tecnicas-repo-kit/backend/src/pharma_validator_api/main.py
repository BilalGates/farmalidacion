from fastapi import FastAPI
from pydantic import BaseModel

from pharma_validator_api.config import Settings, get_settings
from pharma_validator_api.errors import register_error_handlers
from pharma_validator_api.logging import configure_logging


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings or get_settings()
    configure_logging(active.log_level)
    application = FastAPI(
        title=active.app_name,
        version="0.1.0",
        docs_url="/docs" if active.env != "production" else None,
        redoc_url=None,
    )
    register_error_handlers(application)

    @application.get("/health", response_model=HealthResponse, tags=["sistema"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service=active.app_name, environment=active.env)

    return application


app = create_app()
