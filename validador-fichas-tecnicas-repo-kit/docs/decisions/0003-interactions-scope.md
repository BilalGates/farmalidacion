# ADR-0003 — Separar interacciones del piloto de extracción de fichas técnicas

- Estado: aceptado
- Fecha: 2026-08-24
- Decisiones relacionadas: D-009
- Responsables: producto, farmacia y tecnología

## Contexto

El fichero de interacciones contiene 436.148 filas de datos y otras tantas relaciones `AplicaA`. Su origen y mantenimiento son estructurados y masivos. El corpus de 500 fichas técnicas no puede reconstruir de forma representativa este maestro, y mezclar ambos objetivos distorsionaría la medición del extractor.

## Opciones consideradas

### Opción A — Incluir todas las interacciones en el mismo piloto

Amplía cobertura, pero añade un volumen y una lógica que no dependen del extractor de FT.

### Opción B — Excluirlas completamente del proyecto

Simplifica el piloto, pero puede dejar incompleta la carga final.

### Opción C — Subproyecto de migración y conciliación

Mantener la entidad en el modelo canónico y en el contrato de exportación, pero desarrollar su importación, calidad e integridad como flujo separado.

## Decisión propuesta

Adoptar la opción C. No usar el LLM para generar interacciones. Incluir solo el soporte estructural necesario para no bloquear la carga final.

## Evidencia de aceptación

Decisión humana explícita del 24 de agosto de 2026: el maestro de interacciones queda fuera del piloto de extracción de fichas técnicas y se trata como línea separada de migración y conciliación.

## Consecuencias

- El piloto mide realmente la asistencia sobre fichas técnicas.
- Se requiere un backlog separado para interacciones.
- El contrato de exportación debe aclarar si el maestro se carga en la misma entrega.

## Validación

- Confirmación de farmacia y proveedor.
- Perfilado e integridad del fichero.
- Importación de una muestra y estimación del flujo completo.

## Preguntas pendientes

- Fuente original y proceso de actualización.
- Claves de relación con principios activos y medicamentos.
- Reglas de alta, modificación y baja.
