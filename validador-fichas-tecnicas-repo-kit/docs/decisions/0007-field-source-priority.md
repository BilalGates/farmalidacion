# ADR-0007 — Prioridad de fuentes por campo

- Estado: aceptado
- Fecha: 2026-08-25
- Decisiones relacionadas: D-008
- Responsables: producto, farmacia, proveedor y tecnología

## Contexto

Los 353 campos pueden recibir afirmaciones de maestros, CIMA estructurado, ficha técnica, decisiones farmacéuticas y transformaciones autorizadas. ADR-0002 acepta los maestros como línea base, pero aclara que no son verdad absoluta. El catálogo clasifica la utilidad de la ficha técnica como `No`, directa, parcial o de interpretación.

## Restricciones

- Conservar cada afirmación y su procedencia.
- No confundir línea base con autoridad.
- No completar valores parciales ni interpretables mediante inferencia.
- No preseleccionar campos protegidos.
- No usar CIMA como fuente de un atributo hasta verificar el mapeo.
- Mantener D-005 y el contrato de exportación fuera de esta decisión.

## Opciones consideradas

### Opción A — Maestro siempre prioritario

Produce una salida completa rápidamente, pero ocultaría obsolescencia, conflictos y evidencia más reciente.

### Opción B — CIMA o ficha técnica siempre prioritarios

Parece más oficial, pero no cubre todos los campos y convertiría texto parcial o interpretativo en autoridad indebida.

### Opción C — Línea base más prioridad configurable y conflicto visible

Mantener el maestro como valor base, registrar fuentes adicionales como afirmaciones y aplicar una prioridad únicamente cuando exista una regla aceptada por campo. Si falta, conservar el conflicto y exigir acción humana.

## Decisión propuesta

Adoptar la opción C y el contrato de `docs/SOURCE_PRIORITY_MATRIX.md`. La clasificación FT determina límites de automatización, no una precedencia universal. Hasta validar campo por campo, `authoritative_priority` permanece `pending_human_validation` salvo decisiones ya aceptadas explícitamente.

## Evidencia de aceptación

Aprobación humana explícita del 25 de agosto de 2026. Se aceptan la línea base con procedencia, la prioridad configurable, el conflicto visible, la acción humana cuando falta regla y los límites por clasificación FT. Esta aceptación no asigna prioridades concretas pendientes, no valida atributos CIMA y no resuelve D-005 ni D-010.

## Consecuencias

### Positivas

- Cobertura explícita de 353/353 campos sin inventar prioridades.
- Conflictos visibles y trazables.
- CIMA puede añadirse después sin sobrescribir la línea base.

### Negativas

- Requiere validación humana y configuración antes de consolidar automáticamente.
- Algunos campos permanecerán pendientes aunque exista un valor de maestro.

### Riesgos

- Interpretar `baseline_source` como fuente autoritativa.
- Crear excepciones demasiado amplias por prefijo o bloque.
- Ocultar conflictos porque los textos parezcan iguales tras una normalización no autorizada.

## Validación

- Revisar las cuatro categorías y una muestra por entidad con farmacia y proveedor.
- Verificar disponibilidad CIMA antes de asignarla a campos.
- Ejecutar omeprazol conservando afirmaciones y conflictos.
- Demostrar que un campo sin prioridad queda pendiente y no se resuelve silenciosamente.

## Migración y reversibilidad

No se crea esquema ni migración. La propuesta es reversible porque la prioridad es metadato versionado y ninguna afirmación fuente se elimina.

## Preguntas pendientes

- Prioridad y excepciones exactas por campo.
- Autoridad de otros maestros externos.
- Tratamiento operativo y de exportación de conflictos no resueltos.
