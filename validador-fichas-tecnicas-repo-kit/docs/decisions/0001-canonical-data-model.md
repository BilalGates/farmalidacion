# ADR-0001 — Separar documentos fuente, registros destino y ocurrencias repetibles

- Estado: propuesto
- Fecha: 2026-08-24
- Decisiones relacionadas: D-001, D-002, D-003, D-006, D-020
- Responsables: producto, farmacia y tecnología

## Contexto

La especificación v2 propone una tabla `registro` y una unicidad por registro, campo y segunda validación. Los ficheros reales contienen múltiples composiciones, indicaciones, vías, frecuencias, excipientes, enlaces y otros bloques para una misma entidad. Además, una ficha técnica pertenece a un `nregistro`, mientras que los registros destino pueden identificarse por CN, medicamento, especialidad o principio activo y relacionarse con más de una fuente.

## Restricciones

- Debe conservarse cada fila repetible.
- Cada propuesta y validación debe apuntar a una fuente y versión exactas.
- El piloto usa SQLite, pero el modelo debe ser portable.
- La exportación debe reconstruir los bloques por filas.
- No se puede sobrescribir texto histórico.

## Opciones consideradas

### Opción A — Mantener una fila por registro y campo

Sencilla, pero no representa la cardinalidad real. Obliga a serializar listas o perder filas y hace ambigua la auditoría.

### Opción B — Crear una tabla específica para cada bloque

Muy explícita y tipada, pero multiplica tablas y migraciones; cualquier nuevo bloque exige código.

### Opción C — Modelo canónico con ocurrencias de bloque y valores configurados

Separar documento/versiones, registro destino y vínculos. Representar cada fila repetible como `instancia_bloque`, con valores de campo asociados, claves naturales, orden, procedencia y estado. Permite tablas especializadas solo donde aporten valor.

## Decisión propuesta

Adoptar la opción C, con un enfoque híbrido: núcleo canónico configurable para importación, revisión y exportación; tablas tipadas adicionales para relaciones críticas si las pruebas demuestran que son necesarias.

El contrato conceptual, diagrama, cardinalidades conservadoras y cobertura de las 22 hojas de omeprazol se desarrollan en `docs/CANONICAL_CONCEPTUAL_MODEL.md`. La evidencia de DEV-003 demuestra capacidad de representación sin pérdida de ocurrencias, pero no resuelve las claves de negocio ni ejecuta el round-trip; por ello este ADR permanece propuesto.

DEV-005 desarrolla la unidad de revisión y el grafo entre destinos en `docs/TARGET_RECORD_RELATIONSHIP_EVIDENCE.md` y ADR-0006. La relación `nregistro`↔CN sigue pendiente de evidencia CIMA, por lo que este ADR no cambia de estado.

ADR-0006 fue aceptado el 25 de agosto de 2026 y cierra D-001, D-002 y D-006 en su alcance conceptual. ADR-0001 permanece propuesto hasta el round-trip y la aceptación del modelo completo.

DEV-007 demostró el 25 de agosto de 2026 que el núcleo candidato puede importar las 22 hojas del fixture de omeprazol sin perder sus 616 ocurrencias materiales ni sus 2.674 valores. La identidad usada por el spike es exclusivamente técnica y derivada de coordenadas de fuente; no valida claves de negocio. La exportación y comparación semántica siguen pendientes en DEV-008, por lo que el estado permanece propuesto.

DEV-008 completó el 25 de agosto de 2026 dos round-trips reversibles: 22/22 hojas, 2.674/2.674 valores y estructura OOXML auxiliar conciliados con cero diferencias. Esta evidencia valida la capacidad técnica de no pérdida para el fixture, pero no demuestra claves naturales, relaciones farmacéuticas ni un esquema físico definitivo. El ADR permanece propuesto hasta validación y aceptación humana del modelo completo.

## Consecuencias

### Positivas

- Representa los Excel sin pérdida.
- Permite añadir campos por configuración.
- Conserva procedencia y versiones.
- Facilita un round-trip verificable.

### Negativas

- Consultas y validaciones más complejas.
- Requiere claves y cardinalidades bien definidas.
- Puede necesitar vistas de lectura tipadas para simplificar el backend.

### Riesgos

- Convertir el núcleo configurable en un EAV sin restricciones.
- Dificultad de garantizar tipos y claves si el catálogo sigue ambiguo.

## Validación

- Importar las 22 hojas del omeprazol.
- Exportar y comparar semánticamente.
- Probar varios CN por `nregistro`, varios principios activos y varias ocurrencias del mismo bloque.
- Demostrar validación de tipos y cardinalidades.

## Migración y reversibilidad

No implementar migraciones definitivas hasta aprobar el ADR. Un spike puede usar un esquema temporal desechable.

## Preguntas pendientes

- Unidad exacta que ve el farmacéutico.
- Clave natural de cada bloque.
- Cuándo una ocurrencia se comparte entre presentaciones.
- Qué tablas merecen modelado tipado específico.
- Relación y cardinalidad exactas entre `nregistro`, CN, autorización CIMA, medicamento, especialidad/presentación y principio activo.
- Semántica e identidad de los conceptos transversales.
