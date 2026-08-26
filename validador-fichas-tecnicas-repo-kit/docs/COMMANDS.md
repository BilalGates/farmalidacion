# Superficie canónica de comandos

DEV-101 reserva una única superficie conceptual de comandos. Cada comando se habilitará en el issue que configure sus herramientas; no se añaden envoltorios que aparenten comprobaciones inexistentes.

| Comando conceptual | Finalidad | Estado |
|---|---|---|
| `test` | suite backend, frontend e integración | `python -m pytest tests backend/tests`; `npm --prefix frontend run test` |
| `lint` | estilo estático de Python y TypeScript | Ruff y `npm --prefix frontend run lint` |
| `typecheck` | tipos de backend y frontend | frontend incluido en `npm --prefix frontend run build`; backend pendiente |
| `verify` | tests, lint, tipos, referencias y migraciones | migraciones disponibles; unificación pendiente DEV-106 |
| `up` | levantar el entorno local | `docker compose up --build --detach --wait` |

Hasta que exista el ejecutor común, los únicos comandos canónicos disponibles son:

```text
python -m pytest tests backend/tests
python -m ruff check backend/src backend/tests
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run build
python scripts/verify_reference_files.py
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini downgrade base
docker compose up --build --detach --wait
docker compose down
```

No deben crearse convenciones paralelas por componente. DEV-102 a DEV-106 concretarán un ejecutor común compatible con el entorno del proyecto.
