# Límite de migración y conciliación de interacciones

## Decisión aplicada

DEV-306 aplica D-009 y ADR-0003, aceptado el 24 de agosto de 2026. `Interacciones-cargaMaster250626.xlsx` queda formalmente fuera de la secuencia de importación y consolidación del piloto de fichas técnicas de Fase 3. Permanece dentro del proyecto como una línea separada de migración y conciliación.

Esta exclusión es de alcance, no de datos: no se modifica, descarta, transforma ni sustituye el fichero; tampoco se afirma que sus filas sean prescindibles para la carga final.

## Evidencia reproducible disponible

- Fichero: `Interacciones-cargaMaster250626.xlsx`.
- SHA-256 inventariado y verificado: `f72d368f7590c1c41a886055f58b131305cb24c383cfa80f3028656fe351037f`.
- `General`: 436.148 filas de datos.
- `AplicaA`: 436.148 filas de datos.
- Relación observada `IDEXTERNO` → `IN_IDEXTERNO`: 436.148 filas hijas, cardinalidad observada 1..21 y cero huérfanos en esta versión.
- `IDEXTERNO` de `General` presenta 17.238 repeticiones respecto a las filas completas; no se acepta como clave canónica por comodidad técnica.
- DEV-002 estimó 17.440 duplicados de fila en `General` y 16.858 en `AplicaA`; son observaciones agregadas, no órdenes de deduplicación.
- DEV-009 reprodujo longitudes máximas de 31 para `Interacciones / IDEXTERNO` y 34 para `Interacciones - GP / IDEXTERNO`, frente a tipos declarados de longitud 20. No se trunca ningún literal.

Los recuentos describen únicamente la versión recibida. No demuestran estabilidad histórica, autoridad de claves ni reglas de alta, modificación o baja.

## Motivo de la exclusión del piloto

El maestro suma 872.296 filas de datos estructurados. No procede reconstruirlo desde el corpus de 500 fichas técnicas ni utilizar un LLM para generarlo. Importarlo ahora congelaría decisiones todavía abiertas sobre identidad, actualización, conciliación y entrega al proveedor, además de mezclar sus métricas con las del piloto de extracción.

No se crea un importador de interacciones en DEV-306, no se materializan las 436.148 relaciones `AplicaA` y no se modifica el modelo canónico.

## Condiciones para reabrir la migración

La línea separada deberá resolver y aprobar antes de una importación completa:

1. **INT-001 — Fuente y versionado:** identificar autoridad, proceso de actualización e instantánea/versionado.
2. **INT-002 — Identidad:** definir claves de interacción y de aplicación sin tratar duplicados como errores por defecto.
3. **INT-003 — Ciclo de vida:** acordar reglas de alta, modificación, baja y conciliación entre versiones.
4. **INT-004 — Importación acotada:** importar una muestra reproducible, verificar procedencia, cardinalidad, huérfanos, idempotencia y estimar recursos del flujo completo.
5. **INT-005 — Entrega:** confirmar con el proveedor si el maestro forma parte de la misma entrega y cuál es su contrato físico.

Ninguno de estos trabajos autoriza recomendaciones clínicas, generación LLM, normalización, truncamiento o deduplicación implícita.

## Efecto sobre gates y siguientes issues

- Gate 3 considera interacciones fuera de los ficheros en alcance del piloto por decisión aceptada y evidencia documentada.
- Gate 3 no se cierra con DEV-306: DEV-307 y DEV-308 continúan pendientes.
- DEV-306 no inicia DEV-307 ni la línea INT-001..005.
- La exclusión es reversible mediante un issue autorizado que cierre las condiciones anteriores; el original y toda la evidencia permanecen disponibles.
