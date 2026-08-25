# Estado del proyecto

## Estado global

`FASE 0A CERRADA — FASE 0B EN DESCUBRIMIENTO`

## Fase actual

Fase 0B — Descubrimiento de dominio y modelo canónico. DEV-002 a DEV-008 están completados en su alcance de spike; el modelo físico no está implementado y la puerta requiere todavía decisiones y validación humana.

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
- ADR-0001 continúa propuesto; DEV-002 por sí solo no lo acepta.

## DEV-003 — Completado documentalmente

- Definidos `documento_fuente`, `documento_fuente_version`, `fragmento_fuente`, `registro_destino`, `instancia_bloque`, `valor_campo` y sus vínculos conceptuales.
- Diagrama y tabla de entidades, bloques, cardinalidades conservadoras y claves candidatas documentados en `docs/CANONICAL_CONCEPTUAL_MODEL.md`.
- Las 22 hojas de omeprazol tienen representación sin concatenar, deduplicar ni descartar ocurrencias.
- La demostración es de capacidad conceptual; la importación y comparación real siguen pendientes en DEV-007/DEV-008.
- D-004 y D-006 no se han cerrado; las claves y cardinalidades no demostradas permanecen abiertas.
- ADR-0001 permanece propuesto.

## DEV-004 — Completado como evidencia

- Analizador agregado dirigido implementado sin serialización de relaciones fila a fila.
- 35 hipótesis de clave y 12 relaciones evaluadas sobre cuatro maestros.
- 6 unicidades observadas; ninguna se declara clave natural aceptada.
- Cardinalidades observadas documentadas, incluidos bloques 0..N y hojas vacías 0..0.
- Reproducidas 275 filas huérfanas de excipientes, equivalentes a 184 claves paternas distintas.
- Hash de evidencia: `c685c293172fd3702db881eff6823409a6f9b8447772ab283ef159bba2f23a6c`.
- D-004/ADR-0005 siguen propuestos; D-006 pasa a propuesta documental en DEV-005, sin aceptación.

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
- ADR-0007 aceptado y D-008 cerrada; D-005 sigue pendiente y D-011 mantiene abierta la serialización externa de estados.

## DEV-007 — Completado como spike reversible

- Importador temporal seguro implementado en `scripts/import_omeprazole_fixture.py`; no define esquema físico ni infiere identidades de negocio.
- Las 22/22 hojas se representan con orden, filas materiales, valores literales, tipos observados, coordenadas, fórmulas y procedencia por fragmento.
- Se conservaron 616 ocurrencias técnicas provisionales y 2.674 valores materiales; no se concatenaron, deduplicaron ni descartaron ocurrencias.
- Dos corridas independientes produjeron instantáneas idénticas y el hash canónico `5e8564dcd726380aec23f031f6060e4450d2c0fa09f559589e9c6d32caebdb5f`.
- Los recuentos por hoja coinciden con el perfil agregado de DEV-002; suite completa 12/12 OK.
- Evidencia y límites en `docs/OMEPRAZOLE_CANONICAL_IMPORT_EVIDENCE.md`.
- ADR-0001 permanece propuesto: DEV-008 debe reconstruir y comparar semánticamente las 22 hojas.

## DEV-008 — Completado como round-trip reversible

- Reconstrucción OOXML temporal implementada en `scripts/roundtrip_omeprazole_fixture.py`; usa el original verificado como plantilla estructural inmutable y restaura los contenidos materiales desde DEV-007.
- Comparadas 22/22 hojas y 2.674/2.674 valores, tipos, fórmulas, estilos de celda, orden, visibilidad y estructura auxiliar, sin normalizaciones.
- Cero diferencias, defectos, pendientes, truncamientos, descartes, concatenaciones o partes auxiliares alteradas.
- Dos corridas de 8,165 s y 7,373 s produjeron XLSX e informes idénticos con hash reproducible `7d474de536f4e168636c286aabd4ab3339715dde04c3164900c58c5204926adf`.
- Suite completa 14/14 OK; la prueba de mutación confirma que un valor alterado se clasifica como defecto.
- Evidencia en `docs/OMEPRAZOLE_ROUNDTRIP_EVIDENCE.md`. No es el exportador final y ADR-0001 permanece propuesto.

## DEV-009 — Completado como evidencia de integridad

- Catálogo: cabecera reproducible y 353/353 filas activas.
- Reproducidos 275 huérfanos/184 claves, seis incidencias de duplicado, cuatro excesos y 24 valores exactamente al límite, sin reparar datos.
- Dos conflictos de tipo: `Composición / DESCRIPCION` (`CHAR(50)`/`CHAR(100)`) y `Links / DESCRIPCION` (`CHAR(100)`/`CHAR(255)`).
- Dos corridas idénticas: `987129be4c8d7b62517c0962e19279e01b00299c7c51490e179137b3040579e7`; suite 16/16 OK.
- Evidencia en `docs/INTEGRITY_INCIDENT_EVIDENCE.md`; no se aceptan claves ni reparaciones.

## Puerta 0B — No superada

DEV-011 está completado para el modelo interno: D-010 y ADR-0004 quedan aceptados en semántica, autoridad, comentarios, reversibilidad y doble validación. La serialización de `no_consta`/`not_applicable` sigue abierta bajo D-011; no se supera la puerta 0B ni se autoriza Fase 1.

Faltan cerrar o aceptar explícitamente las claves y relaciones todavía propuestas, validar humanamente el modelo candidato y aceptar o sustituir ADR-0001. No se autoriza avanzar a Fase 1.

## Decisiones pendientes

- D-004 y D-005 requieren validación humana o evidencia adicional; D-011 requiere el contrato del proveedor.
- Las excepciones concretas por campo y el mapeo CIMA se verificarán en sus fases sin reabrir prioridades implícitas.
- Contrato de exportación, separador decimal y hardware de inferencia siguen pendientes en sus fases.

## Última actualización

25 de agosto de 2026.
