# Estado del proyecto

## Estado global

`FASE 0A CERRADA — FASE 0B CERRADA CON DEPENDENCIAS EXTERNAS — FASE 1 AUTORIZADA`

## Fase actual

Fase 1 iniciada. DEV-101 a DEV-105 están completados; el siguiente issue recomendado es DEV-106. Existe un núcleo físico inicial reversible, no un contrato físico definitivo de proveedor.

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

## Decisiones pendientes

- PROVIDER-001 debe resolverse antes de reglas condicionales definitivas; PROVIDER-002 antes del exportador definitivo.
- Las excepciones concretas por campo y el mapeo CIMA se verificarán en sus fases sin reabrir prioridades implícitas.
- Contrato de exportación, separador decimal y hardware de inferencia siguen pendientes en sus fases.

## Última actualización

25 de agosto de 2026.
