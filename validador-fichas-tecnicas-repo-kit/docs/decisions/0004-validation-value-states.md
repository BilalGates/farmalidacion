# ADR-0004 — Semántica de vacío, pendiente, no consta y no aplica

- Estado: propuesto
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

## Decisión propuesta

Evaluar la opción C. Como vocabulario candidato, sin aprobación todavía:

- `source_absent`: no existe celda/atributo en la fuente;
- `source_blank`: existe pero está vacío, conservando la variante observada;
- `pending`: requiere revisión y aún no existe decisión;
- `no_consta`: una persona revisó la fuente aplicable y confirmó que el dato no consta;
- `not_applicable`: una persona confirmó que el campo/bloque no aplica bajo una regla aprobada;
- `valued`: existe un valor, con su estado de validación separado.

Los nombres, transiciones, actor autorizado, obligatoriedad de comentario y representación de exportación siguen pendientes. Nada en este ADR autoriza mapear automáticamente un vacío a otro estado.

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

## Preguntas pendientes

- ¿Qué fuentes debe revisar una persona antes de declarar `no_consta`?
- ¿Quién puede declarar `no_aplica` y bajo qué regla por campo o bloque?
- ¿Puede un bloque completo ser no aplicable y cómo se conservan ocurrencias previas?
- ¿Qué estados admite exactamente el proveedor y cómo se exporta cada uno?
- ¿Qué transiciones requieren comentario o doble validación?

## Evidencia DEV-011

`docs/VALUE_STATE_VALIDATION_TABLE.md` separa observación, trabajo y decisión. La especificación respalda `no_consta` como decisión distinta de vacío y pendiente, y excluye `pending` de exportación. `not_applicable`, fuentes mínimas, transiciones y serialización siguen sin evidencia suficiente. El ADR permanece **propuesto** y DEV-011 requiere validación de farmacia y proveedor.
