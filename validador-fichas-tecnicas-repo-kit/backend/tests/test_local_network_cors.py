from fastapi.testclient import TestClient

from pharma_validator_api.config import Settings
from pharma_validator_api.main import create_app


def test_allows_private_network_preflight_from_configured_frontend() -> None:
    origin = "https://farmalidacion-beta.vercel.app"
    app = create_app(
        Settings(
            env="test",
            data_mode="real",
            database_url="sqlite://",
            cors_allow_origins=(origin,),
        )
    )

    with TestClient(app) as client:
        response = client.options(
            "/auth/config",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
                "Access-Control-Request-Private-Network": "true",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-private-network"] == "true"
