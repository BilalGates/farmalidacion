# Estado del proyecto

## Estado global

`FASE 0A CERRADA — FASE 0B CERRADA CON DEPENDENCIAS EXTERNAS — FASE 1 CERRADA — FASE 2 CERRADA — FASE 3 CERRADA`

## Fase actual

Fase 3 cerrada. Gate 3 es PASS según docs/PHASE_3_GATE_REVIEW.md. Fase 4 no se ha iniciado. D-013 está cerrada con un servidor interno de al menos 24 GB de VRAM; el contrato del conjunto oro fija semilla 407 y ausencia de estratificación ATC inicial, pero GOLD-002, la herramienta y la anotación real siguen pendientes.

## Fase 0A — Cerrada

- Instrucciones, agentes y skill del proyecto disponibles y aplicados.
- Especificación, inventario, plan, decisiones, ADRs, backlog y trazabilidad disponibles.
- Ocho referencias verificadas por hash con código 0.
- No existe código de producto ni un modelo definitivo congelado.

## DEV-002 — Completado

- Perfilador agregado OOXML en streaming implementado en `scripts/profile_reference_files.py`.
- Siete Excel y todas sus hojas procesados sin modificar originales.
- Salidas limitadas a agregados por libro, hoja y columna; no se vuelcan celdas ni relaciones fila a fila.
- 730 columnas perfiladas.
- Dos ejecuciones completas: 115,605 s y 321,479 s.
- Hash reproducible idéntico: `1999097257b99fe5cc52ab903da873085dd9abe5deb7b0a1d327670f04875976`.
- Incidencias agregadas: 34.314 duplicados de fila observados o estimados, distribuidos en cinco hojas, y una cabecera duplicada en una hoja.
- Cardinalidad exacta hasta 100.000 valores distintos; por encima se informa estimación `linear_counting` y no se propone clave candidata.
- Relaciones detalladas, cardinalidades entre bloques y huérfanos diferidos a DEV-004/DEV-006.
- Tests unitarios: 5/5 OK.
- Referencias verificadas de nuevo: 8/8 OK, código 0.

## Otros trabajos documentales de Fase 0B

- Contrato semántico del round-trip de omeprazol definido, todavía no ejecutado.
- Bloques repetibles exigidos como ocurrencias explícitas; concatenación prohibida.
- ADR-0004/D-010 está aceptado para el modelo interno; la serialización externa continúa pendiente bajo D-011.
- ADR-0001 aceptado tras DEV-008 y aprobación humana.

## DEV-003 — Completado documentalmente

- Definidos `documento_fuente`, `documento_fuente_version`, `fragmento_fuente`, `registro_destino`, `instancia_bloque`, `valor_campo` y sus vínculos conceptuales.
- Diagrama y tabla de entidades, bloques, cardinalidades conservadoras y claves candidatas documentados en `docs/CANONICAL_CONCEPTUAL_MODEL.md`.
- Las 22 hojas de omeprazol tienen representación sin concatenar, deduplicar ni descartar ocurrencias.
- La demostración es de capacidad conceptual; la importación y comparación real siguen pendientes en DEV-007/DEV-008.
- D-004 y D-006 no se cerraron dentro de DEV-003; fueron aceptadas posteriormente mediante ADR-0005/0006.
- ADR-0001 está aceptado como modelo conceptual, no como esquema físico definitivo.

## DEV-004 — Completado como evidencia

- Analizador agregado dirigido implementado sin serialización de relaciones fila a fila.
- 35 hipótesis de clave y 12 relaciones evaluadas sobre cuatro maestros.
- 6 unicidades observadas; ninguna se declara clave natural aceptada.
- Cardinalidades observadas documentadas, incluidos bloques 0..N y hojas vacías 0..0.
- Reproducidas 275 filas huérfanas de excipientes, equivalentes a 184 claves paternas distintas.
- Hash de evidencia: `c685c293172fd3702db881eff6823409a6f9b8447772ab283ef159bba2f23a6c`.
- La evidencia no convierte unicidad en clave natural; D-004/ADR-0005 fueron aceptados posteriormente con identidad canónica propia.

## DEV-005 — Completado y aceptado

- Verificados sin huérfanos los enlaces composición→principio activo y especialidad→medicamento.
- Cardinalidades observadas: principio activo→composiciones 0..83 y medicamento→especialidades 1..643.
- Definidos por separado `nregistro`, CN, especialidad/presentación, medicamento y principio activo.
- Propuesto un expediente contextual de revisión con decisiones atribuidas al nivel destino correspondiente.
- Los maestros no contienen `nregistro`; la cardinalidad `nregistro`↔CN no se ha inferido y requiere evidencia CIMA.
- ADR-0006 aceptado por decisión humana; D-001, D-002 y D-006 cerradas en su alcance conceptual.
- La cardinalidad factual `nregistro`↔CN sigue pendiente de verificación en Fase 2 y no se ha supuesto.
- No se ha iniciado integración CIMA ni modelo físico.

## DEV-006 — Completado y aceptado

- Matriz contractual de fuentes definida para los 353 campos del catálogo.
- Cobertura: 204 no procedentes de FT, 53 directos, 79 parciales y 17 interpretables.
- Maestro actual conservado como línea base, nunca como verdad autoritativa automática.
- Toda prioridad no aprobada queda `pending_human_validation` y todo conflicto conserva las afirmaciones y procedencias.
- CIMA estructurado permanece fuente candidata condicionada a mapeo verificado; no se ha integrado ni consultado.
- ADR-0007 aceptado y D-008 cerrada; PROVIDER-001/002 siguen abiertos sin bloquear Fase 1.

## DEV-007 — Completado como spike reversible

- Importador temporal seguro implementado en `scripts/import_omeprazole_fixture.py`; no define esquema físico ni infiere identidades de negocio.
- Las 22/22 hojas se representan con orden, filas materiales, valores literales, tipos observados, coordenadas, fórmulas y procedencia por fragmento.
- Se conservaron 616 ocurrencias técnicas provisionales y 2.674 valores materiales; no se concatenaron, deduplicaron ni descartaron ocurrencias.
- Dos corridas independientes produjeron instantáneas idénticas y el hash canónico `5e8564dcd726380aec23f031f6060e4450d2c0fa09f559589e9c6d32caebdb5f`.
- Los recuentos por hoja coinciden con el perfil agregado de DEV-002; suite completa 12/12 OK.
- Evidencia y límites en `docs/OMEPRAZOLE_CANONICAL_IMPORT_EVIDENCE.md`.
- Esta evidencia permitió ejecutar DEV-008; ADR-0001 fue aceptado después del round-trip.

## DEV-008 — Completado como round-trip reversible

- Reconstrucción OOXML temporal implementada en `scripts/roundtrip_omeprazole_fixture.py`; usa el original verificado como plantilla estructural inmutable y restaura los contenidos materiales desde DEV-007.
- Comparadas 22/22 hojas y 2.674/2.674 valores, tipos, fórmulas, estilos de celda, orden, visibilidad y estructura auxiliar, sin normalizaciones.
- Cero diferencias, defectos, pendientes, truncamientos, descartes, concatenaciones o partes auxiliares alteradas.
- Dos corridas de 8,165 s y 7,373 s produjeron XLSX e informes idénticos con hash reproducible `7d474de536f4e168636c286aabd4ab3339715dde04c3164900c58c5204926adf`.
- Suite completa 14/14 OK; la prueba de mutación confirma que un valor alterado se clasifica como defecto.
- Evidencia en `docs/OMEPRAZOLE_ROUNDTRIP_EVIDENCE.md`. No es el exportador final; ADR-0001 quedó aceptado conceptualmente.

## DEV-009 — Completado como evidencia de integridad

- Catálogo: cabecera reproducible y 353/353 filas activas.
- Reproducidos 275 huérfanos/184 claves, seis incidencias de duplicado, cuatro excesos y 24 valores exactamente al límite, sin reparar datos.
- Dos conflictos de tipo: `Composición / DESCRIPCION` (`CHAR(50)`/`CHAR(100)`) y `Links / DESCRIPCION` (`CHAR(100)`/`CHAR(255)`).
- Dos corridas idénticas: `987129be4c8d7b62517c0962e19279e01b00299c7c51490e179137b3040579e7`; suite 16/16 OK.
- Evidencia en `docs/INTEGRITY_INCIDENT_EVIDENCE.md`; no se aceptan claves ni reparaciones.

## Puerta 0B — PASS WITH EXTERNAL DEPENDENCIES

Revisión formal en `docs/PHASE_0B_GATE_REVIEW.md`. Excepción humana aprobada para PROVIDER-001/002; Fase 1 autorizada.

DEV-011 queda cerrado bajo la excepción: modelo interno aceptado y serialización externa trasladada a PROVIDER-002.

DEV-101 quedó autorizado por esta puerta y se completó sin avanzar automáticamente a DEV-102.

## DEV-101 — Completado

- Creados los límites `backend/`, `frontend/`, `infra/` y `data/examples/` con responsabilidades explícitas.
- Añadida configuración local de ejemplo sin secretos y documentada una única superficie futura de comandos.
- No se instalaron dependencias ni se implementaron API, interfaz, modelo físico, migraciones, contenedores, CIMA, LLM o exportación.
- Un test de arquitectura protege la presencia del scaffold y la ausencia de marcadores de secretos en `.env.example`.

## DEV-102 — Completado

- Backend FastAPI empaquetado de forma independiente con configuración tipada por entorno.
- Logging JSON y respuestas de error en español sin exposición de detalles internos.
- `GET /health` comprueba el proceso; no simula conectividad de base de datos.
- Pytest y Ruff configurados para el backend.
- Sin modelos canónicos físicos, migraciones, endpoints de dominio ni acceso a datos.

## DEV-103 — Completado

- Frontend React/TypeScript/Vite con shell técnico accesible y textos en español.
- Configuración de URL de API por entorno, todavía sin llamadas de red.
- Vitest y Testing Library verificados sobre happy-dom; ESLint y build configurados.
- El shell explicita que no contiene datos de pacientes, propuestas clínicas ni exportación.
- Sin pantalla farmacéutica definitiva, persistencia, CIMA o LLM.

## DEV-104 — Completado

- SQLAlchemy 2 y Alembic configurados sobre SQLite con claves foráneas activas.
- Migración inicial reversible para documentos/versiones, fragmentos, registros destino, identificadores externos, vínculos, bloques, valores y procedencia.
- PK canónicas internas y única restricción externa aprobada por sistema, identificador y versión.
- Dos ocurrencias idénticas se conservan como filas distintas; no se infieren claves farmacéuticas ni cardinalidades máximas.
- Upgrade y downgrade verificados sobre bases temporales; sin datos reales importados.

## DEV-105 — Completado

- Imágenes separadas para backend Python no-root y frontend estático nginx.
- Compose aplica Alembic y persiste SQLite en un volumen nombrado, sin incluir originales ni secretos.
- Backend y frontend verificados saludables en dos ciclos de arranque; revisión Alembic `9b01a03d5247` estable.
- Puertos locales: backend 8000 y frontend 5173.
- El volumen de prueba contiene solo esquema; fixture canónico de demostración pendiente de DEV-107.

## DEV-106 — Completado

- Workflow de GitHub Actions creado para `push` a `main` y pull requests, con Python 3.12, Node 24 y timeout de 20 minutos.
- `python scripts/verify_project.py` unifica pytest, Ruff, mypy estricto, Vitest, ESLint, build Vite, validación de Compose, hashes de referencias y round-trip Alembic sobre SQLite temporal.
- Verificación local completa: 26/26 tests Python, 1/1 test frontend, Ruff, mypy sobre 7 módulos, ESLint, build, Compose, 8/8 referencias y Alembic upgrade/downgrade, todo con código 0.
- CI omite explícitamente solo los hashes de originales no versionados mediante `--skip-references`; no inventa ni descarga referencias.
- No se añadieron endpoints, datos de producto, integraciones ni cambios de esquema.

## DEV-107 — Completado

- Fixture sintético offline de omeprazol con una versión documental, dos fragmentos y dos ocurrencias explícitas de composición.
- Las dos ocurrencias conservan IDs, ordinales y procedencias distintas aunque su valor literal sea idéntico; no se concatenan ni deduplican.
- La carga configurable es idempotente y rechaza colisiones parciales o distintas sin sobrescribir.
- `GET /records/{record_id}` devuelve identificadores externos versionados, bloques, valores y procedencia; un ID inexistente responde 404 en español.
- Compose verificó el registro antes y después de reiniciar el backend: dos bloques, ordinales 1/2 y localizadores `composition/1` y `composition/2`.

## Gate 1 — PASS

Revisión formal en `docs/PHASE_1_GATE_REVIEW.md`. El scaffold ejecutable,
migraciones reversibles, fixture API, gate de calidad y arranque con datos
locales quedan demostrados. No se inicia automáticamente la Fase 2.

## DEV-201 — Completado documentalmente

- Verificada la documentación oficial CIMA REST API v1.23 y su publicación en el portal de datos abiertos de AEMPS.
- Documentados base URL, endpoints mínimos, parámetros exactos, paginación, modelos relevantes, negociación de contenido y registro de cambios.
- Separados contrato oficial, observaciones vivas y políticas internas; el límite de 5 peticiones/s no se atribuye a AEMPS.
- Dos fallos consecutivos impidieron validar el formato vivo de `docSegmentado/contenido`; el punto exacto y la prueba pendiente quedan registrados para DEV-202.
- No se implementó cliente, persistencia, descarga de corpus ni cambios de esquema.

## DEV-202 — Completado

- Cliente CIMA de solo lectura con base HTTPS, timeout, límite de ritmo y reintentos exponenciales configurables.
- Reintentos limitados a fallos de transporte y HTTP 429/500/502/503/504; errores y esperas superiores al máximo fallan de forma visible.
- Caché local inmutable por URL y `Accept`, con manifiesto, cuerpo original byte a byte y verificación SHA-256 antes de cada reutilización.
- Las respuestas no exitosas no se cachean; una entrada incompleta o alterada no se repara ni sobrescribe silenciosamente.
- Métodos mínimos para medicamento, presentaciones, secciones, contenido segmentado y registro de cambios, preservando parámetros `nregistro` repetidos.
- Siete pruebas HTTP completamente offline cubren éxito, contenido no decodificable, caché, corrupción, timeout, 429, 404, espera insegura, parámetros y alcance de URL.
- No se hicieron nuevas solicitudes vivas, no se descargó corpus y no se persistieron datos CIMA en el modelo canónico.
- El comportamiento vivo de `docSegmentado/contenido`, `Retry-After` con fecha HTTP y las formas de payload se verificarán en el muestreo controlado; no se han supuesto.

## DEV-203 — Completado como capacidad reproducible

- Muestreo aleatorio y estratificado explícito, con semilla, tamaño y versión de algoritmo.
- Solo son elegibles medicamentos con `estado.aut` presente y `comerc = true`.
- El inventario paginado debe ser completo y sin páginas ni `nregistro` repetidos; las inconsistencias detienen la ejecución.
- El modo estratificado usa reparto proporcional por restos mayores y falla ante primer nivel ATC ausente o ambiguo.
- Ejecuciones e ítems se persisten de forma idempotente con hashes de inventario y respuesta fuente mediante una migración reversible.
- Una prueba sintética reproduce exactamente la misma lista de 500 documentos con la misma semilla; ambos modos se verifican offline.
- D-016 permanece abierta: no se ha elegido el modo del piloto ni descargado el corpus real. DEV-204 debe producir el informe de composición antes de esa decisión.
- Contrato y límites en `docs/CIMA_SAMPLING_CONTRACT.md`; no se inició DEV-204.

## DEV-204 — Completado como capacidad reproducible

- Informe automático por primer nivel ATC, forma farmacéutica y vía desde respuestas originales de medicamento ya cacheadas.
- Política multilabel explícita: documentos distintos y ocurrencias se cuentan por separado; no se concatenan ni deduplican listas.
- Ausencias clasificadas como diagnóstico interno `__MISSING__`, sin convertirlas en `no_consta` o `no_aplica`.
- ATC incompatible, respuesta faltante, duplicada o fuera de muestra detienen la generación sin normalización implícita.
- Salidas JSON, CSV y Markdown reproducibles e inmutables, ligadas a la ejecución de muestra y hashes de cada respuesta.
- Al cerrar DEV-204 no se había descargado corpus real; D-016 y Gate 2 seguían abiertos.
- Contrato en `docs/CIMA_COMPOSITION_REPORT.md`; no se inició DEV-205.

## DEV-205 — Completado como capacidad reversible

- Persistencia content-addressed de paquetes CIMA con documentos, versiones y artefactos separados.
- Cuerpo original binario, URL, estado, tipo, cabeceras, fecha literal, localizador, rol, ordinal y hashes conservados.
- Una repetición idéntica es idempotente; cambiar una sección crea otra versión sin sobrescribir la anterior.
- Reconstrucción byte a byte con verificación SHA-256 y soporte de contenido no decodificable.
- Mutaciones y borrados históricos rechazados desde el ORM; corrupción de cuerpo detectable al leer.
- Migración reversible `e3c83b4ed201`; no se descargaron documentos ni se modificaron fuentes.
- Al cerrar DEV-205, D-020 permanecía propuesta: `source_version` no se infería y faltaba evidencia CIMA real.
- Contrato en `docs/CIMA_DOCUMENT_VERSIONING.md`; DEV-206 aún no se había iniciado y Gate 2 seguía abierto.

## DEV-206 — Completado como capacidad reproducible

- Comparación dirigida entre dos versiones explícitas del mismo documento, sin inferir vigencia.
- Artefactos emparejados solo por rol y ordinal; añadidos, eliminados, modificados e idénticos quedan separados.
- Diff unificado completo para texto estrictamente decodificable; binarios o codificaciones incompatibles permanecen como hashes sin conversión.
- Cambios de metadatos visibles aunque el cuerpo sea idéntico y hashes verificados antes de comparar.
- Salidas JSON y Markdown reproducibles e inmutables; invertir anterior/nueva produce otro identificador.
- Sin descargas, cambios de validación, tareas `revision_pendiente`, consulta programada ni migraciones.
- D-020 y Gate 2 seguían abiertos al cerrar DEV-206; contrato en `docs/CIMA_VERSION_DIFF.md`.

## DEV-207 — Completado como capacidad verificable

- Manifiesto versionado con dos versiones sintéticas, cuatro cuerpos y SHA-256 explícitos.
- Verificación estricta de rutas, ocurrencias, ficheros declarados e integridad antes de cargar.
- Carga idempotente mediante DEV-205, reconstrucción exacta y diff de DEV-206 sin cliente HTTP.
- La prueba bloquea la creación de sockets y completa todo el recorrido usando solo disco y SQLite.
- El fixture está marcado como sintético y sus URLs `example.test` no se presentan como evidencia CIMA.
- Al cerrar DEV-207 no se habían descargado las 500 fichas; D-016, D-020 y Gate 2 seguían abiertos.
- Contrato en `docs/CIMA_OFFLINE_CORPUS.md`; no se inicia automáticamente otro issue.

## DEV-208 — Corpus real capturado; D-016 cerrada

- La API oficial respondió 200 y declaró 16.093 candidatos en páginas de 200 (81 páginas).
- Se autorizó comparar muestras aleatoria y estratificada con semilla 203 sin elegir D-016.
- El renombrado de directorios falló dos veces; tras autorización humana, una entrada ZIP atómica resolvió la caché Windows conservando compatibilidad de lectura.
- Se capturaron 81/81 páginas, 16.093 candidatos y 19.353.056 bytes con instantánea `72e9b05fd60a524fa9115c09fee9f29e98779a8c5c95565fe6d0bee4395c27cb`.
- La muestra aleatoria candidata de 500 (semilla 203) tiene SHA-256 `ebeb1f8c3823c5cd206bf3044f9f9adef194ed93d23048806268309b9fee8929`.
- Las 16.093 filas del inventario carecen de ATC; la muestra estratificada no puede calcularse con esa fuente.
- Se aceptó la muestra aleatoria con semilla 203; no se infirió exclusión ni estrato ni se lanzaron 16.093 consultas adicionales. D-016 queda cerrada.
- Se descargaron 500 metadatos y 500 fichas completas: 1.000 artefactos, 115.583.103 bytes y manifiesto `34d2216d09150bb07615fada4adc4ea45f7a35cbb7b96c011fa689d6d6759fb3`.
- El informe real contiene 109 filas y tiene ID `bb80992258d07a5e49f1beef46e983f3f56a57e7d48ad20d5aef19e3bffa5fe7`.
- Con sockets bloqueados, una SQLite temporal creó 500 versiones y la segunda carga creó 0; código 0.
- Evidencia, caché, corpus e informes permanecen en `data/local/`, fuera de Git.
- D-020 fue aceptada el 31 de agosto de 2026: versiones content-addressed e inmutables, `source_version` literal/opcional y nunca inferida.
- Gate 2 es PASS según `docs/PHASE_2_GATE_REVIEW.md`; Fase 3 quedó autorizada.

## DEV-301 — Completado

- Infraestructura común para lotes, diagnósticos y filas en cuarentena mediante una migración Alembic reversible.
- La identidad idempotente conserva sistema y localizador de fuente, `source_version` literal opcional, SHA-256 exacto e identidad/versión del importador.
- Reejecutar la misma combinación devuelve el lote existente; cambiar bytes, versión literal o versión del importador produce otro lote.
- Los diagnósticos y filas en cuarentena tienen claves reproducibles por lote; el payload literal y su SHA-256 se conservan sin normalizar, corregir ni deduplicar datos clínicos.
- Los lotes fallidos conservan sus diagnósticos. No se ha importado ningún maestro ni resuelto ningún huérfano.
- Contrato en `docs/IMPORT_BATCH_INFRASTRUCTURE.md`; DEV-302 no iniciado.

## DEV-302 — Completado

- Importador OOXML seguro para `Catalogo_campos_clinicos_medicamentos.xlsx`, ligado a la infraestructura de lotes de DEV-301.
- Cabecera localizada por la única fila que contiene `Entidad`, `Campo` y `Tipo`; 353/353 definiciones activas importadas en secuencia 1..353.
- Cada definición conserva hoja, fila física, valores y tipos OOXML literales, fórmula si existe, payload reproducible, tipo declarado y tipo efectivo.
- Se conservaron cinco identidades `(bloque, campo)` repetidas y dos conflictos de tipo; no se fusionaron ni declararon erróneos por duplicación.
- D-021 aplica `CHAR(100)` a `EX_DESCRIPCION` y `ME_DESCRIPCION`; D-026 aplica `CHAR(100)` a Composición/DESCRIPCION y `CHAR(255)` a Links/DESCRIPCION. Los tipos originales permanecen intactos y estos límites no son contrato del proveedor.
- Dos importaciones del mismo fichero producen un lote y 353 definiciones; el hash original sigue `a10160ebe5c7fe0b5d2a35a12d4597c982bacdafe04cb0f8d98c437183d19eac`.
- Contrato en `docs/CATALOG_IMPORT_CONTRACT.md`; DEV-303 no iniciado.

## DEV-303 — Completado

- Importador canónico e idempotente de `PrincipioActivoCargaMaster-22062026.xlsx`, integrado con los lotes de DEV-301.
- Las cinco hojas quedan registradas con orden, cabecera literal, filas y valores materiales; `General` aporta 7.189 filas y 35.945 valores.
- Cada fila general crea un registro destino de principio activo y una ocurrencia explícita; cada valor conserva literal, tipo OOXML, fragmento fila, versión documental y procedencia `master_baseline`.
- `Frecuencia`, `Via`, `ConsejosAdministracion` y `DatosAnaliticos` contienen solo cabecera en esta versión: cuatro diagnósticos `info`, sin inferir cardinalidad de dominio 0.
- No se usa `IDEXTERNO` como identidad canónica ni se fusionan filas por su valor; queda disponible únicamente como observación fuente para conciliación posterior.
- Dos ejecuciones producen un lote, 7.189 registros/ocurrencias y 35.945 valores; cero cuarentenas. El hash original permanece `89e6806b4cba7d6724533bfdc29ea834056223872385f08c080b72b965448e6c`.
- Contrato en `docs/ACTIVE_INGREDIENT_IMPORT_CONTRACT.md`; DEV-304 no iniciado.

## DEV-304 — Completado

- Importador canónico por lotes de `Medicamento-cargaMaster25062026.xlsx`, integrado con DEV-301 y con los principios activos importados por DEV-303.
- Siete hojas registradas; 58.256 ocurrencias y 509.496 valores conservan literal, tipo OOXML, hoja, fila, versión documental y procedencia `master_baseline`.
- `Composicion`, `Indicacion`, `Via` y `Links` son bloques 1:N explícitos. Los duplicados observados no se fusionan; las dos columnas `DESCRIPCION` de `Links` permanecen separadas por columna dentro del payload fuente.
- 4.211 filas de composición enlazan por coincidencia literal y única con principio activo; no se concilia por nombre ni semejanza.
- `Frecuencia` y `Prescripcion` contienen solo cabecera: dos diagnósticos informativos, sin inferir cardinalidad de dominio 0.
- Dos ejecuciones producen un lote y los mismos recuentos; cero cuarentenas. Prueba real completa: 208,47 s incluyendo la precarga DEV-303.
- Hash original intacto: `4b87aeac96ea220126c090d755fa5bfbaabe7aec304cfccb2e15537bd96cbf1b`.
- Contrato en `docs/MEDICATION_IMPORT_CONTRACT.md`; DEV-305 no iniciado.

## DEV-305 — Completado

- Importador canónico por lotes de `Especialidades-CargaMaster190626.xlsx`, integrado con DEV-301 y los medicamentos importados por DEV-304.
- Dos hojas registradas; 48.195 ocurrencias válidas y 1.623.810 valores conservan literal, tipo OOXML, hoja, fila, versión documental y procedencia `master_baseline`.
- Las 29.850 especialidades enlazan a medicamento por `ME_IDEXTERNO` literal y único; no se concilia por nombre o semejanza.
- `Excipientes` conserva 18.345 ocurrencias repetibles. Sus 275 filas sin padre, correspondientes a 184 `BN_IDEXTERNO`, quedan reproducidas individualmente en cuarentena con payload literal; no se reparan ni descartan.
- Dos ejecuciones producen un lote y los mismos recuentos. Prueba real completa: 171,99 s incluyendo las precargas DEV-303 y DEV-304.
- Hash original intacto: `2117c3e33c05158dd10f81ce07424dd1ea2d0f36747faea3ad9c630b2d4ab37b`.
- Contrato en `docs/SPECIALTY_IMPORT_CONTRACT.md`; DEV-306 no iniciado.

## DEV-306 — Completado por exclusión formal del piloto

- D-009 y ADR-0003 se aplican sin reinterpretación: interacciones quedan fuera de la importación/consolidación del piloto de fichas técnicas y permanecen como línea separada de migración y conciliación.
- `Interacciones-cargaMaster250626.xlsx` conserva su hash inventariado; no se modificó ni se creó un importador que materialice sus 872.296 filas de datos.
- Se registran la relación observada de 436.148 filas `AplicaA`, cardinalidad 1..21 y cero huérfanos, sin aceptar `IDEXTERNO` como clave canónica ni deduplicar repeticiones.
- INT-001..INT-005 delimitan fuente/versionado, identidad, ciclo de vida, muestra de importación y contrato de entrega que deben resolverse antes de reabrir la migración completa.
- Contrato en `docs/INTERACTION_MIGRATION_BOUNDARY.md`. Al cerrar DEV-306, Gate 3 seguía abierto y DEV-307 no se había iniciado.

## DEV-307 — Completado

- Motor puro y determinista para comparar afirmaciones de procedencia sobre una identidad exacta de ordinal, entidad, bloque y campo.
- La igualdad compara sin normalizar estado lógico y valor literal; espacios, mayúsculas y los estados no_consta/no_aplica permanecen diferenciados.
- Una prioridad pendiente nunca selecciona valor. Una prioridad aceptada exige orden explícito y referencia de decisión humana; las reglas de otro campo se rechazan.
- Coincidencias exactas conservan todas las procedencias. Conflictos resueltos por regla también conservan todas las afirmaciones; una fuente prioritaria internamente contradictoria permanece sin resolver.
- No se añadieron prioridades concretas, heurísticas de matching, persistencia, migraciones, integración CIMA/FT ni exportación.
- Contrato en docs/PROVENANCE_CONFLICT_ENGINE.md. Al cerrar DEV-307, Gate 3 seguía abierto; DEV-308 se completó posteriormente.

## DEV-308 — Completado

- Consolidador agregado implementado sobre los artefactos reproducibles de DEV-002 y DEV-009; no vuelve a perfilar celdas ni serializa filas o relaciones.
- Valida los manifiestos y hashes de entrada, rechaza artefactos modificados y no sobrescribe una salida existente.
- Dos informes reales tardaron 0,462 s y 0,336 s, fueron idénticos byte a byte y produjeron el hash 4009cac62bb27974ee3ff15a6b863a03cbb090816e220cb2aee66da128745d48.
- Resultados: 730 columnas, 9.301.670 valores materiales, 6.510.031 nulos, 52 fórmulas, 106 claves candidatas observadas, seis grupos de duplicados, cuatro excesos, 24 valores al límite y 275 huérfanos/184 claves.
- Las claves candidatas y los duplicados no se reinterpretan como decisiones de dominio; no se reparó, normalizó, truncó ni deduplicó ningún original.
- Contrato en docs/DATA_QUALITY_REPORT.md. Al cerrar DEV-308, Gate 3 quedó pendiente de la revisión formal realizada posteriormente; Fase 4 no se inició.

## Gate 3 — PASS

Revisión formal en docs/PHASE_3_GATE_REVIEW.md. Los maestros en alcance se importan idempotentemente o están excluidos por decisión aceptada; cada valor importado conserva lote y procedencia; los 275 huérfanos/184 claves permanecen clasificados en cuarentena; las incidencias se informan sin normalización ni reparación silenciosa.

Fase 3 queda cerrada. Fase 4 no se inicia automáticamente: D-013 está cerrada, pero el conjunto oro aún no está implementado ni anotado y faltan los dos anotadores de GOLD-002.

## Decisiones pendientes

- PROVIDER-001 debe resolverse antes de reglas condicionales definitivas; PROVIDER-002 antes del exportador definitivo.
- Las excepciones concretas por campo y el mapeo CIMA se verificarán en sus fases sin reabrir prioridades implícitas.
- Contrato de exportación y separador decimal siguen pendientes en sus fases; D-013 ya cerró el dimensionado de hardware, mientras D-014 mantiene pendiente el modelo/servidor exactos.

## Prerrequisitos de Fase 4 — En preparación

- `docs/GOLD_SET_ANNOTATION_CONTRACT.md` define selección, unidad, evidencia, estados, doble anotación y salidas del conjunto oro. La herramienta no está implementada y no se ha anotado ninguna ficha.
- Las 20 fichas se seleccionarán desde el universo de 500 ya capturado en DEV-208 reutilizando `cima-sampling-v1`; no se descargará nada nuevo ni se estratificará por ATC, ausente en el inventario.
- La evidencia se cita por desplazamientos sobre el `contenido` HTML literal de la sección, sin desescapar entidades ni normalizar espacios. Un intervalo que parte una entidad o etiqueta se advierte al anotador y no se corrige automáticamente.
- Los estados de anotación son los ya validados en DEV-011; `pending` bloquea el cierre del conjunto oro.
- Los desacuerdos entre los dos anotadores se conservan y se concilian de forma identificada; la tasa de acuerdo se publica junto con las métricas y acota lo exigible al modelo.
- `docs/GPU_SIZING_ANALYSIS.md` registra D-013: servidor interno con al menos 24 GB de VRAM; D-014 conserva abierta la elección exacta tras benchmark.
- DEV-401, DEV-403, DEV-405 y DEV-407 pueden avanzar sin GPU; DEV-402 y DEV-408 la requieren.
- GOLD-001 está cerrada con semilla `407`; GOLD-003 está cerrada sin estratificación ATC inicial porque DEV-208 no aporta ese atributo. GOLD-002 (dos anotadores farmacéuticos identificados) sigue abierta.
- Sin código, migraciones, descargas ni modificación de fuentes en este trabajo.

## DEV-405 — Núcleo preparatorio verificado

- Verificador literal de evidencia implementado en `pharma_validator_api.evidence_verification`: módulo puro, determinista, sin persistencia ni acceso a base de datos.
- La cita se compara por igualdad exacta contra el texto de la sección tal cual se almacenó; no se desescapan entidades HTML ni se normalizan espacios.
- Una cita inventada, desplazada un solo carácter o desescapada se rechaza. Una cita que parte una entidad HTML se admite si sus desplazamientos reproducen el literal; expandirla hasta un límite limpio cambiaría el texto citado y está prohibido.
- Longitud de cita exigida entre 10 y 400 caracteres según la especificación 8.2. `no_encontrado` se admite sin cita solo si no aporta valor ni opciones.
- Las políticas de pre-relleno se hacen cumplir aquí: `oculto` no persiste nada, `solo_evidencia` nunca admite valor, `proponer_opciones` nunca admite valor único y ningún campo protegido puede llegar preseleccionado.
- Observación factual sobre el corpus de DEV-208: 1.464 de 13.907 secciones (10,5%) carecen de `contenido` por ser cabeceras de agrupación. Una cita contra ellas se rechaza con un diagnóstico propio, distinto de un intervalo mal calculado. No se repara el corpus ni se sintetiza contenido.
- Validado además sobre una ficha real: cita válida admitida, cita inventada y cita contra cabecera rechazadas.
- 19 pruebas específicas. Suite completa 112/112: 91 en `backend/` (819,99 s) y 21 en `tests/`. Ruff y mypy estricto sin incidencias en 23 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/EVIDENCE_VERIFICATION_CONTRACT.md`. No se ha implementado el extractor, el cliente local ni la persistencia de propuestas.

## DEV-401 — Núcleo preparatorio verificado

- Interfaz `ExtractorLLM` implementada en `pharma_validator_api.extractor`: abstracta, sustituible por configuración, sin sockets, sin modelo y sin dependencia de hardware.
- La implementación es sustituible; la admisión no lo es. `run_extraction` verifica toda propuesta con el verificador literal de DEV-405 antes de admitirla, de modo que un adaptador devuelve candidatas y nunca decisiones.
- Una prueba específica confirma que una implementación no puede puentear la barrera afirmando su propia validez: la cita inventada se rechaza igualmente.
- `SectionRequest` agrupa los campos que dependen de un apartado en una sola llamada, según la especificación 8: de unas 150 llamadas por documento a unas 15.
- Toda propuesta admitida queda atribuida a versión de extractor y modelo; sin esa identidad, la comparación entre tamaños de DEV-408 no sería interpretable.
- Un fallo del extractor no bloquea la revisión manual: se registra incidencia y la sección devuelve cero propuestas admitidas. Campo no solicitado, duplicado o ausente también producen incidencia sin inventar ausencia.
- `NullExtractor` no propone ningún valor y hace ejecutable el resto de la Fase 4 sin GPU, materializando la degradación elegante de 8.4.
- 12 pruebas; Ruff y mypy estricto sin incidencias en 24 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/EXTRACTOR_INTERFACE_CONTRACT.md`. No se ha implementado el adaptador real (DEV-402), el esquema guiado (DEV-403) ni la reanudación por lotes (DEV-406).

## DEV-403 — Núcleo preparatorio verificado

- Esquema JSON de salida guiada implementado en `pharma_validator_api.guided_schema`, versión `guided-extraction-v1`.
- El esquema es cerrado: `additionalProperties` falso en raíz y resultados, `required` sobre las ocho claves de 8.2, recuento de resultados fijado al número de campos pedidos y enum de campo restringido a esos nombres.
- La longitud de `evidencia_texto` se acota a 10..400 caracteres, el mismo rango que verifica DEV-405.
- La sección citada la aporta la petición, no el modelo: pedírsela le permitiría declarar un apartado distinto del que se le mostró. Una primera versión la leía de la respuesta y habría dejado sin sección toda propuesta con cita, provocando en DEV-405 un rechazo por motivo equivocado.
- Los valores se validan contra `tipo_dato` sin reparar: `CHAR` que excede falla sin truncar, `DECIMAL` con exceso de escala falla sin redondear, `BIT` solo admite 0 o 1 y un tipo no reconocido no se relaja a texto libre.
- Una respuesta malformada es error explícito, nunca una propuesta parcialmente reconstruida.
- 22 pruebas; Ruff y mypy estricto sin incidencias en 25 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/GUIDED_SCHEMA_CONTRACT.md`. Con DEV-401 y DEV-405 suman 53 pruebas de Fase 4 sin GPU. La traducción a GBNF y el cliente real siguen en DEV-402.

## DEV-404 — Núcleo preparatorio verificado

- Agrupación por apartado implementada en `pharma_validator_api.section_grouping`: módulo puro que lee `ft_section_literal` tal como lo importó DEV-302, sin reinterpretar el catálogo.
- Medido sobre el catálogo real: 353 definiciones, 129 campos extraíbles resueltos en 14 llamadas por documento. La especificación estimaba ~150 campos en ~12 apartados.
- Apartados citados: 1, 2, 3, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 6.1, 6.3, 6.5 y 6.6.
- Un campo citado en varios apartados se pide en todos: la evidencia puede estar en cualquiera y descartar apartados perdería la cita. El orden del literal no es significativo.
- Ningún campo desaparece en silencio: 245 diagnósticos, de los cuales 208 son campos sin apartado declarado y 37 repeticiones dentro del mismo apartado.
- Los 208 sin apartado son del mismo orden que los 204 no procedentes de FT de DEV-006, pero no son la misma cifra ni se ha comprobado que sean el mismo conjunto; la diferencia queda como observación.
- El catálogo conserva identidades repetidas. La repetición se informa y el campo se solicita una vez; no se deduplica el catálogo ni se fusionan definiciones. Este caso lo detectó la validación contra datos reales, no las pruebas sintéticas.
- El nivel superior de un apartado nunca es 0: la hoja contiene, fuera de las 353 definiciones, una tabla de resumen con ratios como 0.375 que no son secciones. Las 353 definiciones no contienen numéricos en esa columna.
- 17 pruebas; Ruff y mypy estricto sin incidencias en 26 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/SECTION_GROUPING_CONTRACT.md`. Con DEV-401, DEV-403 y DEV-405 suman 70 pruebas de Fase 4 sin GPU.

## DEV-406 — Núcleo preparatorio verificado

- Planificador reanudable implementado en `pharma_validator_api.extraction_batches`: módulo puro, sin sockets ni persistencia; quien ejecuta aporta el estado completado.
- La unidad reanudable es una llamada: versión documental, apartado y conjunto de campos. El orden de los campos no cambia su clave; el conjunto sí, porque la respuesta depende de qué se preguntó junto.
- La huella de configuración cubre planificador, versión de extractor, modelo, prompt y esquema. Una unidad solo se reutiliza con la misma huella.
- Cambiar modelo, prompt o esquema no invalida ni borra el trabajo anterior: lo marca como superado y replanifica. Es lo que permitirá a DEV-408 comparar dos tamaños sobre el mismo corpus sin pisar la primera ejecución.
- El reintento de incidencias es configurable: una incidencia puede ser transitoria o estable, y la decisión es de quien opera el lote.
- Las unidades pendientes se ordenan por documento y apartado en orden numérico, no por hash: un lote de 7.500 peticiones debe ser legible mientras avanza. El criterio se comparte con DEV-404 mediante `section_sort_key`.
- Se distinguen fallo de unidad (esperable, no interrumpe) y error de uso (unidad duplicada o estado repetido, se detiene explícitamente).
- 17 pruebas; Ruff y mypy estricto sin incidencias en 27 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/EXTRACTION_BATCH_CONTRACT.md`. Con DEV-401, DEV-403, DEV-404 y DEV-405 suman 87 pruebas de Fase 4 sin GPU.

## DEV-510 — Núcleo preparatorio verificado

- Reglas de pre-relleno implementadas en `pharma_validator_api.prefill_policy`, módulo puro e independiente de la interfaz: la pantalla consumirá estas decisiones en lugar de reimplementarlas.
- Las cuatro políticas de la especificación 9.2 quedan cubiertas: `proponer_valor` precarga con evidencia, `proponer_opciones` ofrece candidatos sin marcar, `solo_evidencia` deja la casilla vacía con aviso de criterio farmacéutico y `oculto` no aparece.
- Ejemplo canónico `ADUDOMAXDIA` cubierto por prueba: la evidencia del apartado 4.2 se muestra, la casilla queda vacía y el aviso indica que la ficha no declara dosis máxima.
- La política es una regla, no una recomendación: un valor pasado a un campo protegido se descarta en lugar de mostrarse, y `assert_no_protected_preselection` detecta incluso un plan construido a mano que intente saltarse la comprobación.
- Confirmación en bloque conforme a 9.3: solo `proponer_valor` y solo con la evidencia visible, que es un argumento explícito y no una suposición. Un `proponer_valor` sin evidencia tampoco admite bloque.
- Esta barrera es distinta de la de DEV-405: aquella protege la veracidad de la cita, esta la autoría de la decisión. Ninguna sustituye a la otra.
- 13 pruebas; Ruff y mypy estricto sin incidencias en 28 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/PREFILL_POLICY_CONTRACT.md`.

## DEV-501 — Núcleo preparatorio verificado

- Identificación del revisor implementada en `pharma_validator_api.reviewer_identity`, con la lista configurable `APP_REVIEWERS` en formato `identificador:Nombre`.
- La garantía es `declarada` y está explícita en el tipo, no en un comentario: la firma identifica quién dijo ser, no quién era. El campo permite que una futura autenticación real (D-018, reevaluable en Fase 8) sea un cambio de valor y no una reinterpretación silenciosa.
- Sin revisor seleccionado no se guarda ninguna validación; un nombre fuera de la lista tampoco firma; una lista vacía no firma nada.
- Revisor ausente y revisor desconocido son errores distintos con mensajes distintos: uno indica que la pantalla no pidió usuario y el otro un intento de firma indebida.
- La doble validación de 11.1 exige dos revisores distintos y la comprobación vive junto a la resolución de identidad, no en la pantalla.
- Verificado de extremo a extremo que el formato documentado en `.env.example` se lee sin adaptaciones.
- 15 pruebas; Ruff y mypy estricto sin incidencias en 29 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/REVIEWER_IDENTITY_CONTRACT.md`.

## DEV-506 — Núcleo preparatorio verificado

- Estados de validación implementados en `pharma_validator_api.validation_states`: módulo puro, sin persistencia ni auditoría; la regla vive junto a la decisión para que ninguna vía de entrada la evite.
- El módulo describe el plano interno y no traduce estados al contrato del proveedor: ADR-0004 está aceptado para el modelo interno y la serialización externa sigue pendiente bajo D-011/PROVIDER-002. Por eso habla de resolución interna y cierre de revisión, no de elegibilidad de exportación.
- `no_aplica` es un estado propio, distinto de `no_consta`, conforme a DEV-011: uno dice que el dato no está en las fuentes, el otro que el campo no tiene sentido para ese medicamento.
- `no_consta` exige declarar qué fuentes son aplicables, cuáles obligatorias y cuáles se revisaron, y falla nombrando las que faltan. Sin esa comprobación sería indistinguible de «no lo he mirado».
- `no_consta` y `no_aplica` solo puede decidirlos un farmacéutico. El comentario es obligatorio donde DEV-011 lo exige: siempre en `no_aplica`, y en `no_consta` solo si el campo es obligatorio.
- `no_consta` no admite valor final: es una ausencia comprobada, y llevar valor la convertiría en un dato inventado.
- Nada resuelto vuelve a `pendiente`: revertir borraría la autoría sin rastro. Para deshacer se registra otra decisión, conservando el evento anterior.
- Revertir `no_consta`/`no_aplica` y salir de `revision_pendiente` exigen comentario explícito.
- Un cambio de versión documental marca como `revision_pendiente` y no borra ni invalida. Lo que nunca se decidió sigue `pendiente`: marcarlo falsearía el recuento de trabajo hecho.
- El cierre de revisión distingue retención por estado y por doble validación sin conciliar; un campo `confirmado` bloqueado se retiene igual, con el motivo registrado aparte. Qué se exporta y en qué formato no se decide aquí.
- 15 pruebas; Ruff y mypy estricto sin incidencias en 30 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/VALIDATION_STATES_CONTRACT.md`.

## DEV-508 — Núcleo preparatorio verificado

- Medición de `segundos_empleados` implementada en `pharma_validator_api.time_measurement`: módulo puro que recibe intervalos de foco ya observados; no lee relojes ni depende de la interfaz.
- Se descuenta la inactividad por encima de 60 segundos, según 7.2. Comprobado con un caso real: dos campos, uno de 8 s y otro abandonado 3.600 s, dan una media de 34,0 s por campo frente a 1.804,0 s sin descuento.
- Un tramo de exactamente 60 segundos no se marca como recortado: el umbral es el límite de lo que cuenta, no el principio de lo que sobra.
- El tiempo descartado y la marca de recorte se informan junto al contado: descartar en silencio impediría distinguir un campo genuinamente difícil de una pantalla olvidada abierta.
- Dos intervalos de foco solapados son error explícito, no una duración estimada: el foco no puede estar en dos sitios a la vez y un solapamiento indica captura defectuosa.
- Un campo sin foco cuenta cero segundos y sigue siendo campo medido; excluirlo haría que la media mejorase sola al ignorar los campos que nadie tocó.
- 15 pruebas; Ruff y mypy estricto sin incidencias en 31 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/TIME_MEASUREMENT_CONTRACT.md`.

## DEV-507 — Núcleo preparatorio verificado

- Edición de bloques repetibles implementada en `pharma_validator_api.block_editing`: módulo puro que transforma ocurrencias y describe qué cambió, para que la auditoría consuma esa descripción en lugar de reconstruirla.
- Las cinco operaciones que pide el plan son justamente las que pueden violar la regla de ocurrencias explícitas, y cada una lleva su salvaguarda.
- Crear no fabrica procedencia: una ocurrencia añadida por un revisor no puede declarar `origin_provenance`, o una fila inventada sería indistinguible de una importada.
- Eliminar una ocurrencia importada exige comentario y el mensaje sugiere marcarla no aplicable; una añadida por el revisor se retira sin fricción.
- Reordenar debe cubrir exactamente las ocurrencias existentes: omitir una la eliminaría de hecho, esquivando la salvaguarda de eliminación.
- Fusionar exige comentario y falla si ambas ocurrencias afirman valores distintos para el mismo campo: elegir uno sería decidir un dato clínico sin constancia de qué se descartó. Se admiten complementarias, de forma simétrica, y un campo ausente en ambas sigue ausente.
- Marcar no aplicable conserva los valores intactos, conforme a DEV-011, y es reversible con justificación.
- Durante la implementación se corrigió un fallo propio: la fusión tomaba como conflicto un ausente en la ocurrencia de origen frente a un valor en la de destino. Lo detectó una prueba antes de que existiera interfaz, y se añadió la prueba de simetría que faltaba.
- 22 pruebas; Ruff y mypy estricto sin incidencias en 32 ficheros. Sin migraciones ni cambios de datos.
- Contrato en `docs/BLOCK_EDITING_CONTRACT.md`.

## Integración de la cadena — Verificada

- Suite de integración en `backend/tests/test_phase4_pipeline_integration.py`: comprueba lo que ninguna prueba unitaria puede, que los módulos encajan sin adaptadores y que las barreras siguen en pie cuando los datos atraviesan toda la cadena.
- Recorrido completo verificado: catálogo → agrupación por apartado → plan de lote → extracción → presentación en pantalla. El campo `oculto` no se pide y los tres restantes caen en dos apartados.
- Un extractor que devuelve citas inventadas para todos los campos queda detenido antes de la presentación: cero propuestas admitidas y ninguna conserva su valor.
- Los campos protegidos permanecen vacíos en la pantalla completa: `proponer_valor` precargado, `solo_evidencia` con casilla vacía, `proponer_opciones` sin marcar y `oculto` no visible.
- Reanudación tras interrupción y cambio de modelo comprobados sobre peticiones reales generadas por la agrupación, no sobre fixtures artificiales.
- 5 pruebas de integración; Ruff y mypy estricto sin incidencias en 32 ficheros.

## Incidencia observada — Renombrado de directorios en Windows

- Una ejecución del verificador integral falló con `1 failed, 240 passed`: `test_aggregate_profile_is_reproducible` de DEV-002 lanzó `PermissionError [WinError 5]` al ejecutar `staging.replace(output_dir)` en `scripts/profile_reference_files.py:409`.
- El fallo es de entorno, no de lógica. La prueba pasa en aislamiento y se repitió cinco veces seguidas en verde; solo falló dentro de la suite completa, con los importadores pesados ejecutándose antes.
- Es el mismo patrón registrado en DEV-208: el renombrado de directorios falló dos veces por la caché de Windows y se resolvió con una entrada ZIP atómica, tras autorización humana.
- No se ha modificado `scripts/profile_reference_files.py`: DEV-002 está cerrado y su hash reproducible es evidencia de fase. Cambiarlo sin decisión humana alteraría un artefacto ya verificado.
- El patrón `staging.replace(output_dir)` no es exclusivo del perfilador: aparece en seis scripts —`analyze_integrity_incidents.py:161`, `analyze_reference_relationships.py:200`, `generate_data_quality_report.py:366`, `import_omeprazole_fixture.py:174`, `profile_reference_files.py:409` y `roundtrip_omeprazole_fixture.py:201`—. La incidencia afecta potencialmente a todos ellos, no solo al que falló.
- Queda como incidencia abierta: la reproducibilidad de estos artefactos no está en cuestión, pero el verificador puede fallar de forma intermitente en Windows por esta causa. Si se decide corregirlo, la solución candidata es la misma que se aceptó en DEV-208 y debería aplicarse a los seis puntos a la vez, no solo al que se manifestó.
- La ejecución integral posterior del 2 de septiembre de 2026 terminó con código 0 en aproximadamente 5 minutos y medio: 295/295 pruebas Python, Ruff, mypy sobre 32 ficheros, Vitest, ESLint, build, Compose, 8/8 referencias y Alembic upgrade/downgrade. La incidencia queda registrada como intermitente, no reproducida en esta corrida.

## Pureza de los módulos — Verificada

- Suite en `backend/tests/test_module_purity.py`: convierte en comprobable lo que los contratos afirmaban en prosa. Una afirmación documental envejece; esta no.
- Los diez módulos de Fases 4 y 5 se importan con `socket.socket` bloqueado. Importa para 8.3: no hay salida a internet, y un módulo que abriera una conexión al importarse rompería esa garantía en silencio.
- Ninguno llama a primitivas de disco ni importa `sqlalchemy`, `httpx`, `requests`, `urllib`, `pathlib` o `shutil`, ni las capas `database`/`models`.
- La comprobación usa árbol sintáctico y no subcadenas. La primera versión daba dos falsos positivos porque `requests` aparece como nombre de campo (`requests: tuple[SectionRequest, ...]`) y `replace(` como `dataclasses.replace`; el defecto estaba en la prueba, no en los módulos.
- Se confirmó que la prueba detecta una violación real inyectando `import sqlalchemy` y una escritura a disco en una copia del módulo: ambas se señalan.
- La primera versión de esta suite rompió 21 pruebas de otras tres suites. Usaba `importlib.reload`, que sustituye las clases del módulo por otras nuevas dentro del mismo intérprete: las excepciones seguían lanzándose, pero `pytest.raises` dejaba de reconocerlas por proceder de una clase distinta. El fallo no se manifestaba al ejecutar cada suite por separado, solo en la suite completa.
- Corregido importando cada módulo en un intérprete aparte mediante `subprocess`. Una prueba de pureza no puede contaminar el estado global de la sesión que verifica.
- 30 pruebas; Ruff y mypy estricto sin incidencias en 32 ficheros.

## Fase 5 — No abierta formalmente

DEV-510, DEV-501, DEV-506, DEV-508 y DEV-507 se han adelantado como núcleos de decisión y cálculo verificables sin interfaz. La Fase 5 no está iniciada ni su puerta de salida cumplida: no existen el selector de interfaz, la cola de trabajo (DEV-502), la pantalla de tres zonas (DEV-503), la navegación por teclado (DEV-504), el guardado incremental (DEV-505), la persistencia de las validaciones, la interfaz de edición de bloques ni la captura de foco que alimenta la medición.

Adelantar estos núcleos no sustituye la entrada ni la puerta de salida de Fase 4. D-013 está cerrada; el bloqueo de entrada restante es definir y anotar realmente el conjunto oro con dos farmacéuticos identificados.

La vertical de revisión descrita más abajo tampoco abre la Fase 5: es un spike de producto demostrable. De su alcance solo quedan parcialmente adelantados el guardado por campo (DEV-505) y la persistencia de estados (DEV-506); la cola de trabajo, la pantalla de tres zonas, la navegación por teclado, la edición de bloques y la medición de foco siguen sin implementarse.

## Vertical funcional de revisión — Spike de producto demostrable

- Recorrido completo ejecutable: listado → búsqueda → ficha → fuentes y procedencia → discrepancias → decisión firmada → guardado → listado con el estado actualizado.
- **No abre la Fase 5 ni cierra DEV-502/503/504/505/509.** Es un spike de producto para poder enseñar el sistema, no evidencia de que las reglas pendientes estén cerradas. La puerta de entrada de Fase 5 sigue sin cumplirse porque la Fase 4 no está abierta.
- La capa HTTP no reimplementa ninguna regla clínica: `pharma_validator_api.review` traduce entre la base de datos y los módulos puros ya verificados (`reviewer_identity`, `validation_states`, `provenance_conflicts`) y propaga sus mensajes literalmente hasta la pantalla. Nueve pruebas comprueban que la vía HTTP no puede saltarse ninguna barrera: sin revisor, revisor desconocido, `no_aplica` sin comentario, `no_aplica` firmado por no farmacéutico, `no_consta` sin revisar las fuentes obligatorias, `confirmado` sin valor final, vuelta a `pendiente` y reversión de `no_aplica` sin justificación.
- Las decisiones se persisten como eventos append-only en `validation_decision_record`. El modelo rechaza UPDATE y DELETE con `ImmutableHistoryError`: revertir se registra como otra decisión y el historial anterior se conserva. Verificado también que el trabajo confirmado sobrevive a un reinicio de la aplicación.
- Defecto propio detectado y corregido durante la implementación: la evaluación de discrepancias se hacía por fila de `field_value`, de modo que dos fuentes que discrepan producían dos filas y ninguna se comparaba con la otra; el resultado era siempre «sin conflicto». La unidad correcta es el campo dentro de la ocurrencia de bloque, y agrupar por nombre de campo a secas habría fusionado ocurrencias distintas del mismo bloque repetible. Lo detectó la prueba contra el conjunto DEMO, no una prueba sintética.
- Ninguna discrepancia se resuelve automáticamente: el motor de ADR-0007 se invoca deliberadamente sin regla de prioridad, de modo que un conflicto real queda en `unresolved_pending_priority` con todos los valores y procedencias conservados. La interfaz nunca aparenta que una decisión farmacéutica se haya tomado sola.
- La pantalla no precarga ningún valor y el desplegable de decisión arranca vacío. La vertical no consume todavía `prefill_policy`; no precargar es el comportamiento seguro por defecto y cumple D-023 sin depender de que la pantalla lo recuerde.
- Datos de demostración en `data/examples/showcase-demo.json`, generados de forma determinista por `scripts/generate_showcase_fixture.py`. Los nombres de campo y bloque proceden del catálogo real de 353 definiciones; los valores no proceden de los maestros ni de CIMA. Cada registro declara el sistema fuente `demo_showcase` y la interfaz muestra un aviso permanente. Los ficheros originales de referencia no se han modificado.
- Los módulos todavía inexistentes (Validaciones, Fuentes, Importaciones, Auditoría, Configuración) aparecen anunciados con una nota que declara qué hacen hoy, qué falta y de qué decisión dependen. Representarlos no cierra ninguna decisión ni ADR.
- Se corrigió una carencia real de la configuración de pruebas del frontend: con `globals` desactivado, la limpieza automática de Testing Library no se registraba y los árboles renderizados se acumulaban entre pruebas.
- 20 pruebas de backend y 6 de frontend nuevas. Suite completa: 294/294 Python, 6/6 Vitest, Ruff, mypy estricto sobre 33 ficheros, ESLint, build y Alembic upgrade/downgrade.
- Alcance, límites, comportamiento provisional y decisiones abiertas en `docs/REVIEW_VERTICAL_SPIKE.md`.

## DEV-407 — Selección del conjunto oro verificada; anotación no implementada

- Algoritmo `gold-selection-v1` implementado en `pharma_validator_api.gold_selection`: módulo puro, sin red ni disco, incorporado a la suite de pureza (33 pruebas sobre 11 módulos).
- Se implementa **solo la mitad de selección** de DEV-407. La anotación exige dos farmacéuticos identificados y GOLD-002 sigue pendiente de decisión humana. Separarlas permite tener la selección verificada y estable sin inventar anotadores para poder ejecutarla.
- Selección verificada sobre el corpus real de 500 documentos de DEV-208, sin red y sin modificar el corpus: dos ejecuciones producen el mismo `run_id` `ac843f92c081045bd61ed80d6aef13c703f88275eeab433291ddb6ce9dd792cd` y los mismos 20 `nregistro`. La prueba comprueba además que el manifiesto no se ha tocado.
- La ordenación previa por `nregistro` no es cosmética: `random.sample` depende del orden de la secuencia, de modo que sin ella el mismo corpus leído en otro orden daría un conjunto oro distinto con la misma semilla. Hay una prueba específica que lo fija.
- La huella del universo cubre `nregistro` **y** versión documental. Dos corpus con los mismos registros pero versiones distintas no son el mismo universo, y tratarlos como tal permitiría que una selección «reproducible» se refiriese en realidad a documentos diferentes.
- Una selección que difiera de la publicada detiene el proceso con conflicto en lugar de reescribirla: reescribirla invalidaría en silencio toda anotación hecha sobre el conjunto anterior.
- GOLD-001 (semilla 407) y GOLD-003 (sin estratificación ATC) se aplican como decisiones ya cerradas; no se ha cerrado ninguna decisión nueva.
- 13 pruebas; Ruff y mypy estricto sin incidencias en 34 ficheros. Sin migraciones ni cambios de datos.
- **DEV-407 no queda cerrado y la Fase 4 no se abre**: faltan los criterios 2 a 7 del contrato, que pertenecen a la anotación.

## Estabilización operativa de la demo — 3 de septiembre de 2026

- Causa del fallo navegador/API reproducida: Compose no configuraba CORS y el navegador recibía `405` en el preflight `OPTIONS /records` desde `http://localhost:5173`.
- `compose.yaml` declara ahora los orígenes locales de la demo. El preflight real devuelve `200`, `Access-Control-Allow-Origin` y los métodos `GET, POST`.
- Verificados frontend y backend saludables, `/health`, `/docs`, seis registros DEMO, dos revisores, Alembic en `d51f7a2c9e04 (head)` y SQLite accesible. El piloto usa SQLite por ADR-0001; PostgreSQL no forma parte de la arquitectura aprobada actual.
- Smoke test real: decisión firmada guardada, backend reiniciado y decisión recuperada con historial, autor y estado agregado `en_revision` (`1/7`).
- Regresión añadida al test del scaffold para exigir `APP_CORS_ALLOW_ORIGINS` en Compose.
- Gate integral posterior: 332/332 pruebas Python, Ruff, mypy estricto sobre 34 módulos, 6/6 Vitest, ESLint, build Vite, Compose, 8/8 referencias y Alembic upgrade/downgrade; código 0.
- La corrección estabiliza el spike y no abre Fase 5. El siguiente bloque no bloqueado continúa siendo la herramienta offline de anotación DEV-407; la anotación real sigue bloqueada por GOLD-002.
## DEV-407B — Herramienta offline preparada; anotación humana pendiente

- Núcleo puro `pharma_validator_api.gold_annotations` y CLI `scripts/generate_gold_annotations.py` implementados sin reglas clínicas nuevas.
- Evidencia `valued` validada por igualdad exacta de offsets sobre el HTML literal de la versión inmutable; no se normaliza ni desescapa.
- Ocurrencias conservadas por ordinal; `source_absent`, `source_blank`, `no_consta` y `not_applicable` permanecen distintos y aplican sus requisitos.
- `pending` bloquea `--close`; dos anotaciones se conservan y cualquier diferencia exacta se publica como desacuerdo `open`, sin autorresolución.
- Salidas deterministas: selección, anotaciones JSONL, desacuerdos CSV, manifiesto con hashes y resumen Markdown. Un directorio existente nunca se sobrescribe.
- 8 pruebas específicas; 44/44 al incluir pureza; Ruff y mypy estricto sobre 35 módulos correctos.
- GOLD-002 y la anotación real por dos farmacéuticos siguen pendientes. DEV-407 no se cierra y Fase 4 no se abre.
- Gate integral posterior: 343/343 pruebas Python, 7/7 Vitest, Ruff, mypy estricto sobre 35 módulos, ESLint, build Vite, Compose, 8/8 referencias y Alembic upgrade/downgrade; código 0.

## Pulido UX del spike de revisión

- El revisor declarado se recuerda en el navegador, sin convertir su identidad declarada en autenticación.
- La evidencia y la versión documental son visibles; ya no dependen de un tooltip.
- El cliente bloquea `confirmado`/`corregido` sin valor y `no_aplica` sin comentario, manteniendo el backend como barrera final.
- 7/7 Vitest, ESLint y build Vite correctos.
## Última actualización

3 de septiembre de 2026.
