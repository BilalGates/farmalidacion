# Estado del proyecto

## Estado global

`FASE 0A CERRADA — FASE 0B CERRADA CON DEPENDENCIAS EXTERNAS — FASE 1 CERRADA — FASE 2 CERRADA — FASE 3 EN CURSO`

## Fase actual

Fase 3 en curso. DEV-301, DEV-302 y DEV-303 están completados; DEV-304 no se ha iniciado. Gate 2 permanece PASS.

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

## Decisiones pendientes

- PROVIDER-001 debe resolverse antes de reglas condicionales definitivas; PROVIDER-002 antes del exportador definitivo.
- Las excepciones concretas por campo y el mapeo CIMA se verificarán en sus fases sin reabrir prioridades implícitas.
- Contrato de exportación, separador decimal y hardware de inferencia siguen pendientes en sus fases.

## Última actualización

31 de agosto de 2026.
