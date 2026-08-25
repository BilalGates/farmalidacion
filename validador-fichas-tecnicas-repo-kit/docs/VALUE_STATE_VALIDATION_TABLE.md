# DEV-011 — Tabla de validación de estados de valor

Esta tabla recoge la validación humana de D-010 para el modelo interno. No define enums físicos ni serialización del proveedor. ADR-0004 está aceptado en ese alcance; D-011 permanece pendiente.

| Concepto | Plano | Significado | Actor | Exportación conocida |
|---|---|---|---|---|
| `source_absent` | observación | no existe celda, atributo o fragmento | importador con procedencia | no autoriza exportación |
| `source_blank` | observación | existe la posición, pero está vacía; conserva variante literal | importador con procedencia | no autoriza exportación |
| `pending` | trabajo | falta decisión o validación | flujo | prohibida por especificación 12.2 |
| `no_consta` | decisión | revisadas todas las fuentes obligatorias configuradas y el dato no aparece | farmacéutico identificado | elegible; representación pendiente del proveedor |
| `not_applicable` | decisión | el campo/bloque no corresponde semánticamente al medicamento | solo farmacéutico | pendiente del proveedor |
| `valued` | contenido | existe valor; su validación se registra aparte | fuente o usuario | solo confirmado/corregido son elegibles |

`confirmado`, `corregido`, `descartado` y `revision_pendiente` son estados de validación o flujo. `S`, `N`, `S*` y `N*` son literales de obligatoriedad gobernados por D-005 y no se convierten en estos estados.

## Reglas respaldadas

1. Ausencia o vacío nunca se convierten automáticamente en `no_consta` o `not_applicable`.
2. `no_consta` exige revisión humana y es distinto de vacío y `pending`.
3. `pending` no se exporta.
4. Todo original conserva literal, tipo, presencia y procedencia.
5. Ningún estado elimina ocurrencias repetibles ni sobrescribe la observación.

## Transiciones aceptadas internamente

| Desde | Hacia | Condición propuesta | Estado |
|---|---|---|---|
| observación | `pending` | crear trabajo sin decisión final | detalle por validar |
| `pending` | `valued` confirmado/corregido | usuario aporta o valida valor con procedencia | parcialmente definida |
| `pending` | `no_consta` | farmacéutico revisa todas las fuentes obligatorias | aceptada |
| `pending` | `not_applicable` | farmacéutico documenta motivo; nunca automática | aceptada |
| resuelto | `revision_pendiente` | cambia versión fuente relevante | granularidad pendiente |
| resuelto | otro resuelto | conservar evento, actor, instante, motivo y anterior | comentario/doble validación pendientes |

## Reglas de comentario, bloque y riesgo

Comentario obligatorio para `not_applicable`, sobrescritura de fuente prioritaria, conflicto, conciliación de doble validación, reversión de `no_consta`/`not_applicable` y `no_consta` en campo obligatorio. Un bloque puede marcarse `not_applicable` lógicamente sin alterar ocurrencias; es reversible y auditado.

La doble validación depende solo de riesgo ATC. Si aplica, `no_consta` y `not_applicable` requieren dos revisores independientes.

El proveedor debe confirmar la representación exacta. Hasta entonces no se implementará esa traducción ni se cerrará D-011.
