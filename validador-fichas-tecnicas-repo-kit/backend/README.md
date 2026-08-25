# Backend

Backend HTTP de la aplicación. DEV-102 proporciona infraestructura técnica: factoría FastAPI, configuración tipada, logging JSON, errores seguros y `GET /health`.

## Desarrollo

```text
python -m pip install -e 'backend[dev]'
python -m pytest tests backend/tests
python -m ruff check backend/src backend/tests
python -m uvicorn pharma_validator_api.main:app --app-dir backend/src
```

El health check confirma el proceso. La base de datos se comprobará tras DEV-104.
