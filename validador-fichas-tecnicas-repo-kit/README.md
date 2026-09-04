# Validador asistido de fichas técnicas

Aplicación interna para consolidar y validar datos de medicamentos con procedencia verificable. La Fase 0B está cerrada y el repositorio inicia su scaffold ejecutable en Fase 1.

## Orden de lectura

1. `AGENTS.md`
2. `docs/PROJECT_CONTEXT.md`
3. `docs/DEVELOPMENT_PLAN.md`
4. `docs/DECISION_REGISTER.md`
5. `docs/BACKLOG.md`
6. `docs/reference/ESPEC_validador_fichas_tecnicas_v2.md`

## Estructura

- `backend/`: aplicación y pruebas del backend a partir de DEV-102.
- `frontend/`: aplicación web y pruebas a partir de DEV-103.
- `infra/`: composición y soporte local a partir de DEV-105.
- `data/examples/`: fixtures pequeños, anonimizados y versionables.
- `scripts/`: utilidades reproducibles del repositorio.
- `docs/`: contratos, decisiones, evidencias y estado.

DEV-101 solo establece estos límites. No instala frameworks ni fija el esquema físico.

## Arranque reproducible

La única ruta soportada para levantar la demostración completa es:

```text
docker compose up --build --detach --wait
```

Después quedan disponibles la interfaz en `http://localhost:5173`, la API en
`http://localhost:8000`, su documentación en `http://localhost:8000/docs` y la
salud en `http://localhost:8000/health`. Compose aplica las migraciones antes de
arrancar la API y carga de forma idempotente los fixtures DEMO sobre el volumen
SQLite `app-data`; las decisiones sobreviven a los reinicios.

El gate completo del repositorio es `python scripts/verify_project.py`. El resto
de comandos canónicos se documenta en `docs/COMMANDS.md`. `.env.example` sirve
solo para desarrollo fuera de contenedores; nunca se versionan secretos ni
ficheros `.env` reales.

## Principios

- La IA localiza, cita y propone solo cuando la política lo permite; no toma decisiones clínicas.
- Ninguna propuesta se persiste sin evidencia literal o procedencia estructurada verificable.
- Los bloques repetibles son entidades de primera clase, no columnas forzadas en una fila única.
- Las versiones documentales son inmutables.
- No se trunca ni se descarta información en silencio.
- El sistema debe seguir siendo útil aunque el extractor se degrade a `solo_evidencia`.
