# ADR-0004 — Semántica de vacío, pendiente, no consta y no aplica

- Estado: aceptado para el modelo interno; serialización externa pendiente en D-011
- Fecha: 2026-08-24
- Decisiones relacionadas: D-010
- Responsables: producto, farmacia, tecnología y proveedor

## Contexto

Los Excel pueden contener ausencia de celda, celda vacía, cadena vacía, espacios, fórmulas sin resultado y valores explícitos. La especificación define `no_consta` como “revisado en la ficha técnica y no encontrado”, distinto de vacío y pendiente, pero no cierra `no_aplica` ni la representación exacta de cada estado en importación, validación y exportación.

Confundir estos estados puede inventar una decisión farmacéutica, ocultar trabajo pendiente o perder un valor original. El contrato de perfilado debe observarlos sin interpretarlos y el round-trip no puede normalizarlos implícitamente.

## Restricciones

- Preservar siempre presencia, valor y tipo originales con procedencia.
- No convertir vacíos en decisiones de validación.
- Solo una persona identificada puede declarar estados que requieran revisión.
- No exportar trabajo pendiente ni inventar la representación del sistema destino.
- No implementar el esquema definitivo hasta aceptar esta decisión.

## Opciones consideradas

### Opción A — Un único nulo técnico

Simplifica almacenamiento, pero pierde la diferencia entre ausencia de fuente, revisión pendiente, dato no encontrado y no aplicable. No permite un round-trip fiable.

### Opción B — Texto/sentinelas en el propio valor

Conserva etiquetas visibles, pero mezcla dato y estado, puede colisionar con valores literales y depende del contrato de exportación aún pendiente.

### Opción C — Estado explícito separado del valor y de la observación de origen

Mantiene por separado el valor observado, su presencia/tipo, el estado de trabajo y una eventual decisión humana, con reglas de exportación configurables. Es la recomendación provisional.

## Decisión aceptada

Adoptar la opción C para el modelo interno:

- `source_absent`: no existe celda/atributo en la fuente;
- `source_blank`: existe pero está vacío, conservando la variante observada;
- `pending`: requiere revisión y aún no existe decisión;
- `no_consta`: una persona revisó la fuente aplicable y confirmó que el dato no consta;
- `not_applicable`: una persona confirmó que el campo/bloque no aplica bajo una regla aprobada;
- `valued`: existe un valor, con su estado de validación separado.

Cada campo configura fuentes aplicables y obligatorias. `no_consta` solo se confirma tras revisar todas sus fuentes obligatorias. `not_applicable` solo puede declararlo un farmacéutico, nunca CIMA, heurísticas o LLM; exige motivo y auditoría.

Un bloque completo puede declararse `not_applicable` sin alterar ocurrencias originales. El cambio es lógico, reversible y auditado.

Comentario obligatorio para `not_applicable`, sobrescritura de fuente prioritaria, conflicto entre fuentes, conciliación de doble validación, reversión de `no_consta`/`not_applicable` confirmado y `no_consta` en campo obligatorio. La doble validación depende exclusivamente de riesgo ATC e incluye estos estados cuando aplique.

La representación externa permanece abierta bajo D-011: no se infiere vacío, `NULL`, omisión, sentinela ni código.

## Consecuencias

### Positivas

- Evita pérdida semántica y decisiones implícitas.
- Permite auditar observación, trabajo y decisión por separado.
- Hace configurables las reglas de exportación futuras.

### Negativas

- Aumenta estados y combinaciones que deben validarse.
- Exige reglas por campo/bloque y pruebas de transición/exportación.

### Riesgos

- Crear estados solapados o imposibles de explicar al usuario.
- Exportar sentinelas no aceptados por el proveedor.
- Aplicar `no_aplica` a un bloque completo sin preservar sus ocurrencias de origen.

## Validación

- Perfilar los siete Excel preservando todas las variantes observadas.
- Inventariar ejemplos reales por estado candidato y campo/bloque.
- Ejecutar el round-trip de omeprazol sin sustituciones implícitas.
- Obtener validación de farmacia para significado y transiciones.
- Obtener del proveedor la representación exacta de exportación.
- Probar una tabla de decisión que cubra valor presente, vacío, ausencia, pendiente, `no_consta` y `no_aplica`.

## Migración y reversibilidad

No hay migración en esta fase. El modelo candidato debe mantener el valor y estado originales para permitir renombrar o dividir estados sin pérdida. No crear enums ni columnas definitivas hasta aceptar el ADR.

## Pregunta pendiente fuera del alcance interno

- ¿Qué estados admite exactamente el proveedor y cómo se exporta cada uno?

## Evidencia DEV-011

`docs/VALUE_STATE_VALIDATION_TABLE.md` incorpora la aprobación humana del 25 de agosto de 2026. Semántica interna, autoridad, comentarios, reversibilidad y doble validación quedan aceptadas. Solo la serialización del proveedor permanece pendiente bajo D-011.
