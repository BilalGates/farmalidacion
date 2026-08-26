# Backlog inicial

Prioridades: `P0` bloquea fases; `P1` necesaria para la puerta; `P2` mejora o endurecimiento. Los identificadores se mantienen aunque las issues se creen después en GitHub.

## EPIC E0 — Gobierno y descubrimiento

### DEV-001 — Instalar el sistema operativo del repositorio (`P0`)

**Objetivo:** copiar y validar `AGENTS.md`, agentes, skill, documentos y ficheros de referencia.

**Aceptación:** Codex enumera instrucciones, agentes y skill; el verificador de hashes pasa; `STATUS.md` refleja el arranque.

**Estado:** completada el 24 de agosto de 2026. Evidencia: 8/8 referencias `OK`, código 0, y Fase 0A cerrada en `STATUS.md`.

### DEV-002A — Definir contrato de perfilado reproducible (`P0`)

**Objetivo:** fijar entradas, invariantes, seguridad, reproducibilidad y formatos del perfilado sin implementarlo.

**Salida:** `docs/contracts/PROFILING_CONTRACT.md` con manifiesto, JSON agregado por libro/hoja, CSV de columnas, incidencias resumidas y resumen Markdown. Relaciones detalladas diferidas a DEV-004/DEV-006.

**Aceptación:** contrato revisado, siete Excel identificados, originales inmutables, ocurrencias explícitas y ninguna normalización implícita.

**Estado:** completada documentalmente el 24 de agosto de 2026.

### DEV-002 — Crear perfilador reproducible de Excel (`P0`)

**Objetivo:** inspeccionar todas las hojas sin modificar los originales.

**Salida:** JSON/CSV y Markdown con filas materialmente pobladas, columnas, tipos observados, nulos, longitudes, duplicados, fórmulas y claves candidatas.

**Aceptación:** dos ejecuciones sobre los mismos hashes producen el mismo informe.

**Estado:** completada el 25 de agosto de 2026. Evidencia: 7/7 Excel, 730 columnas, tests 5/5 y dos corridas de 115,605 s y 321,479 s con hash común `1999097257b99fe5cc52ab903da873085dd9abe5deb7b0a1d327670f04875976`. Cardinalidades superiores a 100.000 valores quedan estimadas y señaladas; relaciones/huérfanos detallados permanecen pendientes.

### DEV-003 — Reconstruir el catálogo canónico (`P0`)

**Objetivo:** definir el modelo conceptual canónico capaz de representar sin pérdida maestros, CIMA, ficha técnica y bloques repetibles, sin fijar esquema físico.

**Aceptación:** ADR, diagrama, tabla de entidades/bloques/cardinalidades/claves candidatas y cobertura documental de las 22 hojas de omeprazol sin pérdida de ocurrencias.

**Estado:** completada documentalmente. ADR-0001 fue aceptado posteriormente tras round-trip y aprobación humana; esquema físico pendiente.

### DEV-004 — Mapear cardinalidades y claves por bloque (`P0`)

**Objetivo:** definir uno-a-uno, uno-a-muchos y claves naturales de cada hoja.

**Aceptación:** tabla revisable y tests sobre ejemplos reales.

**Estado:** completada y aceptada el 25 de agosto de 2026. ADR-0005/D-004 adoptan PK canónica propia e identificadores externos versionados; ninguna unicidad observada se convierte en clave natural.

### DEV-005 — Resolver relación entre CIMA y registros destino (`P0`)

**Objetivo:** cerrar D-001, D-002 y D-006.

**Aceptación:** ADR-0001 aceptado o reemplazado; ejemplos de uno-a-varios y varios-a-varios.

**Estado:** completada y aceptada el 25 de agosto de 2026. Los maestros demuestran especialidad→medicamento y composición→principio activo, pero no contienen `nregistro`. ADR-0006 aceptado; D-001, D-002 y D-006 cerradas en su alcance conceptual. La cardinalidad factual `nregistro`↔CN se verificará con CIMA estructurado en Fase 2 sin reabrir equivalencias implícitas.

### DEV-006 — Definir matriz de fuentes por campo (`P0`)

**Objetivo:** indicar fuente primaria, secundaria, prioridad, conflicto y acción humana.

**Aceptación:** todos los campos activos tienen regla o estado explícito pendiente.

**Estado:** completada y aceptada el 25 de agosto de 2026. Las 353 filas del catálogo quedan cubiertas mediante cuatro reglas de clasificación FT: 204 `No`, 53 directas, 79 parciales y 17 interpretables. Todas conservan el maestro como línea base y una prioridad autoritativa explícita o `pending_human_validation`. ADR-0007 aceptado y D-008 cerrada; excepciones concretas y mapeo CIMA siguen pendientes de evidencia.

### DEV-007 — Prueba de importación de omeprazol (`P0`)

**Objetivo:** representar las 22 hojas en el modelo canónico candidato.

**Aceptación:** recuentos y valores materialmente poblados conciliados.

**Estado:** completada el 25 de agosto de 2026 como spike reversible. Las 22/22 hojas, 616 filas materiales y 2.674 valores se conservaron con coordenada y procedencia, sin identidad de negocio inferida. Dos corridas produjeron instantáneas idénticas con hash canónico `5e8564dcd726380aec23f031f6060e4450d2c0fa09f559589e9c6d32caebdb5f`; los recuentos por hoja coinciden con DEV-002 y la suite completa pasa 12/12. Evidencia en `docs/OMEPRAZOLE_CANONICAL_IMPORT_EVIDENCE.md`.

### DEV-008 — Prueba de exportación y comparación semántica (`P0`)

**Objetivo:** reconstruir omeprazol y comparar hoja por hoja.

**Aceptación:** cero pérdidas; diferencias clasificadas y aprobadas.

**Estado:** completada como spike reversible: 22/22 hojas, 2.674/2.674 valores y cero diferencias. No es exportador final; permitió aceptar ADR-0001 conceptualmente.

### DEV-008A — Definir contrato semántico del round-trip (`P0`)

**Objetivo:** fijar igualdad literal, normalizaciones autorizadas, multiplicidad, relaciones, clasificación de diferencias e informe para las 22 hojas.

**Aceptación:** ninguna normalización implícita; toda diferencia tiene evidencia y categoría; defecto o diferencia no resuelta produce fallo.

**Estado:** completada documentalmente el 24 de agosto de 2026.

### DEV-011 — Validar semántica de estados D-010 (`P0`)

**Objetivo:** validar con farmacia y proveedor las diferencias entre vacío de fuente, pendiente, `no_consta`, `no_aplica` y valor presente.

**Aceptación:** ADR-0004 aceptado o sustituido con reglas de autoridad, transición y exportación verificadas.

**Estado:** cerrada el 25 de agosto de 2026 bajo excepción explícita de Gate 0B. ADR-0004 aceptado; serialización trasladada a PROVIDER-002 y no bloquea Fase 1.

**Evidencia DEV-011:** `docs/VALUE_STATE_VALIDATION_TABLE.md`. Aprobación humana registrada; pendiente exclusivamente el contrato de representación del proveedor.

### DEV-009 — Reproducir incidencias de integridad (`P1`)

**Objetivo:** comprobar huérfanos de excipientes, duplicados y límites de longitud.

**Aceptación:** informe reproducible con ejemplos y severidad.

**Estado:** completada el 25 de agosto de 2026. Dos corridas idénticas reprodujeron 275 huérfanos/184 claves, seis incidencias de duplicado, cuatro excesos, 24 valores al límite y dos conflictos de tipo. Hash `987129be4c8d7b62517c0962e19279e01b00299c7c51490e179137b3040579e7`; evidencia en `docs/INTEGRITY_INCIDENT_EVIDENCE.md`. No se corrigieron originales.

### DEV-010 — Cerrar estrategia de interacciones (`P0`)

**Objetivo:** aceptar, cambiar o descartar ADR-0003.

**Aceptación:** alcance y backlog separados claramente.

**Estado:** completada el 24 de agosto de 2026. D-009 cerrada y ADR-0003 aceptado por decisión humana; la migración/conciliación permanece como línea separada.

## EPIC E1 — Scaffold de aplicación

### DEV-101 — Crear estructura del repositorio (`P0`)

Backend, frontend, infraestructura, scripts, docs y datos de ejemplo.

**Aceptación:** límites de componentes documentados, configuración de ejemplo sin secretos, datos de ejemplo separados y superficie única de comandos definida sin simular herramientas aún no configuradas.

**Estado:** completado el 25 de agosto de 2026. Scaffold estructural creado sin frameworks, lógica de producto, esquema físico, migraciones ni servicios.

### DEV-102 — Configurar backend (`P0`)

FastAPI, configuración, logging, health check, pytest y lint.

**Estado:** completado el 25 de agosto de 2026. Paquete backend aislado con configuración Pydantic, logs JSON, errores seguros, health check, pytest y Ruff; sin persistencia ni lógica de producto.

### DEV-103 — Configurar frontend (`P0`)

React, TypeScript, Vite, Vitest, lint y shell visual mínimo.

**Estado:** completado el 25 de agosto de 2026. Shell técnico accesible en español con React/TypeScript, configuración por entorno, Vitest sobre happy-dom, ESLint y build Vite; sin flujo farmacéutico ni llamadas de red.

### DEV-104 — Configurar SQLite y Alembic (`P0`)

Migración inicial del modelo aceptado, upgrade/downgrade y fixtures.

**Estado:** completado el 25 de agosto de 2026. Núcleo físico inicial reversible con UUID canónica, identificadores externos versionados, documentos/versiones, destinos, vínculos, bloques, valores y procedencia. Tests sobre SQLite temporal; fixture de omeprazol diferido a DEV-107.

### DEV-105 — Crear Docker Compose (`P0`)

Arranque limpio con backend, frontend y datos de demostración.

**Estado:** completado el 26 de agosto de 2026 en alcance de scaffold. Backend y frontend construyen y quedan saludables; Alembic aplica de forma idempotente sobre volumen SQLite. El fixture canónico de demostración sigue asignado a DEV-107.

### DEV-106 — Crear CI (`P1`)

Tests, lint, typecheck, build y verificación de migraciones.

**Estado:** completado el 26 de agosto de 2026. GitHub Actions ejecuta el verificador único con Python 3.12 y Node 24. La verificación local completa pasó 26/26 tests Python, 1/1 test frontend, Ruff, mypy estricto, ESLint, build Vite, Compose, 8/8 hashes y Alembic upgrade/downgrade. CI omite únicamente las referencias originales no versionadas mediante una opción explícita.

### DEV-107 — Primer corte vertical de lectura (`P0`)

Importar fixture y visualizar por API un registro con bloques repetibles.

## EPIC E2 — CIMA y documentos

### DEV-201 — Verificar contrato de API CIMA (`P0`)

Documentar endpoints y parámetros exactos desde fuente oficial.

### DEV-202 — Cliente CIMA robusto (`P0`)

Rate limit, reintentos, timeouts, cache e idempotencia.

### DEV-203 — Muestreo reproducible (`P0`)

Aleatorio y estratificado, semilla, criterios y persistencia.

### DEV-204 — Informe de composición (`P1`)

ATC, forma y vía; salida legible y datos exportables.

### DEV-205 — Versionado inmutable (`P0`)

Documento, versión, sección, hash y metadatos.

### DEV-206 — Detección y diff de versiones (`P1`)

Preparación para mantenimiento continuo.

### DEV-207 — Corpus offline (`P0`)

Fixtures y operación sin red.

## EPIC E3 — Maestros y consolidación

### DEV-301 — Infraestructura común de importadores (`P0`)

Lotes, hashes, idempotencia, diagnósticos y cuarentena.

### DEV-302 — Importador de catálogo (`P0`)

Incluye overrides CHAR(100) y preserva tipos originales.

### DEV-303 — Importador de principio activo (`P1`)

### DEV-304 — Importador de medicamento (`P1`)

### DEV-305 — Importador de especialidad (`P1`)

### DEV-306 — Importador o exclusión formal de interacciones (`P1`)

### DEV-307 — Motor de conflictos de procedencia (`P0`)

### DEV-308 — Informes de calidad de datos (`P1`)

Longitudes, tipos, duplicados, huérfanos, nulos y catálogos.

## EPIC E4 — Extractor local

### DEV-401 — Contrato `ExtractorLLM` (`P0`)

### DEV-402 — Adaptador de servidor local (`P0`)

### DEV-403 — Esquema de salida guiada (`P0`)

### DEV-404 — Agrupación por sección (`P1`)

### DEV-405 — Verificador literal de evidencia (`P0`)

### DEV-406 — Procesamiento reanudable por lotes (`P1`)

### DEV-407 — Herramienta de anotación del conjunto oro (`P0`)

### DEV-408 — Benchmark de dos modelos (`P0`)

### DEV-409 — Política configurable por resultados (`P0`)

## EPIC E5 — Revisión farmacéutica

### DEV-501 — Selector de usuario (`P0`)

### DEV-502 — Cola y asignación de lotes (`P0`)

### DEV-503 — Pantalla de tres zonas (`P0`)

### DEV-504 — Navegación completa por teclado (`P0`)

### DEV-505 — Guardado incremental (`P0`)

### DEV-506 — Estados de validación (`P0`)

### DEV-507 — Editor de bloques repetibles (`P0`)

### DEV-508 — Medición de tiempo (`P1`)

### DEV-509 — Rendimiento y precarga (`P1`)

### DEV-510 — Tests de sesgo de automatización (`P0`)

### DEV-511 — Ejecución del conjunto de medida (`P0`)

## EPIC E6 — Exportación, riesgo y auditoría

### DEV-601 — Cerrar contrato de exportación (`P0`)

### DEV-602 — Exportadores CSV/TXT/XLSX (`P0`)

### DEV-603 — Validador de tipos y longitudes (`P0`)

### DEV-604 — Informe de exportación (`P1`)

### DEV-605 — Exportación reproducible (`P1`)

### DEV-606 — Reglas ATC por prefijo (`P0`)

### DEV-607 — Segunda validación ciega (`P0`)

### DEV-608 — Conciliación (`P0`)

### DEV-609 — Auditoría append-only (`P0`)

### DEV-610 — Prueba de carga con proveedor (`P0`)

## EPIC E7 — Mantenimiento

### DEV-701 — Consulta de cambios CIMA (`P0`)

### DEV-702 — Revisión pendiente selectiva (`P0`)

### DEV-703 — Panel de novedades y diff (`P1`)

### DEV-704 — Operación programada y alertas (`P1`)

### DEV-705 — Chat contextual citado (`P2`)

## Orden recomendado de las primeras issues

`DEV-001 (completada) → DEV-002A (completada) → DEV-002 → DEV-003 → DEV-004 → DEV-005 → DEV-006 → DEV-007 → DEV-008A (completada) → DEV-008 → DEV-009 → DEV-010 (completada) → DEV-011`

Solo después: `DEV-101` en adelante.
