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

## Migraciones

```text
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini downgrade base
```

La URL puede sobrescribirse con `APP_DATABASE_URL`. El esquema de DEV-104 es un núcleo inicial reversible; no representa el contrato físico del proveedor.
