# ADR-0005 — Identidad y claves candidatas de bloques

- Estado: propuesto
- Fecha: 2026-08-25
- Decisiones relacionadas: D-004
- Responsables: producto, farmacia, proveedor y tecnología

## Contexto

Los maestros incluyen identificadores externos, identificadores internos mayoritariamente vacíos y bloques repetibles. DEV-004 evaluó 35 hipótesis y 12 relaciones de forma agregada y reproducible. La unicidad en una versión no demuestra estabilidad ni identidad de negocio.

## Restricciones

- Conservar duplicados y ocurrencias repetidas.
- No usar una hoja vacía como prueba de unicidad.
- No convertir máximos observados en límites normativos.
- Mantener identificador, sistema emisor, versión y procedencia.
- No cerrar la relación `nregistro`/CN/D-006 dentro de este ADR.

## Opciones consideradas

### Opción A — Usar siempre un identificador externo simple como clave natural

Es directa, pero falla cuando el identificador está repetido, vacío, cambia entre versiones o solo es único dentro del lote.

### Opción B — Construir claves compuestas con todos los identificadores disponibles

Reduce colisiones observadas, pero incorpora columnas vacías o redundantes y confunde una clave de importación con identidad de negocio.

### Opción C — Identidad canónica propia y claves de fuente versionadas

Asignar identidad canónica independiente. Registrar cada clave observada con sistema emisor, versión, ámbito y estado; usar combinaciones de bloque solo como reglas candidatas hasta demostrar estabilidad y aprobarlas.

## Decisión propuesta

Adoptar la opción C. Para ingesta se pueden usar `IDEXTERNO`, `MED_IDEXTERNO`, `BN_IDEXTERNO`, `CODIGO_NACIONAL` y `LI_IDEXTERNO` como identificadores de fuente observados, nunca como identidad canónica universal sin validación adicional.

## Consecuencias

### Positivas

- Evita fusionar registros por una clave cómoda pero no demostrada.
- Permite conservar cambios y conflictos entre versiones.
- Mantiene las ocurrencias repetibles aunque compartan valores.

### Negativas

- La conciliación requiere reglas y revisión adicionales.
- No permite todavía restricciones definitivas de base de datos.

### Riesgos

- Crear duplicados canónicos si la conciliación futura no identifica equivalencias.
- Tratar la unicidad de una sola versión como estabilidad histórica.

## Validación

- Contrastar las candidatas con otra versión o confirmación del proveedor.
- Ejecutar importación y round-trip de omeprazol conservando multiplicidades.
- Confirmar reglas de reutilización, vigencia y bajas.
- Resolver D-006 separadamente.

## Migración y reversibilidad

No se crea migración en DEV-004. El modelo propuesto es reversible porque conserva claves originales y no impone todavía restricciones canónicas.

## Preguntas pendientes

- Qué identificadores garantiza el proveedor y con qué ámbito temporal.
- Qué combinaciones distinguen ocurrencias cuando el identificador del bloque está ausente.
- Si CN puede reutilizarse o cambiar en el histórico.
- Cómo conciliar claves de distintas fuentes sin fusión silenciosa.
