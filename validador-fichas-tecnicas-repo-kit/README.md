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

## Desarrollo

Los comandos canónicos y su estado de disponibilidad se documentan en `docs/COMMANDS.md`. Por ahora:

```text
python -m unittest discover -s tests -v
python scripts/verify_reference_files.py
```

La configuración local partirá de `.env.example`; nunca se versionan secretos ni ficheros `.env` reales.

## Principios

- La IA localiza, cita y propone solo cuando la política lo permite; no toma decisiones clínicas.
- Ninguna propuesta se persiste sin evidencia literal o procedencia estructurada verificable.
- Los bloques repetibles son entidades de primera clase, no columnas forzadas en una fila única.
- Las versiones documentales son inmutables.
- No se trunca ni se descarta información en silencio.
- El sistema debe seguir siendo útil aunque el extractor se degrade a `solo_evidencia`.
