# Backlog inicial

## UI-REG-001 — Registros compacto (10-09-2026)

Implementado según ADR-0012: navegación conjunta, un editor por campo,
filtros, fuente con contexto y avance explícito. Conservar evidencia de pruebas
en STATUS. Pendiente de observación farmacéutica del flujo con datos reales;
la extensión visual al resto del programa se realiza por módulo.

## Orden vigente — D-028 / ADR-0010

Completar desarrollo técnico de fases 4–7; después realizar todas las
comprobaciones farmacéuticas. GOLD y umbrales no bloquean implementación.
Integración actual: cola filtrable y asignable por lotes, guardado condicionado
a asignación vigente, campo activo, evidencia lateral y navegación completa por
teclado. DEV-502/503/504 están cerradas técnicamente.

## Actualización de camino crítico — 7 de septiembre de 2026

- **REAL-001 completada:** `#/fichas` exclusivamente REAL, detalle correcto,
  paginación/búsqueda server-side, estados asíncronos y rendimiento dentro de
  objetivo en caliente. Migración `4d7a6b2c1e90`; evidencia en
  `docs/REAL_MODE_VERIFICATION.md`.
- **DATA-309 completada como análisis:** auditoría exacta CN maestro ↔ CIMA con
  herramienta reproducible; no persiste asociaciones. Próximo paso: decisión
  de vigencia/cobertura antes de importar vínculos.
- **D-027 pendiente:** mapeo de `*_IDEXTERNO` a `external_identifier` por entidad
  y versión. No bloquea GOLD ni se implementa sin ADR.
- **GOLD-004 pendiente y bloqueante:** responsable funcional congela el alcance
  exacto de unidades/campos por ficha. Junto con GOLD-002, es requisito para que
  dos farmacéuticos empiecen sin huecos invisibles.
- **DEV-402 parcialmente completada:** sender HTTP OpenAI-compatible agnóstico
  implementado y probado offline. Falta D-014, despliegue/smoke real y manifiesto
  de ejecución; no falta ya código de transporte.
- **DEV-502 completada técnicamente (7-09-2026):** cola de revisión con seis
  estados, asignación, caducidad de 30 minutos, orden técnico y prevención de
  colisiones por bloqueo optimista (409 en conflicto). `review_queue` (puro),
  `review_queue_store`, API `/queue`, migración `a1b2c3d4e5f6` reversible.
  21 pruebas de dominio/persistencia y 8 de API. `tecnicamente_verificada`, no
  validada clínicamente.
- **Madurez y banderas (7-09-2026):** `maturity.py` separa implementada /
  técnicamente verificada / clínicamente validada / lista para producción, con
  banderas conservadoras por defecto y endpoint `/maturity`. Ver
  `docs/TECHNICAL_AHEAD_OF_GATE.md`.
- **Próximo issue tras acciones humanas:** cerrar DEV-402 contra el runtime
  aceptado y lanzar DEV-408 cuando GOLD esté conciliado.

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

**Objetivo:** hablar con un servidor local compatible con OpenAI-chat sin que el código conozca el modelo concreto.

**Salida:** `pharma_validator_api.inference_backend`.

**Aceptación:** parámetros reproducibles por defecto (`temperature=0`, semilla fija); salida guiada estricta por JSON Schema; los fallos se clasifican y sólo se reintenta lo transitorio; una respuesta servida por un modelo distinto del solicitado se rechaza; ninguna respuesta se repara.

**Estado:** parte agnóstica al modelo implementada el 4 de septiembre de 2026; 11 pruebas, Ruff y mypy limpios. **`BackendConfig` exige `model` explícito y falla sin él**, de modo que ningún camino de código elige modelo mientras D-014 esté pendiente.

**Actualización (7 de septiembre):** `pharma_validator_api.llm_extractor.LocalServerExtractor` implementa `ExtractorLLM` uniendo esquema guiado, transporte y verificación literal. `http_inference_sender.OpenAIChatSender` aporta ya el envío HTTP OpenAI-compatible sin elegir modelo, y el contrato mide la duración total incluidos reintentos. Falta fijar D-014, verificar un servidor real y capturar el manifiesto de runtime/hardware; no cierra DEV-402.

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

**Actualización 4-09-2026:** entradas de anotación materializadas sobre el corpus real (`scripts/materialize_gold_set.py`: 20 fichas, 552 secciones citables, 58 sin contenido); comprobador de completitud `gold_completeness` + `scripts/check_gold.py` (10 pruebas); orquestador `scripts/run_gold_pipeline.py`; runbook operativo `docs/GOLD_ANNOTATION_RUNBOOK.md`. **Cero fichas anotadas de 20.** GOLD-002 sigue siendo el único bloqueo de la anotación.

**Actualización técnica:** el núcleo puro `gold_annotations` y la CLI `scripts/generate_gold_annotations.py` implementan los criterios 2 a 8: evidencia por desplazamientos exactos sobre HTML literal, ocurrencias separadas, estados distinguibles, bloqueo de cierre por `pending`, doble anotación y desacuerdos abiertos, más las cinco salidas deterministas sin sobrescritura. Ocho pruebas específicas y 36 pruebas de pureza verifican el comportamiento. **GOLD-002 continúa pendiente** y bloquea la anotación real; por tanto DEV-407 no se cierra ni abre Fase 4.

### DEV-408 — Benchmark de dos modelos (`P0`)

**Objetivo:** medir el extractor sobre el conjunto oro y comparar al menos dos tamaños de modelo.

**Salida:** `pharma_validator_api.gold_evaluation`, `scripts/run_gold_pipeline.py`.

**Aceptación:** exactitud, precisión, recall, F1, cobertura, evidencia válida, alucinaciones, coincidencia normalizada, latencia y throughput, por campo y global; clasificación en correcta / parcial / incorrecta / no localizada / evidencia inválida / no parseable / alucinación; una unidad con desacuerdo humano sin conciliar no puntúa y las exclusiones se informan; toda métrica queda atribuida a un modelo.

**Estado:** motor implementado y probado el 4 de septiembre de 2026 con entradas sintéticas; 13 pruebas, más 5 de recorrido completo que verifican el encaje entre etapas (anotaciones → checker → conciliación → gold final → evaluación → métricas). **No se ha ejecutado ninguna evaluación real**: faltan el conjunto oro anotado (GOLD-002) y un modelo aceptado (D-014). No cierra DEV-408.

### DEV-409 — Política configurable por resultados (`P0`)

**Estado:** bloqueado por D-015. El mecanismo de degradación existe en `prefill_policy` y las políticas por restricción funcional (D-023) ya están cerradas y probadas. Los umbrales por resultados no pueden fijarse sin métricas: el método de cálculo queda definido en ADR-0009 (propuesto).

## EPIC E5 — Revisión farmacéutica

### DEV-501 — Selector de usuario (`P0`)

**Objetivo:** resolver quién firma una validación desde una lista configurable y rechazar cualquier guardado sin revisor seleccionado.

**Salida:** `pharma_validator_api.reviewer_identity`, ajuste `APP_REVIEWERS` y `docs/REVIEWER_IDENTITY_CONTRACT.md`.

**Aceptación:** lista construida desde configuración; revisor ausente y revisor desconocido son errores distintos; una lista vacía no firma nada; la garantía es `declarada` y está explícita en el tipo; la doble validación exige dos revisores distintos.

**Estado:** núcleo preparatorio verificado el 2 de septiembre de 2026; no cierra formalmente DEV-501 ni abre Fase 5. Evidencia: 15 pruebas, Ruff y mypy limpios.

La vertical añadió el selector de revisor y el endpoint correspondiente. La
elección se conserva en `localStorage` entre sesiones; DEV-501 queda cerrado
técnicamente. La identidad sigue siendo declarada, no autenticada.

### DEV-502 — Cola y asignación de lotes (`P0`)

**Estado: cerrada técnicamente (9-09-2026).** Dominio, persistencia y API de cola;
pantalla con filtros combinables por entidad, bloque, estado, conjunto y doble
validación; alta y asignación individual o por lote. El conjunto y la marca de
doble validación son datos explícitos, nunca inferencias clínicas. La asignación
por lote es atómica y versionada; un conflicto revierte el lote completo.
Migración `a7b8c9d0e1f2`. Contrato en `docs/REVIEW_QUEUE_CONTRACT.md`.

### DEV-503 — Pantalla de tres zonas (`P0`)

**Estado: cerrada técnicamente (8-09-2026).** `ReviewScreen` sobre `/records/*`
con contexto, campo de trabajo y evidencia del campo activo. `/fichas` es la
ruta canónica y opera sobre el corpus real. `ProvenanceList` unifica la
representación de la procedencia, que antes estaba duplicada. Verificado sobre
copia real: ficha de 57 campos, 2 bloques, procedencia completa.

### DEV-504 — Navegación completa por teclado (`P0`)

**Estado: cerrada técnicamente (8-09-2026).** Mapa declarado como dato en
`domain/shortcuts` y documentado en la propia pantalla: campo y ficha
anterior/siguiente, editar, guardar, cancelar, ir a evidencia y volver.
Comprobado que ningún atajo de una sola tecla actúa mientras se escribe, que no
se reservan combinaciones del navegador (Ctrl+T/W/L, F5), que un modificador de
más no dispara dos acciones y que Ctrl+Enter no guarda una decisión incompleta.
El mapa no contiene ninguna acción destructiva inmediata. 10 pruebas.

### DEV-505 — Guardado incremental (`P0`)

**Estado: cerrada técnicamente (8-09-2026).** `domain/drafts` conserva el
borrador no firmado en el navegador y lo recupera tras recargar, anunciándolo.
El autoguardado es **local a propósito**: enviarlo al backend convertiría un
texto a medio escribir en una decisión firmada. Cuatro estados de guardado
distinguibles. Un 409 conserva el borrador y no afirma que se guardó; el
borrador se retira sólo cuando la decisión llega firmada al historial.
La precarga y el objetivo de latencia se cubren en DEV-509. 11 pruebas.

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

**Estado: cerrada técnicamente (8-09-2026).** Al núcleo puro se le añaden
persistencia (`block_editing_store`), API (`block_api`), auditoría
(`block_edit_record`, append-only, con `before_state`) y editor en pantalla.
Migración `c3d4e5f6a7b8`, aditiva y reversible: upgrade → downgrade → upgrade
sobre copia del esquema real con 290 valores intactos en cada paso.
Comprobado que crear no fabrica procedencia, que eliminar una ocurrencia
importada exige motivo, que reordenar no puede dejar caer una ocurrencia, que
fusionar valores en conflicto se rechaza, que marcar «no aplica» conserva los
valores y es reversible, y que una operación rechazada no deja rastro a medias.
45 pruebas (22 del núcleo, 13 de persistencia, 10 de API).

### DEV-508 — Medición de tiempo (`P1`)

**Objetivo:** calcular `segundos_empleados` por campo descontando la inactividad, para que la comparación del piloto de la sección 17 sea posible.

**Salida:** `pharma_validator_api.time_measurement` y `docs/TIME_MEASUREMENT_CONTRACT.md`.

**Aceptación:** cada tramo de foco cuenta hasta 60 segundos y el exceso se descarta e informa; el umbral exacto no se recorta; los solapamientos son error explícito; un campo sin foco cuenta cero y sigue siendo campo medido; la media de sesión no depende del orden de registro.

**Estado: cerrada técnicamente (8-09-2026).** `timing_api` expone abrir sesión,
declarar tramos y cerrar; `FocusTracker` captura el foco en el navegador. El
cliente no puede declarar `is_synthetic`. El descuento de inactividad se aplica
sólo en `time_measurement`: 8 h de pestaña abandonada cuentan 60 s y declaran
el resto como descartado. 13 pruebas nuevas (8 de API, 5 de captura).

### DEV-509 — Rendimiento y precarga (`P1`)

**Estado: cerrada técnicamente (8-09-2026).** `api/recordCache` comparte la
petición en vuelo, caduca a los 30 s y **se invalida en cada escritura**:
servir la versión anterior tras guardar mostraría como pendiente un campo ya
validado, que es el único modo en que una caché puede mentir sobre el estado
clínico. Medido sobre copia del corpus real: listado 246 ms, ficha de 57
campos 90 ms. Una ficha ya precargada no cuesta petición nueva. El objetivo de
<100 ms se cumple sobre datos ya precargados; una petición de red contra el
corpus real no lo alcanza y no se afirma que lo haga. 7 pruebas.

**Refuerzo (10-09-2026).** El espacio integrado de Registros activa la precarga
de las dos filas siguientes. El detalle elimina las consultas repetidas por
campo y recupera valores, procedencias, estados e historial por lotes. En el
contenedor con la base real montada, la muestra inicial de ocho fichas bajó de
2,8–12,6 s a 2,1–2,3 s antes de aplicar la caché de navegación.

### DEV-510 — Tests de sesgo de automatización (`P0`)

**Objetivo:** convertir las reglas de pre-relleno de la especificación 9 en decisiones ejecutables y comprobables, independientes de la interfaz.

**Salida:** `pharma_validator_api.prefill_policy` y `docs/PREFILL_POLICY_CONTRACT.md`.

**Aceptación:** las cuatro políticas producen la presentación correcta; un valor pasado a un campo protegido se descarta en lugar de mostrarse; una pantalla completa se comprueba de una vez y detecta un plan manipulado; la confirmación en bloque exige `proponer_valor` y evidencia visible.

**Estado: cerrada técnicamente (9-09-2026).** La pantalla que
consume estas decisiones existe desde el 8 de septiembre de 2026 (DEV-512) y
sirve la política conservadora para todo campo. La doble revisión ciega está
integrada y las pruebas impiden preseleccionar campos protegidos.

### DEV-512 — Consumo de `prefill_policy` en la pantalla (`P0`)

**Estado: cerrada técnicamente (8-09-2026).** `/records/{id}` sirve la política
de cada campo y la pantalla la obedece. Bajo la política vigente ningún campo
llega con `proposed_value`: precargar es imposible por construcción.
`field_prefill_policy` devuelve `solo_evidencia` y deja declarado el punto de
extensión. **Decisión farmacéutica pendiente (D-015):** qué campos pasan a
`proponer_valor`/`proponer_opciones` y con qué umbral. 7 pruebas.

### DEV-511 — Ejecución del conjunto de medida (`P0`)

**Estado: instrumentación cerrada; ejecución humana pendiente (9-09-2026).**
`pilot_reporting` y `scripts/build_pilot_report.py` consolidan las cuatro
métricas mínimas de la especificación, rechazan observaciones sintéticas y no
presentan como resultado un conjunto incompleto. La ejecución real de dos
semanas sobre 50 fichas requiere farmacéuticos y no se simula. Contrato en
`docs/PILOT_MEASUREMENT_REPORT_CONTRACT.md`.

## EPIC E6 — Exportación, riesgo y auditoría

### DEV-601 — Cerrar contrato de exportación (`P0`)

**Estado: infraestructura cerrada técnicamente (8-09-2026); contrato pendiente
de D-011.** `export_service` lee el modelo canónico y produce filas mediante una
capa de transformación explícita. El perfil es un dato configurable, no una
constante: cuando exista un ejemplo aceptado se añadirá un perfil, no se
reescribirá el motor. Ningún perfil se declara `provider_accepted`.
La pantalla permite iniciar una ejecución técnica declarando nombre, formato,
columnas y alcance, siempre con un revisor identificado; mantiene visible que
el perfil no equivale al contrato pendiente del proveedor.

### DEV-602 — Exportadores CSV/TXT/XLSX (`P0`)

**Estado: cerrada técnicamente (8-09-2026).** Los tres formatos derivan del
mismo modelo normalizado. Comprobado leyendo los ficheros generados: CSV con su
dialecto declarado, escapado del delimitador, encoding respetado y XLSX abierto
como zip con sus partes (`[Content_Types].xml`, `xl/workbook.xml`, hoja).

### DEV-603 — Validador de tipos y longitudes (`P0`)

**Estado: cerrada técnicamente (8-09-2026).** `validate_row` comprueba sin
modificar: obligatoriedad, longitud declarada y estados serializables. Nada se
trunca ni se rellena; un valor fuera de contrato excluye la fila y lo declara.

### DEV-604 — Informe de exportación (`P1`)

**Estado: cerrada técnicamente (8-09-2026).** `export_exclusion` guarda ficha,
campo, severidad (`bloqueante` / `advertencia` / `no_aplicable`), regla, motivo
y estado observado. Servido en `/exports/{id}/exclusions` y visible en la
pantalla de Exportaciones junto al recuento de entregadas.

### DEV-605 — Exportación reproducible (`P1`)

**Estado: cerrada técnicamente (8-09-2026).** La fecha vive en `ExportRun` y en
el manifiesto, nunca en el contenido, y el orden de filas y ocurrencias es
explícito. Dos ejecuciones de los mismos datos comparten bytes y hash aunque
difieran en hora. La versión del perfil se deriva de su configuración para que
cambiar una columna no deje dos exports incomparables con la misma versión.

### DEV-606 — Reglas ATC por prefijo (`P0`)

**Estado: mecanismo cerrado técnicamente (8-09-2026); lista pendiente de
D-017.** Coincidencia por prefijo según la especificación 11.1, con reglas
configurables sin desplegar código. Semilla `L04`, la única acordada. Un
registro sin ATC queda **indeterminado**, no de bajo riesgo. Contrastado en
sólo lectura sobre el corpus real: 6.342 códigos → 255 exigen doble validación,
6.057 no y 30 indeterminados.

### DEV-607 — Segunda validación ciega (`P0`)

**Estado: cerrada técnicamente (8-09-2026).** La ceguera se garantiza en el
dato: `blind_view` no consulta la primera decisión. `first_decision_sequence`
ancla la comparación a la lectura revisada. `record_independent_reading` evita
que la regla de transición filtre la primera decisión por la puerta de atrás.
El primer firmante no puede realizar la segunda.

### DEV-608 — Conciliación (`P0`)

**Estado: cerrada técnicamente (8-09-2026).** La decisión conciliada se añade al
historial del campo; las dos lecturas enfrentadas permanecen íntegras. Exige
justificación, no puede aplicarse sobre un acuerdo y dos conciliaciones
concurrentes no cierran la misma discrepancia.

### DEV-609 — Auditoría append-only (`P0`)

**Estado: cerrada técnicamente (8-09-2026).** `audit_event` con actor, acción,
entidad, estado anterior y posterior, motivo, contexto y fecha. UPDATE y DELETE
rechazados. Un rollback no deja rastro de lo que no ocurrió.
`/audit/records/{id}` reconstruye el historial uniendo decisiones, bloques y
diario en orden cronológico.

### DEV-610 — Prueba de carga con proveedor (`P0`)

**Estado: PENDIENTE EXTERNO.** No se ha realizado y no puede simularse. Listo
para ejecutarla: generador, validador de contrato, manifiesto verificable,
perfiles configurables, artefactos en disco e informe de exclusiones. Falta el
ejemplo aceptado por el proveedor (D-011) y la ejecución en su entorno.

## EPIC E7 — Mantenimiento

### DEV-701 — Consulta de cambios CIMA (`P0`)

**Estado: núcleo técnico cerrado (9-09-2026).** `cima_changes` consulta y
valida `registroCambios`, conserva el Epoch literal, clasifica altas, bajas y
modificaciones, señala códigos de área nuevos sin descartarlos y produce una
representación determinista. La operación evita deliberadamente la caché
inmutable porque el registro del mismo día puede crecer. Contrato en
`docs/CIMA_CHANGE_QUERY_CONTRACT.md`. La descarga/persistencia de nuevas
versiones y la apertura selectiva de revisión continúan en DEV-702.

### DEV-702 — Revisión pendiente selectiva (`P0`)

**Estado: núcleo técnico cerrado (9-09-2026).** `maintenance_refresh` conecta
los cambios `ft` de DEV-701 con descarga fresca por apartado, versión
content-addressed, diff y reapertura selectiva basada en procedencia. Las
decisiones anteriores no se modifican: se añade un evento
`revision_pendiente` firmado por el actor técnico y referenciado a ambas
versiones y al diff. Capturas idénticas no duplican nada y toda la escritura es
transaccional. Contrato en `docs/CIMA_MAINTENANCE_REFRESH_CONTRACT.md`.

### DEV-703 — Panel de novedades y diff (`P1`)

**Estado: cerrado técnicamente (9-09-2026).** Migración aditiva
`e5f6a7b8c9d0`, registro inmutable/idempotente de novedades, API con lista
ligera y detalle con diff, y pantalla `Novedades CIMA`. Los cambios no `ft`
quedan visibles sin fabricar una versión; los `ft` enlazan versiones, diff y
reaperturas de DEV-702. Contrato en `docs/CIMA_NOVELTY_PANEL_CONTRACT.md`.

### DEV-704 — Operación programada y alertas (`P1`)

**Estado: cerrado técnicamente (9-09-2026).** `maintenance_run` conserva cada
intento; el cursor deriva del último día completado y recupera días pendientes
en orden. Un fallo queda visible, no adelanta el cursor y el siguiente intento
repite la fecha. `scripts/run_cima_maintenance.py` ofrece una pasada finita para
el scheduler de infraestructura; `/maintenance/runs` y `Novedades CIMA`
muestran el estado operativo. Contrato en
`docs/CIMA_MAINTENANCE_OPERATION_CONTRACT.md`.

### DEV-705 — Chat contextual citado (`P2`)

**Estado: cerrado técnicamente (9-09-2026).** Panel colapsable en la revisión y
endpoint de consulta documental estrictamente de sólo lectura. La recuperación
determinista usa la ficha CIMA tipo 1 más reciente enlazada al registro; una
respuesta sólo se considera contestada si aporta versión, apartado y fragmento
literal. No genera recomendaciones ni escribe campos. Contrato en
`docs/CONTEXTUAL_CHAT_CONTRACT.md`.

### UX-001 — Sistema visual unificado (`P1`)

**Estado: cerrado técnicamente (9-09-2026).** Armazón, navegación, dashboard y componentes compartidos renovados sobre las rutas existentes. Segunda revisión visual completada con base neutra, acento rosa–morado contenido, menor radio, iconografía lineal y movimiento accesible. No cambia contratos de datos, políticas de pre-relleno ni reglas de validación. Verificado con ESLint, build de producción y 117 pruebas frontend.

### UX-002 — Agrupar documentos por origen en Fuentes (`P2`)

**Estado: cerrado técnicamente (10-09-2026).** La lista plana se resume por tipo de fuente con agregados y permite desplegar todos los documentos originales. La agrupación es exclusivamente visual: conserva el detalle individual y no modifica versiones, identidades ni contratos de API. Verificada con 2 pruebas específicas, ESLint y build de producción.

## Orden recomendado de las primeras issues

`DEV-001 (completada) → DEV-002A (completada) → DEV-002 → DEV-003 → DEV-004 → DEV-005 → DEV-006 → DEV-007 → DEV-008A (completada) → DEV-008 → DEV-009 → DEV-010 (completada) → DEV-011`

Solo después: `DEV-101` en adelante.


## UI — Novedades CIMA (10-09-2026)

Rediseño del panel de novedades (§13): resumen de eventos cargados por tipo, etiquetas de cambio y reapertura, historial en panel y detalle documental contextual. Conserva fuentes, eventos y consulta bajo demanda. Prueba de pantalla cubre resumen y apertura del diff.
