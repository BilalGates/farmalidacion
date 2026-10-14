"""La publicación de Vercel debe servir una demo sintética sin disco persistente."""

from fastapi.testclient import TestClient

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app


def test_vercel_demo_bootstraps_and_allows_public_frontend(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    app = create_app(Settings(database_url="sqlite:///./data/local/validator.db", _env_file=None))

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        database = client.get("/database-info")
        assert database.status_code == 200
        assert database.json()["mode"] == "demo"
        assert database.json()["records_demo"] > 0
        assert database.json()["records_real"] == 0
        assert client.get("/auth/config").status_code == 200
        reviewers = client.get("/records/reviewers")
        assert reviewers.status_code == 200
        assert len(reviewers.json()) == 2
        response = client.options(
            "/auth/config",
            headers={
                "Origin": "https://farmalidacion-beta.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == (
            "https://farmalidacion-beta.vercel.app"
        )
