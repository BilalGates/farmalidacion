# ADR-0006 — Unidad de revisión y relaciones entre registros destino

- Estado: aceptado
- Fecha: 2026-08-25
- Decisiones relacionadas: D-001, D-002, D-006
- Responsables: producto, farmacia, proveedor y tecnología

## Contexto

Una ficha técnica se identifica por `nregistro`, mientras que los maestros separan principio activo, medicamento y especialidad/presentación. DEV-004 demuestra referencias especialidad→medicamento y composición→principio activo, pero los maestros no contienen `nregistro`. Revisar solo por CN duplicaría bloques compartidos; revisar solo por ficha no indica a qué destino pertenece cada valor.

## Restricciones

- No fusionar `nregistro`, CN, medicamento, especialidad y principio activo.
- Conservar procedencia y versiones exactas.
- Representar bloques repetibles por ocurrencias.
- No reutilizar una decisión entre destinos sin regla aceptada.
- No integrar todavía CIMA ni fijar esquema físico.

## Opciones consideradas

### Opción A — Una revisión por `nregistro`

Se ajusta a la ficha técnica, pero mezcla campos de varios niveles destino y puede ocultar diferencias entre presentaciones.

### Opción B — Una revisión independiente por CN

Es explícita para cada presentación, pero duplica trabajo y decisiones de medicamento o principio activo.

### Opción C — Expediente contextual con decisiones atribuidas por nivel

El expediente se ancla a una versión documental y reúne registros destino vinculados. Cada bloque, ocurrencia y decisión pertenece al nivel correspondiente y conserva su procedencia.

## Decisión propuesta

Adoptar la opción C. Mantener `nregistro` como identidad regulatoria/documental; CN como identificador de presentación; especialidad/presentación, medicamento y principio activo como registros destino distintos. Representar sus relaciones mediante vínculos tipados, versionados y con procedencia.

La cardinalidad `nregistro`↔CN queda deliberadamente abierta hasta contrastar CIMA estructurado. La propuesta no autoriza herencia automática de valores o decisiones.

## Evidencia de aceptación

Aprobación humana explícita del 25 de agosto de 2026. Se aceptan el expediente contextual, la separación de identidades, los vínculos con procedencia y vigencia y la prohibición de herencia automática. La aceptación conserva como verificación pendiente la cardinalidad factual `nregistro`↔CN y no acepta ADR-0001 ni autoriza integración CIMA.

## Consecuencias

### Positivas

- Evita duplicar innecesariamente la revisión de datos compartidos.
- Permite mostrar el contexto completo sin perder atribución.
- Admite uno-a-varios y cambios históricos sin sobrescritura.

### Negativas

- La interfaz y las consultas futuras deberán distinguir nivel, contexto y procedencia.
- Requiere conciliación explícita de vínculos entre fuentes.

### Riesgos

- Confundir el expediente de trabajo con un registro exportable.
- Propagar una decisión de medicamento a todas las especialidades sin autoridad.
- Fijar una cardinalidad CIMA a partir de ejemplos insuficientes.

## Validación

- Verificar una muestra CIMA con `nregistro` y CN.
- Representar un caso con varias presentaciones y varios principios activos.
- Ejecutar el round-trip de omeprazol sin duplicar ni perder ocurrencias.
- Obtener aceptación de producto y farmacia sobre la unidad de revisión.

## Migración y reversibilidad

No se crean migraciones. La propuesta es reversible porque mantiene separadas identidades, documentos y vínculos.

## Preguntas pendientes

- Cardinalidad y vigencia exactas entre `nregistro` y CN.
- Regla de visualización o reutilización de validaciones compartidas.
- Tratamiento de presentaciones retiradas, sustituidas o históricas.
