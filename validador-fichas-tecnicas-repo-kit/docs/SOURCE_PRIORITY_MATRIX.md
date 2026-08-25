# Matriz contractual de fuentes por campo — DEV-006

## Estado y alcance

- Estado: aceptado
- Decisión asociada: D-008 / ADR-0007
- Entrada gobernada: las 353 filas numeradas de `Catalogo_campos_clinicos_medicamentos.xlsx`
- No incluye: integración CIMA, importadores, resolución automática de conflictos ni exportación

La matriz efectiva es la unión reproducible de cada fila del catálogo con la regla correspondiente a su clasificación literal `¿Desde la FT?`. No se copia ni modifica el Excel original. Cada campo queda identificado por `(Nº, Entidad, Bloque origen, Campo)`; el nombre técnico aislado no es clave suficiente.

## Cobertura verificada

| Clasificación observada | Campos | Estado de fuente |
|---|---:|---|
| `No` | 204 | ficha técnica excluida; maestro como línea base; otras fuentes pendientes de mapeo |
| `Sí — directo` | 53 | maestro como línea base; ficha técnica candidata con evidencia literal |
| `Parcial` | 79 | maestro como línea base; ficha técnica solo aporta evidencia parcial |
| `Sí — interpretación` | 17 | maestro como línea base; ficha técnica solo evidencia; decisión farmacéutica obligatoria |
| **Total** | **353** | **353/353 con regla o pendiente explícito** |

Las etiquetas se interpretan según el catálogo, conservando siempre el literal original en la futura importación. `S`, `N`, `S*` y `N*` tampoco se reinterpretan: D-005 continúa pendiente.

## Columnas contractuales de la matriz

| Columna | Contenido |
|---|---|
| `field_identity` | ordinal + entidad + bloque + campo literal |
| `baseline_source` | maestro actual y su versión/hash, por ADR-0002 |
| `candidate_sources` | CIMA estructurado, ficha técnica, decisión humana, transformación autorizada u otra fuente; solo las respaldadas para la categoría |
| `authoritative_priority` | regla aceptada por campo o `pending_human_validation` |
| `conflict_policy` | acción explícita cuando dos fuentes difieren |
| `human_action` | validar, decidir, conciliar, solicitar al proveedor o mantener pendiente |
| `prefill_limit` | `direct_literal_candidate`, `evidence_only` o `not_from_ft`; nunca implica aceptación automática |
| `provenance_required` | fuente, versión, localizador, valor literal y regla/actor si existe derivación |
| `decision_reference` | ADR o decisión que autoriza prioridad o transformación |

## Reglas por clasificación

| Clasificación | Línea base | Fuentes candidatas adicionales | Prioridad autoritativa | Conflicto | Acción humana |
|---|---|---|---|---|---|
| `No` | maestro actual | CIMA estructurado u otra fuente solo con mapeo verificado | `pending_human_validation` | conservar ambas afirmaciones; no reemplazar | validar regla de fuente o solicitar definición |
| `Sí — directo` | maestro actual | ficha técnica versionada con cita literal; CIMA si el atributo se verifica | `pending_human_validation` | mostrar valores, versiones y evidencia | elegir/conciliar; una propuesta FT nunca se confirma sola |
| `Parcial` | maestro actual | ficha técnica como evidencia parcial; CIMA verificado | `pending_human_validation` | prohibido completar, calcular o inferir | decisión farmacéutica con evidencia visible |
| `Sí — interpretación` | maestro actual | ficha técnica como `solo_evidencia` | decisión farmacéutica | nunca preseleccionar ni convertir evidencia en valor | introducir decisión explícita y auditada |

## Reglas de conflicto

1. Ninguna fuente sobrescribe otra: se conservan afirmaciones separadas con procedencia.
2. La línea base no significa verdad autoritativa; identifica el valor inicial de los maestros aceptados.
3. Una prioridad solo se aplica si referencia una decisión aceptada para ese campo o grupo inequívoco.
4. Si falta regla, el campo queda `pending_human_validation` y no se exporta como resuelto por automatismo.
5. Coincidencia de valores no fusiona procedencias ni elimina la necesidad de registrar ambas fuentes.
6. Las transformaciones requieren regla versionada, entradas y resultado; no se normaliza implícitamente.
7. Para campos parciales o interpretables, la ficha técnica no puede producir un valor consolidado automático.

## CIMA y ficha técnica

`CIMA estructurado` y `ficha técnica` son fuentes distintas aunque compartan `nregistro`. La disponibilidad exacta de cada atributo CIMA no se ha verificado en DEV-006; por ello CIMA permanece candidata y condicionada a un mapeo explícito. DEV-006 no llama a la API ni presupone su contrato.

## Criterio de aceptación documental

- 353 ordinales únicos, del 1 al 353.
- Cero filas sin entidad, bloque, campo, tipo, obligatoriedad o clasificación FT.
- 353/353 asignadas a una regla de categoría.
- 353/353 con prioridad aceptada o `pending_human_validation`; en esta versión ninguna prioridad de campo se acepta automáticamente.
- Cero normalizaciones, preselecciones o sustituciones silenciosas.

## Pendientes de aplicación y validación específica

- Validación humana de la regla por categoría y de sus excepciones por campo.
- Inventario verificado de atributos CIMA estructurados.
- Confirmación de fuentes externas y autoridad del proveedor.
- Significado de `S*` y `N*` (D-005).
- Regla de exportación ante conflicto o campo pendiente, que pertenece a Fase 6.

## Evidencia de aceptación

Aprobación humana del 25 de agosto de 2026. D-008 queda cerrada para la política contractual. Las filas con `pending_human_validation` conservan ese estado hasta que una decisión específica asigne prioridad; la aceptación no las rellena automáticamente.
