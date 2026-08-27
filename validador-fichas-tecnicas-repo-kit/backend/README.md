# Backend

Backend HTTP de la aplicación. Incluye infraestructura técnica, persistencia
canónica inicial y el corte vertical de lectura de DEV-107.

## Desarrollo

```text
python -m pip install -e 'backend[dev]'
python -m pytest tests backend/tests
python -m ruff check backend/src backend/tests
python -m uvicorn pharma_validator_api.main:app --app-dir backend/src
```

El health check confirma el proceso. `GET /records/{record_id}` devuelve un
registro con identificadores, ocurrencias de bloque, valores y procedencia.

## Migraciones

```text
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini downgrade base
```

La URL puede sobrescribirse con `APP_DATABASE_URL`. El esquema de DEV-104 es un núcleo inicial reversible; no representa el contrato físico del proveedor.

El fixture sintético puede activarse explícitamente con
`APP_LOAD_DEMO_FIXTURE=true` y `APP_DEMO_FIXTURE_PATH`. La carga es
idempotente y falla ante una colisión distinta en lugar de sobrescribirla.

## Cliente CIMA

`pharma_validator_api.cima_client.CimaClient` ofrece las consultas mínimas de
CIMA como GET de solo lectura. Timeout, límite de peticiones, reintentos y ruta
de caché se configuran con las variables `APP_CIMA_*` documentadas en
`.env.example`.

La caché es inmutable y conserva el cuerpo HTTP original junto a un manifiesto
SHA-256. Una discrepancia de integridad detiene la lectura; no vuelve a pedir ni
sobrescribe automáticamente la evidencia. Solo se cachean respuestas 2xx y no
se interpretan los datos ni se persisten en el modelo canónico. Las pruebas del
cliente usan transporte simulado y no necesitan red.

El módulo `pharma_validator_api.sampling` consume páginas originales de
`/medicamentos` desde disco, exige inventario completo y persiste criterios e
ítems sin duplicarlos. Ambos modos requieren `--modo` y `--seed`; el contrato y
el ejemplo operativo están en `docs/CIMA_SAMPLING_CONTRACT.md` y
`docs/COMMANDS.md`.
