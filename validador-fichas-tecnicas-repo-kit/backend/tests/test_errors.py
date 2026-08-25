from fastapi import FastAPI
from fastapi.testclient import TestClient

from pharma_validator_api.errors import ApplicationError, register_error_handlers


def build_error_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get('/controlled')
    async def controlled_error() -> None:
        raise ApplicationError('Solicitud no válida.', status_code=422)

    @app.get('/unexpected')
    async def unexpected_error() -> None:
        raise RuntimeError('detalle privado')

    return app


def test_controlled_error_keeps_public_message() -> None:
    response = TestClient(build_error_app()).get('/controlled')
    assert response.status_code == 422
    assert response.json() == {'detail': 'Solicitud no válida.'}


def test_unexpected_error_hides_internal_detail() -> None:
    response = TestClient(build_error_app(), raise_server_exceptions=False).get('/unexpected')
    assert response.status_code == 500
    assert response.json() == {'detail': 'Se ha producido un error interno.'}
    assert 'detalle privado' not in response.text
