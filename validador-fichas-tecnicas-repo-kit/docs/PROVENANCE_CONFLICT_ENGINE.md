# Contrato del motor de conflictos de procedencia

## Alcance

DEV-307 implementa el mecanismo determinista aceptado por D-008 y ADR-0007 para comparar afirmaciones ya conciliadas sobre un campo exacto. El motor no descubre por sí mismo que dos filas u ocurrencias representan el mismo hecho, no asigna prioridades concretas y no persiste una consolidación.

No se modifica el modelo físico. La integración futura podrá almacenar reglas y resultados cuando existan decisiones de campo aceptadas, sin alterar este contrato semántico.

## Identidad y afirmaciones

Un campo se identifica por ordinal de catálogo, entidad, bloque y campo. El nombre técnico aislado no es suficiente. Cada afirmación requiere identificador único, valor literal, estado lógico, rol de procedencia, versión de fuente y localizador verificable.

Los roles admitidos son master_baseline, cima_structured, technical_sheet, pharmacist_decision, authorized_transformation y external_source. Esta enumeración clasifica procedencias; no establece precedencia universal.

## Semántica de igualdad y conflicto

La comparación es exacta sobre estado lógico y valor literal: no recorta espacios, cambia mayúsculas, convierte tipos o unidades, redondea ni normaliza. no_consta y no_aplica siguen siendo distintos aunque ambos carezcan de literal.

Dos fuentes con la misma afirmación exacta no generan conflicto, pero ambas afirmaciones y procedencias permanecen separadas. La coincidencia no selecciona una fuente autoritativa ni fusiona registros.

## Reglas de prioridad

Una regla pertenece a una identidad de campo exacta:

- pending_human_validation no contiene orden de fuentes ni referencia de decisión y nunca selecciona una afirmación;
- accepted requiere un orden de fuentes sin duplicados y una referencia de decisión humana aceptada.

Una regla de otro campo se rechaza. No existen comodines por nombre, prefijo o bloque. Una regla aceptada puede prohibir la resolución automática; en ese caso el resultado exige acción humana aunque exista un orden configurado.

## Estados de salida

| Estado | Significado |
|---|---|
| no_assertions | no hay afirmaciones que comparar |
| consistent_pending_priority | todas coinciden exactamente; se conservan sin elegir autoridad |
| unresolved_pending_priority | difieren y no existe prioridad aceptada |
| human_action_required | la regla aceptada prohíbe resolución automática |
| unresolved_no_applicable_source | ninguna afirmación procede de las fuentes de la regla |
| unresolved_authoritative_ambiguity | la fuente de mayor prioridad contiene afirmaciones contradictorias |
| resolved_by_accepted_priority | una decisión aceptada selecciona la afirmación de mayor prioridad aplicable |

Incluso al resolver por prioridad, la salida conserva todas las afirmaciones, identifica las seleccionadas y registra la referencia de decisión. No sobrescribe ni elimina valores fuente.

## Límites deliberados

- Las 353 prioridades actuales permanecen pending_human_validation; DEV-307 no acepta ninguna por inferencia.
- El motor recibe conjuntos de afirmaciones explícitos; reconciliar identidades y ocurrencias entre fuentes requiere evidencia y reglas propias.
- No se integra todavía CIMA/FT como fuentes de campos, no se crea UI y no se exporta ningún resultado.
- La política de exportación ante conflicto pertenece a Fase 6.
- DEV-307 no inicia DEV-308.

## Validación

Las pruebas cubren coincidencia sin fusión, espacios y mayúsculas sin normalizar, distinción no_consta/no_aplica, prioridad aceptada, acción humana obligatoria, fuente no aplicable, ambigüedad en la fuente prioritaria, identidad exacta, procedencia obligatoria e identificadores duplicados.
