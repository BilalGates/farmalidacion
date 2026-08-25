# DEV-011 — Tabla de validación de estados de valor

Esta tabla prepara la validación humana de D-010. Separa observación de fuente, estado de trabajo y decisión profesional. No define enums físicos ni serialización del proveedor. ADR-0004 continúa propuesto.

| Concepto | Plano | Significado | Actor | Exportación conocida |
|---|---|---|---|---|
| `source_absent` | observación | no existe celda, atributo o fragmento | importador con procedencia | no autoriza exportación |
| `source_blank` | observación | existe la posición, pero está vacía; conserva variante literal | importador con procedencia | no autoriza exportación |
| `pending` | trabajo | falta decisión o validación | flujo | prohibida por especificación 12.2 |
| `no_consta` | decisión | una persona revisó la fuente aplicable y el dato no aparece | usuario identificado | elegible; representación pendiente del proveedor |
| `not_applicable` | decisión | una persona confirma que no aplica mediante regla aprobada | usuario autorizado | pendiente del proveedor |
| `valued` | contenido | existe valor; su validación se registra aparte | fuente o usuario | solo confirmado/corregido son elegibles |

`confirmado`, `corregido`, `descartado` y `revision_pendiente` son estados de validación o flujo. `S`, `N`, `S*` y `N*` son literales de obligatoriedad gobernados por D-005 y no se convierten en estos estados.

## Reglas respaldadas

1. Ausencia o vacío nunca se convierten automáticamente en `no_consta` o `not_applicable`.
2. `no_consta` exige revisión humana y es distinto de vacío y `pending`.
3. `pending` no se exporta.
4. Todo original conserva literal, tipo, presencia y procedencia.
5. Ningún estado elimina ocurrencias repetibles ni sobrescribe la observación.

## Transiciones candidatas

| Desde | Hacia | Condición propuesta | Estado |
|---|---|---|---|
| observación | `pending` | crear trabajo sin decisión final | detalle por validar |
| `pending` | `valued` confirmado/corregido | usuario aporta o valida valor con procedencia | parcialmente definida |
| `pending` | `no_consta` | usuario revisa todas las fuentes aplicables | fuentes pendientes de farmacia |
| `pending` | `not_applicable` | regla aceptada y usuario autorizado | pendiente de farmacia |
| resuelto | `revision_pendiente` | cambia versión fuente relevante | granularidad pendiente |
| resuelto | otro resuelto | conservar evento, actor, instante, motivo y anterior | comentario/doble validación pendientes |

## Validación necesaria

Farmacia debe confirmar fuentes mínimas para `no_consta`, reglas y actores de `not_applicable`, aplicación a bloques y transiciones con comentario o doble validación. El proveedor debe confirmar representación exacta, diferencia entre omisión/vacío/sentinela y estados admitidos.

Hasta obtener esas respuestas no se aceptará ADR-0004 ni se implementarán reglas definitivas.
