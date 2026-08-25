import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def controlled(request: Request, exc: ApplicationError) -> JSONResponse:
        logger.warning('Error controlado en %s', request.url.path)
        return JSONResponse(status_code=exc.status_code, content={'detail': exc.message})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception('Error inesperado en %s', request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500, content={'detail': 'Se ha producido un error interno.'}
        )
