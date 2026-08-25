# Superficie canónica de comandos

DEV-101 reserva una única superficie conceptual de comandos. Cada comando se habilitará en el issue que configure sus herramientas; no se añaden envoltorios que aparenten comprobaciones inexistentes.

| Comando conceptual | Finalidad | Estado |
|---|---|---|
| `test` | suite backend, frontend e integración | backend: `python -m pytest tests backend/tests` |
| `lint` | estilo estático de Python y TypeScript | backend: `python -m ruff check backend/src backend/tests` |
| `typecheck` | tipos de backend y frontend | pendiente DEV-103 y decisión de herramienta backend |
| `verify` | tests, lint, tipos, referencias y migraciones | pendiente DEV-106 |
| `up` | levantar el entorno local | pendiente DEV-105 |

Hasta que exista el ejecutor común, los únicos comandos canónicos disponibles son:

```text
python -m pytest tests backend/tests
python -m ruff check backend/src backend/tests
python scripts/verify_reference_files.py
```

No deben crearse convenciones paralelas por componente. DEV-102 a DEV-106 concretarán un ejecutor común compatible con el entorno del proyecto.
