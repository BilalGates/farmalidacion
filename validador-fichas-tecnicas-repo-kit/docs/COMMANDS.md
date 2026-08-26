# Superficie canónica de comandos

DEV-106 establece una única superficie de verificación para el repositorio.

| Comando conceptual | Finalidad | Estado |
|---|---|---|
| `test` | suite backend, frontend e integración | incluido en `verify` |
| `lint` | estilo estático de Python y TypeScript | Ruff y ESLint incluidos en `verify` |
| `typecheck` | tipos de backend y frontend | mypy estricto; TypeScript incluido en el build |
| `verify` | tests, lint, tipos, build, referencias, Compose y migraciones | `python scripts/verify_project.py` |
| `up` | levantar el entorno local | `docker compose up --build --detach --wait` |

El gate canónico completo es:

```text
python scripts/verify_project.py
```

Ejecuta pytest, Ruff, mypy estricto, Vitest, ESLint, build TypeScript/Vite,
validación de Compose, hashes de las ocho referencias y upgrade/downgrade de
Alembic sobre una base SQLite temporal.

En CI se usa `python scripts/verify_project.py --skip-references` porque los
originales verificados no se versionan ni están disponibles en el checkout
remoto; el resto del gate es idéntico.

Los comandos operativos de contenedores son:

```text
docker compose up --build --detach --wait
docker compose down
```

No deben crearse convenciones paralelas por componente.
