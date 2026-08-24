# Validador asistido de fichas técnicas

Kit inicial para arrancar el proyecto con Codex de forma controlada. Este repositorio no debe comenzar por la interfaz ni por el modelo local: comienza por reconciliar el modelo de datos real, las fuentes existentes y el contrato de exportación.

## Orden de lectura

1. `AGENTS.md`
2. `docs/PROJECT_CONTEXT.md`
3. `docs/DEVELOPMENT_PLAN.md`
4. `docs/DECISION_REGISTER.md`
5. `docs/BACKLOG.md`
6. `docs/reference/ESPEC_validador_fichas_tecnicas_v2.md`

## Primer objetivo

Demostrar que el modelo canónico puede importar el ejemplo completo de omeprazol, conservar todas las filas repetibles, claves y relaciones, y volver a exportarlo sin pérdida de información. Hasta superar esa puerta no se considera estable el modelo de dominio.

## Uso inicial con Codex

1. Copiar este kit a la raíz del repositorio recién creado.
2. Colocar los Excel originales en `data/reference/raw/`; esa carpeta está ignorada por Git.
3. Ejecutar `python scripts/verify_reference_files.py`.
4. Abrir Codex en la raíz y pedir: `Resume las instrucciones activas y ejecuta el arranque descrito en docs/INITIAL_CODEX_PROMPT.md sin escribir código de producto todavía.`
5. Trabajar una incidencia y una rama por unidad de cambio.

## Principios

- La IA localiza, cita y propone solo cuando la política lo permite; no toma decisiones clínicas.
- Ninguna propuesta se persiste sin evidencia literal o procedencia estructurada verificable.
- Los bloques repetibles son entidades de primera clase, no columnas forzadas en una fila única.
- Las versiones documentales son inmutables.
- No se trunca ni se descarta información en silencio.
- El sistema debe seguir siendo útil aunque el extractor se degrade a `solo_evidencia`.
