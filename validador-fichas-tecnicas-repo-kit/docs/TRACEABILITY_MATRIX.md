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
| Perfilado reproducible de siete Excel | Plan Fase 0B; inventario de fuentes | 0B | `scripts/profile_reference_files.py`; contrato y manifiestos generados | dos corridas: hash `1999097257b99fe5cc52ab903da873085dd9abe5deb7b0a1d327670f04875976`; originales intactos |
| Filas materialmente pobladas | Inventario de fuentes | 0B | JSON agregado por libro/hoja | dimensión aparente separada de filas materiales; 7/7 libros procesados |
| Calidad agregada por columna | Inventario de fuentes; DEV-002 | 0B | `columns.csv`, `incidents-summary.csv`, resumen Markdown | 730 columnas; tipos, nulos, longitudes, fórmulas, duplicados y cardinalidad informados |
| Relaciones y huérfanos detallados | Inventario de fuentes; D-004/D-006 | 0B, 3 | pendiente de DEV-004/DEV-006 | no materializados en DEV-002; requieren reglas e identidad aprobadas |
| Round-trip semántico de 22 hojas | Plan Fase 0B; omeprazol de referencia | 0B | `docs/contracts/OMEPRAZOLE_SEMANTIC_COMPARISON_CONTRACT.md` | 22/22 hojas; cero defectos, descartes o concatenaciones |
| Sin normalización implícita | AGENTS.md; reglas no negociables | 0B, 3, 6 | reglas versionadas y diferencias clasificadas | toda transformación referencia decisión aceptada |
| Estados vacío/pendiente/no consta/no aplica | Especificación 7.1; D-010 | 0B, 5, 6 | ADR-0004 propuesto | tabla de decisión y round-trip sin sustituciones implícitas |
| Maestros como línea base con procedencia | D-007; ADR-0002 | 0B, 3 | contrato de perfilado y futura consolidación | valor trazable a fichero, hash, hoja y coordenada |
| Interacciones como línea separada | D-009; ADR-0003 | 0B, 3 | perfilado incluido; extracción FT excluida | alcance e informes separados |
| Procedencia múltiple | Ficheros reales y análisis | 0B, 3 | modelo de evidencia/procedencia | maestro, CIMA, FT y humano |
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
