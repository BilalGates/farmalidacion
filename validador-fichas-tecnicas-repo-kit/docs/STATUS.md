# Estado del proyecto

## Estado global

`FASE 0A CERRADA — FASE 0B EN DESCUBRIMIENTO`

## Fase actual

Fase 0B — Descubrimiento de dominio y modelo canónico. DEV-002 y el trabajo documental de DEV-003 están completados; el modelo físico y el round-trip todavía no están implementados.

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
- ADR-0004/D-010 continúa propuesto.
- ADR-0001 continúa propuesto; DEV-002 por sí solo no lo acepta.

## DEV-003 — Completado documentalmente

- Definidos `documento_fuente`, `documento_fuente_version`, `fragmento_fuente`, `registro_destino`, `instancia_bloque`, `valor_campo` y sus vínculos conceptuales.
- Diagrama y tabla de entidades, bloques, cardinalidades conservadoras y claves candidatas documentados en `docs/CANONICAL_CONCEPTUAL_MODEL.md`.
- Las 22 hojas de omeprazol tienen representación sin concatenar, deduplicar ni descartar ocurrencias.
- La demostración es de capacidad conceptual; la importación y comparación real siguen pendientes en DEV-007/DEV-008.
- D-004 y D-006 no se han cerrado; las claves y cardinalidades no demostradas permanecen abiertas.
- ADR-0001 permanece propuesto y no se ha iniciado DEV-004.

## Puerta 0B — No superada

Faltan el catálogo ampliado, claves y relaciones verificadas, la validación humana del modelo candidato, la importación/exportación real de omeprazol, la comparación de sus 22 hojas y la aceptación de ADR-0001. No se autoriza avanzar a Fase 1.

## Decisiones pendientes

- D-001, D-002, D-004, D-005, D-006 y D-010 requieren evidencia y validación humana.
- D-008 queda pendiente para Fase 3.
- Contrato de exportación, separador decimal y hardware de inferencia siguen pendientes en sus fases.

## Última actualización

25 de agosto de 2026.
