# Contrato interno de estados de validación

- Issue: DEV-506
- Fase prevista: 5
- Estado: núcleo preparatorio implementado; Fase 5 no abierta
- Módulo: pharma_validator_api.validation_states
- Base: ADR-0004 y tabla DEV-011

## Alcance

El módulo valida decisiones y transiciones internas. No persiste, no audita, no serializa para el proveedor y no determina qué representación externa corresponde a no_consta o no_aplica.

## Estados internos

- pendiente: todavía no existe decisión.
- confirmado y corregido: decisión con valor final.
- no_consta: el farmacéutico revisó todas las fuentes obligatorias configuradas y el dato no aparece.
- no_aplica: el farmacéutico decide que el campo no corresponde semánticamente al medicamento.
- descartado: estado distinto de no_aplica.
- revision_pendiente: una decisión previa debe revisarse contra otra versión.

no_consta y no_aplica son resoluciones internas explícitas. Esto no implica que el proveedor acepte NULL, vacío, omisión, sentinela o código alguno. PROVIDER-002/D-011 sigue bloqueando esa traducción.

## Autoridad y fuentes

Cada decisión transporta fuentes aplicables, obligatorias y revisadas. Las fuentes obligatorias y revisadas deben pertenecer a las aplicables y no pueden duplicarse.

no_consta solo se admite cuando todas las fuentes obligatorias están revisadas. No existe una combinación global maestro+CIMA+FT. no_consta y no_aplica solo pueden decidirlos revisores con rol farmacéutico.

## Comentarios y transiciones

- no_aplica siempre exige comentario.
- no_consta exige comentario cuando el campo es obligatorio.
- revertir no_consta o no_aplica exige comentario.
- salir de revision_pendiente exige comentario.
- una decisión resuelta no vuelve a pendiente; se registra otra decisión conservando la anterior.

La doble validación depende exclusivamente de las reglas ATC. El módulo recibe los campos con doble validación pendiente y los retiene al evaluar si la revisión interna está completa; no decide riesgo ni concilia revisores.

## Verificación

Quince pruebas cubren valores, fuentes aplicables/obligatorias/revisadas, autoridad farmacéutica, comentarios condicionados, no_aplica, reversión, cambio de versión y doble validación pendiente. Ruff y mypy pasan.

## Límites

- No existe persistencia, auditoría ni interfaz.
- No se exportan ni serializan estados.
- No se implementan reglas ATC ni conciliación.
- Fase 5 y DEV-506 no se consideran formalmente cerrados hasta superar Gate 4 y completar el issue en su fase.
