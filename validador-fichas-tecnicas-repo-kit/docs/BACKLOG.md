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

**Estado:** completado el 27 de agosto de 2026. Fixture sintético cargado de
forma idempotente; API de solo lectura verificada con dos ocurrencias idénticas
pero separadas y con procedencia distinta. Compose conserva exactamente dos
bloques tras reiniciar el backend. Gate 1 cerrado; Fase 2 no iniciada.

## EPIC E2 — CIMA y documentos

### DEV-201 — Verificar contrato de API CIMA (`P0`)

Documentar endpoints y parámetros exactos desde fuente oficial.

**Estado:** completado documentalmente el 27 de agosto de 2026. Contrato CIMA
REST API v1.23 registrado en `docs/CIMA_API_CONTRACT.md` con endpoints,
parámetros, respuestas, ambigüedades y evidencia puntual. La negociación viva
de `docSegmentado/contenido` queda como prueba explícita de DEV-202 tras dos
fallos de cliente; no se implementó integración.

### DEV-202 — Cliente CIMA robusto (`P0`)

Rate limit, reintentos, timeouts, cache e idempotencia.

**Estado:** completado el 27 de agosto de 2026. Cliente de solo lectura con
configuración por entorno, límite de ritmo, timeout, reintentos acotados y
caché inmutable verificada por SHA-256. Las pruebas HTTP son offline y
preservan el cuerpo original byte a byte; no se descargó corpus ni se persistió
información CIMA. La validación viva y reproducible de contenido segmentado se
traslada a DEV-203 sin asumir formato ni semántica.

### DEV-203 — Muestreo reproducible (`P0`)

Aleatorio y estratificado, semilla, criterios y persistencia.

**Estado:** completado como capacidad reproducible el 27 de agosto de 2026.
Ambos modos, filtros de elegibilidad, integridad paginada, manifiesto y
persistencia idempotente están verificados offline, incluida una muestra
sintética exacta de 500. No se descargó ni seleccionó el corpus real. D-016
continúa pendiente del informe de composición de DEV-204.

### DEV-204 — Informe de composición (`P1`)

ATC, forma y vía; salida legible y datos exportables.

**Estado:** completado como capacidad reproducible el 27 de agosto de 2026.
Genera JSON, CSV y Markdown inmutables con recuento multilabel de documentos y
ocurrencias, sin normalizar metadatos CIMA. No existe aún informe del corpus
real; D-016 permanece abierta y no se ha recomendado un modo de muestreo.

### DEV-205 — Versionado inmutable (`P0`)

Documento, versión, sección, hash y metadatos.

**Estado:** completado como capacidad reversible el 27 de agosto de 2026.
Los artefactos CIMA originales se conservan byte a byte en versiones
content-addressed e idempotentes; un cambio crea otra versión y la anterior no
se modifica. D-020 permaneció propuesta al cerrar DEV-205 porque no se infería
`source_version` y aún faltaba evidencia documental real; DEV-208 permitió aceptarla.

### DEV-206 — Detección y diff de versiones (`P1`)

Preparación para mantenimiento continuo.

**Estado:** completado como capacidad reproducible el 28 de agosto de 2026.
Compara artefactos inmutables por rol/ordinal y genera JSON/Markdown con diff
textual completo o clasificación binaria explícita. No decide vigencia, no
marca validaciones y no implementa todavía la tarea de `registroCambios`.

### DEV-207 — Corpus offline (`P0`)

Fixtures y operación sin red.

**Estado:** completado primero con fixture sintético y confirmado después sobre
el corpus real de DEV-208: 500 documentos, 1.000 artefactos y segunda carga
idempotente con sockets bloqueados.

### DEV-208 — Captura comparativa real CIMA (`P0`)

**Estado:** captura de inventario completada y decisión bloqueada el 28 de
agosto de 2026. Una caché ZIP atómica compatible con Windows permitió conservar
81/81 páginas, 16.093 candidatos y 19.353.056 bytes; instantánea
`72e9b05fd60a524fa9115c09fee9f29e98779a8c5c95565fe6d0bee4395c27cb`.
Las 16.093 filas del inventario omiten ATC y no permiten estratificar. Se aceptó
la muestra aleatoria con semilla 203 sin lanzar 16.093 consultas adicionales.
Se descargaron y verificaron offline 500 documentos, 1.000 artefactos y
115.583.103 bytes. D-016 y D-020 quedan cerradas; Gate 2 es PASS.

## EPIC E3 — Maestros y consolidación

### DEV-301 — Infraestructura común de importadores (`P0`)

Lotes, hashes, idempotencia, diagnósticos y cuarentena.

**Estado:** completada el 31 de agosto de 2026. Migración reversible y servicio común con identidad content-addressed/versionada, diagnósticos y cuarentena literal; 7 pruebas dirigidas. No se importó ningún maestro y DEV-302 no se inició.

### DEV-302 — Importador de catálogo (`P0`)

Incluye overrides CHAR(100) y preserva tipos originales.

**Estado:** completada el 31 de agosto de 2026. Importadas 353/353 definiciones con fila, payload, tipo OOXML y tipo declarado conservados; segunda ejecución idempotente. D-021/D-026 se aplican como overrides trazables sin truncar ni modificar el Excel. Se mantienen cinco identidades repetidas y dos conflictos de tipo como siete diagnósticos. DEV-303 no iniciado.

### DEV-303 — Importador de principio activo (`P1`)

**Estado:** completada el 1 de septiembre de 2026. Importadas cinco hojas, 7.189 ocurrencias y 35.945 valores con versión, fragmento y procedencia; segunda ejecución idempotente. Cuatro hojas solo-cabecera quedan como diagnósticos informativos, no como cardinalidad canónica. Cero cuarentenas; original intacto. DEV-304 no iniciado.

### DEV-304 — Importador de medicamento (`P1`)

**Estado:** completada el 1 de septiembre de 2026. Importadas siete hojas, 58.256 ocurrencias y 509.496 valores con procedencia; 4.211 vínculos de composición a principio activo; segunda ejecución idempotente y cero cuarentenas. Dos hojas solo-cabecera quedan como diagnósticos informativos. Prueba real completa en 208,47 s; original intacto. DEV-305 no iniciado.

### DEV-305 — Importador de especialidad (`P1`)

**Estado:** completada el 1 de septiembre de 2026. Importadas dos hojas: 48.195 ocurrencias válidas y 1.623.810 valores con procedencia; 29.850 vínculos especialidad→medicamento. Las 275 filas de excipiente sin padre, correspondientes a 184 identificadores, quedan reproducidas individualmente en cuarentena y no se reparan. Segunda ejecución idempotente; prueba real en 171,99 s; original intacto. DEV-306 no iniciado.

### DEV-306 — Importador o exclusión formal de interacciones (`P1`)

**Estado:** completada el 1 de septiembre de 2026 por exclusión formal y reversible de la importación del piloto, conforme a D-009/ADR-0003. El maestro permanece en el proyecto como línea separada de migración/conciliación; no se importaron ni descartaron sus 872.296 filas. `docs/INTERACTION_MIGRATION_BOUNDARY.md` registra evidencia y los trabajos INT-001..INT-005 sobre fuente, identidad, ciclo de vida, muestra y entrega. Al cerrar DEV-306, Gate 3 seguía abierto y DEV-307 no se había iniciado.

**Backlog separado de interacciones:**

- `INT-001`: confirmar fuente autoritativa, actualización y versionado.
- `INT-002`: aprobar identidad y claves sin deduplicación implícita.
- `INT-003`: definir altas, modificaciones, bajas y conciliación histórica.
- `INT-004`: importar una muestra reproducible y estimar el flujo completo.
- `INT-005`: confirmar contrato y separación de entrega con el proveedor.

### DEV-307 — Motor de conflictos de procedencia (`P0`)

**Estado:** completada el 2 de septiembre de 2026. Motor determinista sobre afirmaciones explícitas, identidad completa de catálogo y comparación exacta de estado/literal. Las reglas pendientes no seleccionan; una regla aceptada requiere decisión humana y campo exacto. Se conservan todas las afirmaciones y procedencias, incluso al resolver por prioridad. Sin prioridades concretas, matching implícito, migración o exportación. Contrato en `docs/PROVENANCE_CONFLICT_ENGINE.md`; al cerrar DEV-307, DEV-308 no se había iniciado y Gate 3 seguía abierto.

### DEV-308 — Informes de calidad de datos (`P1`)

**Estado:** completada el 2 de septiembre de 2026. Consolidador agregado sobre DEV-002/009, sin salida por celda. Dos corridas de 0,462 s y 0,336 s produjeron artefactos idénticos y el hash 4009cac62bb27974ee3ff15a6b863a03cbb090816e220cb2aee66da128745d48. Reproduce 275 huérfanos/184 claves, 6 grupos de duplicados, 4 excesos y 24 valores al límite. Gate 3 fue cerrado posteriormente como PASS; Fase 4 no iniciada.

## Gate 3 — PASS

Revisión formal en docs/PHASE_3_GATE_REVIEW.md. Fase 3 cerrada; D-013 está resuelta con servidor interno de al menos 24 GB de VRAM. La apertura formal de Fase 4 sigue pendiente de herramienta, dos anotadores identificados (GOLD-002) y conjunto oro anotado.

## EPIC E4 — Extractor local

### DEV-401 — Contrato `ExtractorLLM` (`P0`)

**Objetivo:** desacoplar el motor de inferencia mediante una interfaz sustituible por configuración, con petición agrupada por sección y verificación obligatoria antes de admitir una propuesta.

**Salida:** `pharma_validator_api.extractor` y `docs/EXTRACTOR_INTERFACE_CONTRACT.md`.

**Aceptación:** la implementación es sustituible pero no puede puentear el verificador de DEV-405; las peticiones agrupan campos por apartado; toda propuesta admitida queda atribuida a versión de extractor y modelo; un fallo del extractor no bloquea la revisión manual; campo no solicitado, duplicado o ausente producen incidencia.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-401 ni abre Fase 4. Evidencia: 12 pruebas, Ruff y mypy limpios. No requiere GPU; DEV-402 sí.

### DEV-402 — Adaptador de servidor local (`P0`)

### DEV-403 — Esquema de salida guiada (`P0`)

**Objetivo:** gobernar la decodificación del modelo con un esquema JSON cerrado y validar la respuesta contra los tipos declarados en el catálogo, sin reparar.

**Salida:** `pharma_validator_api.guided_schema` y `docs/GUIDED_SCHEMA_CONTRACT.md`.

**Aceptación:** esquema cerrado con `required` completo y recuento de resultados fijado; longitud de evidencia acotada a 10..400; la sección la aporta la petición y no el modelo; `CHAR` que excede, `DECIMAL` con exceso de escala o precisión y `BIT` inválido fallan con error legible sin truncar ni redondear; campo desconocido, duplicado o ausente rechazados.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-403 ni abre Fase 4. Evidencia: 22 pruebas, Ruff y mypy limpios. La traducción a GBNF es DEV-402.

### DEV-404 — Agrupación por sección (`P1`)

**Objetivo:** agrupar los campos extraíbles en una petición por apartado de la ficha técnica, según la especificación 8, sin reinterpretar el catálogo.

**Salida:** `pharma_validator_api.section_grouping` y `docs/SECTION_GROUPING_CONTRACT.md`.

**Aceptación:** literales simples y múltiples reconocidos; orden del literal no significativo; un campo citado en varios apartados se pide en todos; apartado no reconocido, ausente o inexistente produce diagnóstico y nunca una suposición; campo repetido informado sin deduplicar el catálogo; política `oculto` no se solicita.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-404 ni abre Fase 4. Evidencia: 17 pruebas y validación sobre el catálogo real (353 definiciones, 129 campos extraíbles, 14 llamadas, 245 diagnósticos). No requiere GPU.

### DEV-405 — Verificador literal de evidencia (`P0`)

**Objetivo:** impedir por construcción que se persista una propuesta cuya cita no aparezca literalmente en la versión inmutable citada.

**Salida:** `pharma_validator_api.evidence_verification` y `docs/EVIDENCE_VERIFICATION_CONTRACT.md`.

**Aceptación:** cita verificada por igualdad exacta sobre el texto canónico sin desescapar ni normalizar; cita inventada, desplazada o desescapada rechazada; longitud 10..400; `no_encontrado` admitido solo sin valor; campos protegidos nunca preseleccionados; módulo puro y determinista.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-405 ni abre Fase 4. Evidencia: 19 pruebas específicas, validación sobre ficha real del corpus, Ruff y mypy limpios. No requiere GPU.

### DEV-406 — Procesamiento reanudable por lotes (`P1`)

**Objetivo:** planificar la extracción de forma reanudable, con la configuración de prompt, esquema y modelo como parte de la identidad del trabajo.

**Salida:** `pharma_validator_api.extraction_batches` y `docs/EXTRACTION_BATCH_CONTRACT.md`.

**Aceptación:** un lote interrumpido reanuda solo lo que falta; una unidad se reutiliza únicamente con la misma huella de configuración; cambiar modelo, prompt o esquema supera el trabajo anterior sin borrarlo; el reintento de incidencias es configurable; estado ajeno se ignora; dos peticiones con la misma unidad o un estado repetido son errores de uso explícitos.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-406 ni abre Fase 4. Evidencia: 17 pruebas, Ruff y mypy limpios. No requiere GPU.

### DEV-407 — Herramienta de anotación del conjunto oro (`P0`)

**Objetivo:** seleccionar de forma reproducible las 20 fichas del conjunto oro desde el corpus de DEV-208 y permitir su anotación farmacéutica con evidencia literal verificable.

**Salida:** `docs/GOLD_SET_ANNOTATION_CONTRACT.md` (contrato definido) y la herramienta con `gold-selection.json`, `gold-annotations.jsonl`, `gold-disagreements.csv`, `run-manifest.json` y `summary.md`.

**Aceptación:** los nueve criterios del contrato. En particular: selección reproducible desde el universo de 500; evidencia citada por desplazamientos sobre el HTML literal sin desescapar ni normalizar; ocurrencias repetibles sin concatenar; ausencia, vacío, `no_consta` y `not_applicable` distinguibles; desacuerdos conservados sin resolución automática.

**Estado:** contrato definido el 2 de septiembre de 2026. Selección implementada y verificada el 3 de septiembre de 2026 en `pharma_validator_api.gold_selection`: criterio 1 cumplido sobre el corpus real de 500 (`run_id` estable `ac843f92c081045bd61ed80d6aef13c703f88275eeab433291ddb6ce9dd792cd`), y criterios 8 y 9 cumplidos en lo que atañe a la selección. 13 pruebas, Ruff y mypy limpios.

**Actualización técnica:** el núcleo puro `gold_annotations` y la CLI `scripts/generate_gold_annotations.py` implementan los criterios 2 a 8: evidencia por desplazamientos exactos sobre HTML literal, ocurrencias separadas, estados distinguibles, bloqueo de cierre por `pending`, doble anotación y desacuerdos abiertos, más las cinco salidas deterministas sin sobrescritura. Ocho pruebas específicas y 36 pruebas de pureza verifican el comportamiento. **GOLD-002 continúa pendiente** y bloquea la anotación real; por tanto DEV-407 no se cierra ni abre Fase 4.

### DEV-408 — Benchmark de dos modelos (`P0`)

### DEV-409 — Política configurable por resultados (`P0`)

## EPIC E5 — Revisión farmacéutica

### DEV-501 — Selector de usuario (`P0`)

**Objetivo:** resolver quién firma una validación desde una lista configurable y rechazar cualquier guardado sin revisor seleccionado.

**Salida:** `pharma_validator_api.reviewer_identity`, ajuste `APP_REVIEWERS` y `docs/REVIEWER_IDENTITY_CONTRACT.md`.

**Aceptación:** lista construida desde configuración; revisor ausente y revisor desconocido son errores distintos; una lista vacía no firma nada; la garantía es `declarada` y está explícita en el tipo; la doble validación exige dos revisores distintos.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-501 ni abre Fase 5. Evidencia: 15 pruebas, Ruff y mypy limpios.

La vertical demostrable del 3 de septiembre de 2026 añadió el selector de revisor en la cabecera y el endpoint `GET /records/reviewers`. **Sigue pendiente** la persistencia de la elección en el navegador entre sesiones.

### DEV-502 — Cola y asignación de lotes (`P0`)

**Estado:** no iniciada. La vertical demostrable ofrece un listado con búsqueda y filtro, que no es una cola de trabajo: no hay lotes, asignación ni prevención de colisiones.

### DEV-503 — Pantalla de tres zonas (`P0`)

**Estado:** no cerrada. La vertical demostrable incluye una ficha por bloques con valor, fuente, procedencia y estado, pero no la disposición de tres zonas con evidencia contextual que exige la especificación.

### DEV-504 — Navegación completa por teclado (`P0`)

**Estado:** no iniciada. La vertical usa navegación estándar del navegador; los atajos de revisión sin ratón no existen.

### DEV-505 — Guardado incremental (`P0`)

**Estado:** parcialmente adelantado por la vertical demostrable. Existe guardado por campo, persistido y verificado tras reinicio (`test_decision_survives_a_restart`). **Siguen pendientes** la precarga del siguiente campo, el objetivo de cambio de campo inferior a 100 ms (DEV-509) y la garantía de que recargar la pestaña a mitad de edición no pierda trabajo no confirmado.

### DEV-506 — Estados de validación (`P0`)

**Objetivo:** fijar los estados internos de decisión humana, sus transiciones legítimas y el cierre de revisión, de forma verificable e independiente de la interfaz y sin decidir la serialización del proveedor.

**Salida:** `pharma_validator_api.validation_states` y `docs/VALIDATION_STATES_CONTRACT.md`.

**Aceptación:** `no_consta` exige haber revisado las fuentes obligatorias declaradas y solo lo decide un farmacéutico; `no_aplica` es estado propio con comentario obligatorio; ningún estado salvo `confirmado`/`corregido` admite valor final; nada resuelto vuelve a `pendiente`; un cambio de versión marca y no borra; la doble validación sin conciliar retiene el registro. No se traduce al contrato del proveedor.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-506 ni abre Fase 5. Evidencia: 15 pruebas, Ruff y mypy limpios. La serialización del proveedor no existe todavía.

La vertical demostrable del 3 de septiembre de 2026 añadió persistencia append-only de las decisiones (`validation_decision_record`) con historial consultable e inmutable, delegando toda la regla en este módulo. **Sigue pendiente** la auditoría transversal (Fase 6) y la traducción al contrato del proveedor (D-011).

### DEV-507 — Editor de bloques repetibles (`P0`)

**Objetivo:** permitir crear, eliminar, ordenar, fusionar y marcar no aplicable las ocurrencias de un bloque sin violar la regla de ocurrencias explícitas.

**Salida:** `pharma_validator_api.block_editing` y `docs/BLOCK_EDITING_CONTRACT.md`.

**Aceptación:** una ocurrencia creada por un revisor no declara procedencia de origen; eliminar una importada exige comentario; reordenar debe cubrir exactamente las existentes; fusionar exige comentario y falla ante valores en conflicto, admitiendo solo complementarios; marcar no aplicable conserva los valores y es reversible con justificación.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-507 ni abre Fase 5. Evidencia: 22 pruebas, Ruff y mypy limpios. La interfaz de edición no existe todavía.

### DEV-508 — Medición de tiempo (`P1`)

**Objetivo:** calcular `segundos_empleados` por campo descontando la inactividad, para que la comparación del piloto de la sección 17 sea posible.

**Salida:** `pharma_validator_api.time_measurement` y `docs/TIME_MEASUREMENT_CONTRACT.md`.

**Aceptación:** cada tramo de foco cuenta hasta 60 segundos y el exceso se descarta e informa; el umbral exacto no se recorta; los solapamientos son error explícito; un campo sin foco cuenta cero y sigue siendo campo medido; la media de sesión no depende del orden de registro.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-508 ni abre Fase 5. Evidencia: 15 pruebas, Ruff y mypy limpios. La captura de foco en la interfaz no existe todavía.

### DEV-509 — Rendimiento y precarga (`P1`)

### DEV-510 — Tests de sesgo de automatización (`P0`)

**Objetivo:** convertir las reglas de pre-relleno de la especificación 9 en decisiones ejecutables y comprobables, independientes de la interfaz.

**Salida:** `pharma_validator_api.prefill_policy` y `docs/PREFILL_POLICY_CONTRACT.md`.

**Aceptación:** las cuatro políticas producen la presentación correcta; un valor pasado a un campo protegido se descarta en lugar de mostrarse; una pantalla completa se comprueba de una vez y detecta un plan manipulado; la confirmación en bloque exige `proponer_valor` y evidencia visible.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-510 ni abre Fase 5. Evidencia: 13 pruebas, Ruff y mypy limpios. La pantalla que consumirá estas decisiones (DEV-503/504/505) no existe todavía.

### DEV-512 — Consumo de `prefill_policy` en la pantalla (`P0`)

**Objetivo:** que la pantalla de revisión presente cada campo según su política (`proponer_valor`, `proponer_opciones`, `solo_evidencia`, `oculto`) consumiendo `pharma_validator_api.prefill_policy` en lugar de no precargar nada.

**Contexto:** la vertical demostrable del 3 de septiembre de 2026 no precarga ningún valor, lo cual es seguro por defecto pero no implementa la política. Requiere exponer la política por campo desde el catálogo importado, que hoy no llega a la API de registros.

**Aceptación:** ningún campo protegido aparece preseleccionado; `solo_evidencia` muestra el aviso de criterio farmacéutico; la confirmación en bloque solo se ofrece para `proponer_valor` con evidencia visible.

**Estado:** no iniciada. Depende de D-015 para los umbrales de degradación.

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
