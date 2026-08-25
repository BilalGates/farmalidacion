# ADR-0002 — Usar los maestros existentes como línea base híbrida

- Estado: aceptado
- Fecha: 2026-08-24
- Decisiones relacionadas: D-007, D-008
- Responsables: producto, farmacia y tecnología

## Contexto

Los campos que no aparecen en la ficha técnica deben venir de otras fuentes. Los Excel aportados ya contienen claves, relaciones y valores que no pueden reconstruirse de forma fiable desde 500 fichas CIMA. Tratarlos solo como ejemplos dejaría incompleta la carga; tratarlos como verdad absoluta impediría detectar errores y cambios.

## Opciones consideradas

### Opción A — Empezar vacío

Reduce importación inicial, pero obliga a reconstruir datos existentes y hace imposible una salida completa.

### Opción B — Importar y aceptar todo como definitivo

Rápida, pero oculta conflictos, problemas de integridad y procedencia.

### Opción C — Línea base híbrida con procedencia y conciliación

Importar los maestros como una versión de fuente, conservar valores originales, añadir CIMA y ficha técnica, detectar conflictos y exigir decisión solo donde corresponda.

## Decisión propuesta

Adoptar la opción C. Cada valor importado conserva fichero, hoja, fila/lote, hash y estado. Las prioridades se configuran por campo y los conflictos nunca se resuelven silenciosamente.

## Evidencia de aceptación

Decisión humana explícita del 24 de agosto de 2026: los maestros actuales son la línea base y deben conservar procedencia; CIMA estructurado, la ficha técnica y las decisiones farmacéuticas se consolidan como fuentes adicionales. Esta aceptación no cierra D-008 ni define prioridades por campo.

## Consecuencias

- Se necesita infraestructura común de lotes e importadores.
- El sistema puede producir ficheros completos y auditables.
- El trabajo humano se concentra en diferencias y campos clínicos.

## Validación

- Importación idempotente de todos los ficheros incluidos en alcance.
- Informe de conflictos.
- Reproducción de huérfanos y duplicados.
- Round-trip de omeprazol.

## Preguntas pendientes

- Prioridad de cada fuente por campo.
- Tratamiento de valores obsoletos y bajas.
- Campos que el proveedor exige aunque no estén validados clínicamente.
