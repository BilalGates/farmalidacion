# Plan de desarrollo por decisiones, fases y puertas de salida

## 1. Enfoque

El desarrollo se organiza por reducción de riesgo, no por capas técnicas aisladas. Cada fase debe dejar un resultado demostrable, probado y reversible. El orden evita construir una interfaz o un extractor sobre un modelo que no pueda representar los maestros reales.

La regla de avance es simple:

> No se entra en una fase si la puerta de salida de la anterior no está superada o si existe una excepción aprobada mediante ADR.

## 2. Roles de trabajo

- **Responsable funcional / producto:** valida alcance, decisiones de farmacia, reglas de negocio y aceptación.
- **Agente principal de Codex:** actúa como tech lead, mantiene el plan, integra resultados y es el único responsable de declarar una tarea terminada.
- **Subagentes de lectura:** analizan dominio, datos, seguridad, pruebas y documentación en paralelo.
- **Agente de implementación:** realiza cambios acotados en una rama o worktree. Nunca hay dos agentes escribiendo sobre los mismos módulos a la vez.
- **Revisor humano:** aprueba ADRs, PRs y cualquier cambio de una regla clínica o de exportación.

## 3. Fase 0A — Gobierno del repositorio y arranque de Codex

### Objetivo

Crear un entorno de trabajo donde Codex conozca el proyecto, siga reglas estables y deje trazabilidad de decisiones antes de escribir código de producto.

### Trabajos

- Instalar `AGENTS.md`, agentes de proyecto y la skill `pharma-validator-companion`.
- Incorporar la especificación v2 y el inventario de fuentes.
- Crear registro de decisiones, plantilla ADR, backlog, matriz de trazabilidad y estado.
- Definir convención de ramas, commits, PRs, issues y worktrees.
- Colocar los ficheros de referencia localmente y verificar hashes.
- Crear CI mínimo cuando exista el primer scaffold.

### Puerta de salida

- Codex enumera correctamente las instrucciones activas.
- Los ficheros de referencia se validan por hash.
- Todas las decisiones abiertas tienen identificador, propietario, fecha límite de fase y recomendación inicial.
- No existe todavía código de negocio que congele un modelo de datos.

## 4. Fase 0B — Descubrimiento de dominio y modelo canónico

### Objetivo

Definir cómo representar sin pérdida documentos, maestros, registros destino, bloques repetibles, procedencias y versiones.

### Trabajos

1. Crear un perfilador reproducible de los Excel.
2. Generar por hoja: filas materialmente pobladas, columnas, tipos observados, nulos, longitudes, duplicados y claves candidatas.
3. Reconstruir la jerarquía entidad → bloque → subbloque → campo → rol.
4. Identificar cardinalidades y claves naturales de todos los bloques.
5. Definir la relación entre `nregistro`, código nacional, medicamento, especialidad y principio activo.
6. Definir la ontología de procedencia: maestro, CIMA JSON, ficha técnica, decisión humana, transformación autorizada y fuente externa.
7. Definir versiones inmutables de documentos y evidencias.
8. Preparar el modelo canónico candidato y sus ADRs.
9. Importar el caso de omeprazol.
10. Exportarlo de vuelta y comparar semánticamente las 22 hojas.

### Decisiones que deben cerrarse

- Unidad de revisión.
- Entidades y relaciones canónicas.
- Cardinalidad de cada bloque.
- Claves y reglas de identidad.
- Significado de `S*` y `N*`.
- Fuente y prioridad por campo.
- Estrategia de maestros existentes.
- Alcance de interacciones.
- Semántica de `no_consta`, `no_aplica`, vacío y pendiente.

### Puerta de salida

- ADR del modelo canónico aceptado.
- Catálogo ampliado sin colisiones ambiguas.
- Importación y exportación de omeprazol sin pérdida de filas, claves, relaciones ni valores.
- Toda diferencia está clasificada como orden, formato, normalización autorizada o defecto.
- Cero truncamientos y cero descartes silenciosos.

### Prohibido antes de superar la puerta

- Finalizar las tablas de propuestas y validaciones.
- Construir la pantalla definitiva de revisión.
- Diseñar el exportador final.
- Integrar el modelo local como dependencia central.

## 5. Fase 1 — Scaffold ejecutable y primer corte vertical sin IA

### Objetivo

Levantar una aplicación mínima completa que demuestre la arquitectura, migraciones y flujo de datos sin depender todavía del extractor.

### Trabajos

- Monorepo o estructura equivalente con `backend/`, `frontend/`, `infra/` y `docs/`.
- FastAPI, SQLAlchemy, Alembic y SQLite.
- React, TypeScript y Vite.
- Docker Compose con backend, frontend y servicios auxiliares mínimos.
- Configuración tipada y `.env.example`.
- Health checks, logging estructurado y manejo de errores.
- Migración inicial del modelo canónico aprobado.
- API mínima para catálogo, documentos, registros y bloques.
- Pantalla técnica de inspección de un registro importado, todavía no la UX final.
- pytest, Vitest, lint, typecheck y CI.

### Puerta de salida

- `docker compose up` levanta el sistema desde cero.
- Migraciones aplican y revierten en una base vacía.
- El fixture de omeprazol se consulta por API conservando bloques repetibles.
- CI ejecuta pruebas, lint y tipos.
- No existen dependencias de red para arrancar con datos de ejemplo.

## 6. Fase 2 — Ingesta CIMA, muestreo y versionado documental

### Objetivo

Crear una capa robusta y reproducible para descargar, cachear, versionar y segmentar fichas técnicas.

### Trabajos

- Verificar la API contra la documentación oficial antes de codificar endpoints.
- Cliente con límite de ritmo, reintentos exponenciales, timeouts e idempotencia.
- Almacenar respuestas originales y metadatos estructurados.
- Muestreo reproducible aleatorio y estratificado con semilla.
- Informe de composición por ATC, forma y vía.
- Versiones inmutables de ficha y secciones.
- Hash de contenido y detección de cambios.
- Relación explícita entre `nregistro` y presentaciones/CN.
- Fixtures offline para pruebas.

### Puerta de salida

- Misma semilla y criterios producen la misma muestra.
- Las descargas repetidas usan caché cuando no existe cambio.
- Una nueva versión no sobrescribe la anterior.
- Cada sección puede reconstruirse exactamente.
- El informe de composición se genera automáticamente.
- El sistema sigue funcionando offline con el corpus descargado.

## 7. Fase 3 — Importación y consolidación de maestros

### Objetivo

Combinar la línea base existente con CIMA y preparar registros revisables sin perder procedencia.

### Trabajos

- Importadores idempotentes por fichero y hoja.
- Registro de lote, versión de fichero, hash y diagnósticos.
- Mapeo a entidades, bloques, ocurrencias y campos canónicos.
- Integridad referencial y cuarentena de filas huérfanas.
- Detección de conflictos entre fuentes.
- Matriz de prioridad configurable por campo.
- Informes de longitudes, tipos, nulos, duplicados y valores especiales.
- Estrategia específica para bloques vacíos en los maestros generales.

### Puerta de salida

- Todos los ficheros proporcionados se perfilan y se importan o se excluyen por una decisión documentada.
- Cada valor conoce su procedencia y lote.
- Los 184 posibles huérfanos de excipientes quedan reproducidos y clasificados.
- La segunda ejecución del mismo lote no duplica datos.
- No se normaliza ni corrige un valor sin una regla registrada.

## 8. Fase 4 — Extractor local y evaluación

### Objetivo

Integrar un extractor local sustituible, medirlo sobre el conjunto oro y decidir por campo qué política es segura.

### Prerrequisitos

- Hardware GPU confirmado.
- Conjunto oro definido y anotado.
- Modelo de procedencia y versiones estable.

### Trabajos

- Interfaz `ExtractorLLM` desacoplada.
- Servidor local compatible con OpenAI chat.
- Salida guiada por esquema.
- Llamadas agrupadas por sección.
- Verificación literal de evidencia antes de persistir.
- Reanudación de lotes, control de versiones de prompt/modelo y observabilidad.
- Comparación de al menos dos tamaños de modelo.
- Métricas por campo, política, entidad y sección: precisión, cobertura, evidencia válida, falsos positivos, falsos negativos y tasa de corrección.
- Degradación configurable a `solo_evidencia`.

### Puerta de salida

- Cero propuestas persistidas con evidencia literal inválida.
- Resultados publicados sobre las 20 fichas oro.
- Cada campo tiene política justificada por resultados o por restricción funcional.
- Los fallos del extractor no bloquean la revisión manual con evidencia.
- El corpus se procesa de forma reanudable.

> **Estado al 4 de septiembre de 2026: Gate 4 BLOCKED.** Revisión criterio por
> criterio en `docs/PHASE_4_GATE_REVIEW.md`. Todo el trabajo técnicamente
> ejecutable está terminado; los bloqueos restantes son decisiones humanas:
> GOLD-002 (los dos farmacéuticos anotadores) y D-014 (modelo de inferencia),
> más la campaña de anotación que depende de la primera.

## 9. Fase 5 — Pantalla de revisión y piloto de ahorro

### Objetivo

Construir el flujo que reduce segundos por campo y medir su valor real.

### Trabajos

- Selector de usuario y lista configurable.
- Cola de trabajo, lotes y prevención de colisiones.
- Pantalla de tres zonas con evidencia contextual.
- Navegación completa por teclado.
- Guardado incremental por campo.
- Estados diferenciados: pendiente, confirmado, corregido, no consta, descartado y los que apruebe el modelo.
- Edición de bloques repetibles: crear, eliminar, ordenar, fusionar y marcar no aplicable.
- Medición de tiempo descontando inactividad.
- Precarga del siguiente campo y objetivo menor de 100 ms.
- Tests automáticos de políticas de pre-relleno.
- Pruebas de usabilidad con farmacéuticos.

### Puerta de salida

- Un registro completo se valida sin ratón.
- Ningún campo protegido aparece preseleccionado.
- Cerrar o recargar la pestaña no pierde trabajo confirmado.
- Los bloques repetibles se revisan sin ambigüedad.
- Cambio de campo inferior a 100 ms en el entorno del piloto.
- Se ejecuta el conjunto de medida de 50 fichas y se publica el ahorro real.

## 10. Fase 6 — Exportación, riesgo, doble validación y auditoría

### Objetivo

Producir ficheros aceptables por el sistema destino y demostrar la trazabilidad completa.

### Prerrequisitos

- Contrato de exportación confirmado con proveedor.
- Separador decimal confirmado.
- Lista ATC de riesgo aprobada para el piloto.

### Trabajos

- Exportación por bloque a CSV, TXT y XLSX.
- Orden y nombres exactos de columnas.
- Validación de tipos, longitud, obligatoriedad y catálogos.
- Informe de exclusiones y errores.
- Exportaciones archivadas y reproducibles.
- Reglas ATC configurables por prefijo.
- Segunda validación a ciegas por usuario distinto.
- Conciliación de discrepancias.
- Auditoría append-only y consulta histórica.
- Prueba de carga en entorno del proveedor.

### Puerta de salida

- El omeprazol exportado conserva semánticamente todos los bloques.
- El proveedor acepta un lote de prueba.
- Ningún registro incompleto o con discrepancias abiertas se exporta.
- La auditoría reconstruye quién, qué, cuándo, procedencia y versión documental.
- Cualquier exceso de longitud falla de forma legible.

## 11. Fase 7 — Mantenimiento continuo

### Objetivo

Evitar que el catálogo quede obsoleto después de la carga inicial.

### Trabajos

- Consulta programada de cambios CIMA.
- Nuevas versiones y diff por sección.
- Marcado selectivo de revisión pendiente.
- Panel de novedades.
- Revalidación sin borrar decisiones anteriores.
- Alertas operativas y reintentos.
- Chat contextual opcional, solo lectura y siempre citado.

### Puerta de salida

- Un cambio simulado crea nueva versión, diff y tareas de revisión.
- Las validaciones históricas permanecen consultables.
- El fallo de una tarea programada es visible y recuperable.

## 12. Fase 8 — Decisión de escalado

### Objetivo

Decidir con datos si se amplía al catálogo completo y qué cambios de infraestructura son necesarios.

### Entradas

- Ahorro medido.
- Tasa de corrección de propuestas.
- Cobertura por campo.
- Discrepancias de doble validación.
- Coste operativo del modelo local.
- Incidencias de importación/exportación.
- Rendimiento y concurrencia.

### Decisiones posibles

- Continuar con SQLite o migrar a PostgreSQL.
- Mantener o ampliar modelos locales.
- Incorporar autenticación real.
- Ampliar reglas de riesgo.
- Incluir interacciones en un subproyecto.
- Escalar a todo el catálogo o limitar el alcance.

## 13. Secuencia inicial de trabajo con Codex

1. Ejecutar la Fase 0A.
2. Abrir las incidencias D-001 a D-010 del registro de decisiones.
3. Encargar a los agentes de dominio y datos un perfilado independiente.
4. Aprobar o corregir los ADR propuestos.
5. Implementar el perfilador y el round-trip de omeprazol.
6. No crear todavía la aplicación visual final.

## 14. Estrategia de ramas y worktrees

- `main`: siempre demostrable y protegida.
- Una rama por issue: `feat/`, `fix/`, `docs/`, `spike/`.
- Usar worktrees para tareas independientes.
- Un único escritor por worktree.
- Subagentes de revisión trabajan en modo lectura.
- Toda PR incluye requisito, ADR afectado, pruebas, migración y riesgo residual.
