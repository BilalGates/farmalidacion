# Perfil del proyecto: Farmalidación

> Manda sobre todo lo genérico de `AGENTS.md`. Lo mantiene Pep; si algo de aquí
> deja de ser cierto, se corrige aquí antes de seguir trabajando.

## Qué es

Aplicación web interna de **consolidación y validación farmacéutica de datos maestros de medicamentos**: importa los maestros Excel (especialidades, medicamentos, principios activos), los contrasta con CIMA (AEMPS) y el Nomenclátor, y un farmacéutico valida campo a campo con procedencia verificable, doble validación y exportación reproducible. **No es un sistema de apoyo a la decisión clínica.**

El código vive en `validador-fichas-tecnicas-repo-kit/` (backend y frontend). La raíz del repositorio solo contiene este kit de agentes, documentación general y el catálogo de campos clínicos.

## Por dónde empezar

Antes de planificar o cambiar código, en este orden:

1. `validador-fichas-tecnicas-repo-kit/docs/PROJECT_CONTEXT.md`
2. `validador-fichas-tecnicas-repo-kit/docs/STATUS.md` y `docs/DEVELOPMENT_PLAN.md`
3. `validador-fichas-tecnicas-repo-kit/docs/DECISION_REGISTER.md` y los ADR aceptados de `docs/decisions/`
4. La sección que toque de `docs/reference/ESPEC_validador_fichas_tecnicas_v2.md`
5. `validador-fichas-tecnicas-repo-kit/AGENTS.md` (reglas originales del producto, en inglés)

Los ADR aceptados prevalecen sobre las propuestas; la especificación v2 manda en las decisiones cerradas del cliente y en los límites de seguridad. Un conflicto nunca se resuelve en silencio: se anota en el registro de decisiones y se propone un ADR.

## Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Alembic (`backend/migrations`). SQLite en el piloto con tipos portables; ver `docs/DATABASE_PORTABILITY.md`.
- **Frontend:** React 19, TypeScript, Vite, Vitest + Testing Library (happy-dom), ESLint. CSS propio por capas (sin Tailwind): ver *Interfaz* abajo.
- **Entorno:** Docker Compose con perfiles `demo` y `real` (puertos 8000 backend, 5173 frontend). Despliegue alojado en Coolify (ADR 0017).
- **Autenticación:** Microsoft Entra ID por operación (ADR 0015); en piloto, identidad declarada.

## Comandos

Desde `validador-fichas-tecnicas-repo-kit/`:

| Para | Comando |
|---|---|
| Puerta completa (tests, lint, tipos, build, migraciones, Compose) | `python scripts/verify_project.py` |
| Tests frontend | `cd frontend && npx vitest run` |
| Lint frontend | `cd frontend && npm run lint` |
| Build frontend (incluye `tsc -b`) | `cd frontend && npm run build` |
| Tests backend | `cd backend && python -m pytest` |
| Entorno DEMO | `docker compose --profile demo up --build --detach --wait` (o `scripts/start-demo.ps1`) |
| Entorno REAL | `scripts/start-real.ps1` (exige `data/local/real.db`; la ingesta tarda ~25 min) |
| Frontend en desarrollo | `cd frontend && npx vite --port 5173` (comparte puerto con el contenedor del frontend: no los dos a la vez) |

No se inventan convenciones paralelas de comandos (DEV-106).

## Ramas y entrega

- Rama de trabajo por encargo (`ui-pulido`, `nomenclator-persistente`…); `main` recibe por PR.
- **Commits** (los hace Larry): asunto en castellano que empieza por un verbo en infinitivo con mayúscula, sin prefijo de tipo, ≤ 72 caracteres; cuerpo en castellano con el porqué y lo verificado. Trailer de coautoría cuando lo indique la sesión.
- Push, merge y PR: el usuario.

## Reglas que no se negocian

Producto (de `validador-fichas-tecnicas-repo-kit/AGENTS.md`):

- Nunca datos de pacientes ni recomendaciones clínicas.
- Nunca preseleccionar valores en `proponer_opciones` ni `solo_evidencia`.
- Nunca guardar una propuesta sin procedencia verificable; la evidencia literal de la ficha técnica coincide exactamente con la versión inmutable citada.
- Nunca inferir, calcular, convertir, redondear ni normalizar un valor clínico sin una regla aceptada.
- Los bloques repetidos se modelan explícitamente (composiciones, indicaciones, vías, excipientes…).
- Las versiones de documentos fuente son inmutables; toda propuesta y validación apunta a una versión concreta.
- Nunca truncar, descartar ni coaccionar un valor de origen en silencio: diagnóstico.
- Un registro con discrepancias de doble validación abiertas no se exporta. Ninguna discrepancia se resuelve automáticamente.
- REAL y DEMO no se mezclan nunca en la misma vista ni consulta.
- Interfaz y mensajes en **castellano**, tratando de **tú**.

Proceso:

- Disciplina de fases de `docs/DEVELOPMENT_PLAN.md`.
- Un único agente escribe por rama o worktree.
- Sin dependencias nuevas sin consenso; sin secretos en el repositorio.

## Interfaz

La identidad visual está decidida (rama `ui-pulido`, maquetas aprobadas) y se respeta: ver la skill **`farmalidacion-ui`** antes de tocar cualquier pantalla o estilo. Resumen: tokens únicos en `frontend/src/ui/tokens.css`, capa común en `ui/components.css`, estructura en `ui/shell.css`, filtros en `ui/filters.css` (pieza `FilterBar`), hojas por pantalla en `screens/*.css`. Las hojas históricas `styles.css` y `studio.css` solo se vacían, nunca crecen.

## Al terminar un trabajo

1. Tests, lint y build del frontend (y `pytest` si se tocó el backend); en cambios amplios, `python scripts/verify_project.py`.
2. Si el cambio es visual: capturas antes/después de las rutas afectadas, en claro y oscuro (procedimiento en `farmalidacion-ui`).
3. Actualizar `docs/STATUS.md`, backlog, trazabilidad y ADR cuando cambie comportamiento o una decisión.
4. Larry commitea; el usuario hace push y PR.

## Skills del proyecto

| Skill | Para qué |
|---|---|
| `farmalidacion-dominio` | Reglas de producto, modelo de validación, procedencia, REAL/DEMO, exportación. Cárgala si el cambio toca datos, validación o exportación. |
| `farmalidacion-ui` | Sistema visual, capas CSS, componentes, voz de los textos y verificación con capturas. Cárgala para cualquier cambio de interfaz. |

Genéricas especialmente útiles aquí: `ui-ux-pro-max` (con las salvedades de su sección «En Farmalidación»), `migraciones-bd`, `tests`, `revision-codigo`. `supabase-postgres-best-practices` solo aplica si el despliegue alojado usa PostgreSQL.
