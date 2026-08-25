# Evidencia de relaciones entre registros destino — DEV-005

## Conclusión

Los maestros sustentan una jerarquía de referencias entre principio activo, medicamento y especialidad/presentación, pero no contienen `nregistro`. La ficha técnica y su `nregistro` deben mantenerse como contexto regulatorio/documental separado y vincularse explícitamente a los registros destino cuando exista evidencia CIMA. No se admite una equivalencia automática `nregistro = CN = medicamento`.

## Conceptos y alcance

| Concepto | Definición candidata | Identificador observado | Lo que no se afirma |
|---|---|---|---|
| `nregistro` | identificador regulatorio bajo el que CIMA publica una ficha técnica y sus versiones | especificación v2; no aparece en los maestros | que sea CN, medicamento o especialidad |
| CN | código de una presentación/especialidad comercial | `CODIGO_NACIONAL`, único en 29.850 filas de esta versión | estabilidad histórica o equivalencia 1:1 con `nregistro` |
| especialidad/presentación | registro comercial que contiene CN y referencia un medicamento | `BN_IDEXTERNO`, `CODIGO_NACIONAL`, `ME_IDEXTERNO` | que sea la unidad única de todos los bloques clínicos |
| medicamento | nivel compartido al que se adjuntan composición, indicación, vía y enlaces | `MED_IDEXTERNO` | equivalencia con autorización CIMA |
| principio activo | componente referenciado desde ocurrencias de composición | `IDEXTERNO`, enlazado por `PA_IDEXTERNO` | que una descripción textual determine identidad |

## Evidencia agregada

| Relación | Dirección observada por fila | Cardinalidad observada inversa | Huérfanos |
|---|---|---:|---:|
| especialidad → medicamento | exactamente una referencia `ME_IDEXTERNO` completa por especialidad | medicamento → 1..643 especialidades | 0 |
| composición → principio activo | exactamente una referencia `PA_IDEXTERNO` completa por composición | principio activo → 0..83 composiciones | 0 |
| medicamento → composición | bloque repetible | 0..22 composiciones | 0 |
| `nregistro` → ficha técnica | una identidad documental lógica con versiones, según especificación | no cuantificada localmente | no evaluable |
| `nregistro` ↔ CN/presentación | la especificación anticipa varias presentaciones por registro | no reproducible sin CIMA estructurado | no evaluable |

Los máximos son observaciones de los ficheros recibidos, no límites normativos. Una referencia completa por fila no demuestra vigencia, estabilidad ni exclusividad histórica.

## Unidad de revisión propuesta

La unidad de trabajo no debe ser una fila CN ni una ficha aislada. Se propone un **expediente de revisión** que agrupa:

1. una versión exacta de la ficha técnica identificada por `nregistro`;
2. los registros destino vinculados con rol explícito: especialidades/presentaciones, medicamentos y principios activos;
3. bloques y ocurrencias atribuidos al nivel destino correspondiente;
4. procedencia y estado de validación por valor.

El farmacéutico revisaría el expediente con acceso a todos los destinos vinculados, pero cada decisión seguiría atribuida a un campo y ocurrencia concretos. Esto evita duplicar decisiones compartidas por CN y evita trasladar automáticamente un valor entre presentaciones.

## Reglas de vínculo propuestas

- Todo identificador conserva sistema emisor, versión de fuente y valor literal.
- Los vínculos declaran tipo, rol, fuente, vigencia conocida y estado de conciliación.
- CIMA puede aportar el vínculo `nregistro`→presentación/CN; los maestros aportan especialidad→medicamento y composición→principio activo.
- Varias fuentes pueden afirmar vínculos diferentes sin sobrescribirse.
- Un vínculo observado no fusiona identidades canónicas.
- Si falta evidencia, el vínculo permanece pendiente; no se deduce por nombre, descripción, ATC o semejanza.

## Decisiones aprobadas

- D-001: expediente contextual como unidad de revisión.
- D-002: separación documento/versión, registros destino y vínculos tipados.
- D-006: grafo propuesto, manteniendo pendiente la verificación factual de `nregistro`↔CN con CIMA estructurado.

Aprobación humana: 25 de agosto de 2026. Esta aprobación no acepta ADR-0001 ni autoriza integración CIMA.

## Evidencia que falta

- Muestra estructurada CIMA con `nregistro` y presentaciones/CN.
- Reglas del proveedor sobre estabilidad, altas, bajas y reutilización de CN.
- Casos reales de un `nregistro` con varias presentaciones y posibles presentaciones compartidas o históricas.
- Confirmación funcional de si una validación compartida a nivel medicamento debe heredarse, copiarse o mostrarse como referencia en especialidades.
