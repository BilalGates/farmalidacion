# Matriz inicial de trazabilidad

| Requisito | Fuente | Fase | Evidencia de implementación | Prueba mínima |
|---|---|---|---|---|
| Corpus 500, oro 20, medida 50 | Especificación 1.1 | 2, 4, 5 | modelos de conjunto y comandos | misma semilla, mismos registros |
| Muestreo aleatorio/estratificado | Especificación 1.2 | 2 | servicio y CLI de muestreo | reproducibilidad + informe composición |
| Sin datos de paciente | Especificación 2-3 | todas | límites de dominio y revisión | búsqueda de esquemas/endpoints prohibidos |
| CIMA cacheada y limitada | Especificación 5.1 | 2 | cliente CIMA | retry, rate limit, cache hit |
| Relación nregistro-presentaciones | Especificación 5.1 | 0B, 2 | modelo canónico | fixture con varios CN |
| Catálogo gobernado por configuración | Especificación 6 | 0B, 3 | importador de catálogo | añadir campo sin cambiar código |
| Overrides CHAR(100) | Especificación 6.1 | 3 | regla de importación | test de ambos campos |
| Bloques repetibles | Ficheros reales | 0B, 1, 3 | `instancia_bloque` o decisión equivalente | round-trip omeprazol |
| Modelo conceptual canónico | Especificación 5-7; inventario; DEV-002 | 0B | `docs/CANONICAL_CONCEPTUAL_MODEL.md`; ADR-0001 propuesto | cobertura documental 22/22 hojas sin concatenar ni deduplicar ocurrencias |
| Documento, versión y registro destino separados | Especificación 5, 11, 13; D-002/D-020 | 0B, 2 | conceptos y vínculos del modelo candidato | cada valor referencia versión y fragmento; decisión aún propuesta |
| Identidad nregistro/CN/medicamento/especialidad/principio activo | Especificación 5.1; maestros; D-006 | 0B | ADR-0006 aceptado; vínculos tipados | no fusionar; cardinalidad factual CIMA pendiente de Fase 2 |
| Grafo de registros destino | Maestros; DEV-004/DEV-005 | 0B | `docs/TARGET_RECORD_RELATIONSHIP_EVIDENCE.md`; ADR-0006 propuesto | especialidad→medicamento y composición→principio activo sin huérfanos |
| Unidad de revisión contextual | Especificación 7, 10; D-001 | 0B, 5 | expediente contextual aceptado en ADR-0006 | caso con varias presentaciones pendiente de round-trip |
| Relación nregistro→CN | Especificación 5.1; D-006 | 0B, 2 | vínculo explícito propuesto | pendiente de muestra CIMA estructurada; prohibida equivalencia implícita |
| Perfilado reproducible de siete Excel | Plan Fase 0B; inventario de fuentes | 0B | `scripts/profile_reference_files.py`; contrato y manifiestos generados | dos corridas: hash `1999097257b99fe5cc52ab903da873085dd9abe5deb7b0a1d327670f04875976`; originales intactos |
| Filas materialmente pobladas | Inventario de fuentes | 0B | JSON agregado por libro/hoja | dimensión aparente separada de filas materiales; 7/7 libros procesados |
| Calidad agregada por columna | Inventario de fuentes; DEV-002 | 0B | `columns.csv`, `incidents-summary.csv`, resumen Markdown | 730 columnas; tipos, nulos, longitudes, fórmulas, duplicados y cardinalidad informados |
| Relaciones y huérfanos detallados | Inventario de fuentes; D-004/D-006 | 0B, 3 | agregados DEV-004; detalle pendiente de D-006/Fase 3 | no materializados fila a fila; requieren identidad aprobada |
| Cardinalidades padre-hijo observadas | Maestros; DEV-004 | 0B | `scripts/analyze_reference_relationships.py`; `docs/CARDINALITY_KEY_EVIDENCE.md` | 12 relaciones agregadas; máximos observados no normativos |
| Claves candidatas por bloque | Maestros; D-004 | 0B | ADR-0005 propuesto; tabla de 35 hipótesis | 6 unicidades observadas; hojas vacías y claves incompletas no aceptadas |
| Huérfanos de excipientes | Inventario; especialidades | 0B, 3 | informe DEV-004 | 275 filas, 184 claves paternas distintas, sin reparación silenciosa |
| Round-trip semántico de 22 hojas | Plan Fase 0B; omeprazol de referencia | 0B | `docs/contracts/OMEPRAZOLE_SEMANTIC_COMPARISON_CONTRACT.md` | 22/22 hojas; cero defectos, descartes o concatenaciones |
| Importación canónica temporal de omeprazol | Plan Fase 0B; DEV-007 | 0B | `scripts/import_omeprazole_fixture.py`; `docs/OMEPRAZOLE_CANONICAL_IMPORT_EVIDENCE.md` | 22/22 hojas, 616 ocurrencias y 2.674 valores; dos instantáneas idénticas con hash `5e8564dcd726380aec23f031f6060e4450d2c0fa09f559589e9c6d32caebdb5f` |
| Sin normalización implícita | AGENTS.md; reglas no negociables | 0B, 3, 6 | reglas versionadas y diferencias clasificadas | toda transformación referencia decisión aceptada |
| Estados vacío/pendiente/no consta/no aplica | Especificación 7.1; D-010 | 0B, 5, 6 | ADR-0004 propuesto | tabla de decisión y round-trip sin sustituciones implícitas |
| Maestros como línea base con procedencia | D-007; ADR-0002 | 0B, 3 | contrato de perfilado y futura consolidación | valor trazable a fichero, hash, hoja y coordenada |
| Interacciones como línea separada | D-009; ADR-0003 | 0B, 3 | perfilado incluido; extracción FT excluida | alcance e informes separados |
| Procedencia múltiple | Ficheros reales y análisis | 0B, 3 | modelo de evidencia/procedencia | maestro, CIMA, FT y humano |
| Matriz de fuentes por campo | Catálogo; ADR-0002; D-008 | 0B, 3 | `docs/SOURCE_PRIORITY_MATRIX.md`; ADR-0007 aceptado | 353/353 campos con regla o prioridad pendiente explícita |
| Conflicto entre fuentes | ADR-0002; D-008 | 0B, 3 | afirmaciones separadas y acción humana contractual | ninguna sustitución silenciosa; campo sin regla queda pendiente |
| Límites por clasificación FT | Catálogo; especificación 8-9 | 0B, 4, 5 | reglas `No`/directo/parcial/interpretación | parciales e interpretables nunca producen valor automático |
| Versiones inmutables | Especificación 11, 13 | 0B, 2, 7 | tablas de versión | cambio no sobrescribe anterior |
| Ninguna propuesta sin cita | Especificación 8.1 | 4 | verificador literal | rechazo de cita inventada |
| Salida estructurada | Especificación 8.3 | 4 | esquema de respuesta | respuesta inválida no persiste |
| Degradación a solo evidencia | Especificación 8.4 | 4 | configuración por campo | cambio sin despliegue |
| Sin preselección protegida | Especificación 9, 15.1 | 5 | componentes UI | test automático |
| Confirmación en bloque limitada | Especificación 9.3 | 5 | acción por bloque | rechazo en campos protegidos |
| Validación sin ratón | Especificación 10.4, 15.3 | 5 | atajos y foco | recorrido E2E teclado |
| Guardado incremental | Especificación 10.4 | 5 | API y estado | recarga sin pérdida |
| Segundos por campo | Especificación 7.2, 17 | 5 | eventos de tiempo | inactividad >60 s descontada |
| Doble validación L04 | Especificación 11.1 | 6 | reglas y conciliación | usuarios distintos, segunda ciega |
| Auditoría append-only | Especificación 11 | 6 | eventos inmutables | reconstrucción histórica |
| CSV/TXT/XLSX | Especificación 12 | 6 | exportadores | fixtures de formato |
| Sin truncamiento | Especificación 12.3 | 3, 6 | validador e informe | CHAR excedido falla |
| Exportación reproducible | Especificación 12.2 | 6 | snapshot de configuración | mismo estado, mismo contenido |
| Registro de cambios CIMA | Especificación 13 | 7 | tarea programada | nueva versión + diff |
| UI <100 ms por campo | Especificación 14 | 5 | precarga/cache local | prueba de rendimiento |
| Docker Compose | Especificación 15.9 | 1 en adelante | compose y fixtures | arranque limpio |
| Operación offline | Especificación 15.10 | 2 en adelante | fixtures/corpus local | bloqueo de red durante prueba |
