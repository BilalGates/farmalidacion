from fastapi.testclient import TestClient

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app


def test_health_reports_process_state() -> None:
    app = create_app(Settings(env='test', _env_file=None))
    response = TestClient(app).get('/health')
    assert response.status_code == 200
    assert response.json() == {
        'status': 'ok',
        'service': 'Validador de fichas técnicas',
        'environment': 'test',
    }


def test_production_disables_interactive_docs() -> None:
    app = create_app(Settings(env='production', _env_file=None))
    client = TestClient(app)
    assert client.get('/docs').status_code == 404
    assert client.get('/openapi.json').status_code == 200
