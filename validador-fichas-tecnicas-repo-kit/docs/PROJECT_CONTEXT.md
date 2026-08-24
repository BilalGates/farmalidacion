# Contexto consolidado del proyecto

## 1. Propósito

Construir una aplicación web interna que ayude a un equipo de farmacia hospitalaria a consolidar y validar los datos necesarios para cargar el catálogo de medicamentos de un nuevo sistema de prescripción electrónica. La herramienta debe reducir el trabajo de búsqueda y transcripción, colocando la evidencia correcta junto al campo correcto y permitiendo una validación rápida, trazable y reproducible.

El producto correcto no es un simple extractor de fichas técnicas. Es un sistema de consolidación y validación asistida de datos clínicos con varias fuentes:

- maestros actuales;
- metadatos estructurados de CIMA;
- texto versionado de la ficha técnica;
- decisiones explícitas del farmacéutico;
- transformaciones autorizadas y documentadas;
- otros maestros externos que se acuerden.

## 2. Límites funcionales

- No procesa datos de pacientes.
- No prescribe, recomienda tratamientos ni responde preguntas clínicas sobre pacientes.
- No decide valores clínicos que requieren criterio profesional.
- No sustituye al sistema destino.
- No convierte una posología habitual en un umbral de alerta por inferencia.
- No oculta incertidumbre, conflictos entre fuentes ni pérdida de datos.

## 3. Decisiones cerradas por la especificación v2

- Piloto con corpus de 500 fichas técnicas.
- Conjunto oro de 20 fichas y conjunto de medida de 50.
- Modelo local obligatorio para la inferencia; operación sin internet después de descargar el corpus.
- Sin autenticación en el piloto; selección declarada de usuario.
- Salida CSV por defecto y alternativas TXT/XLSX.
- Doble validación inicial para prefijo ATC `L04`.
- `EX_DESCRIPCION` y `ME_DESCRIPCION` se amplían a `CHAR(100)`.
- Stack base: FastAPI, SQLAlchemy, Alembic, SQLite, React, TypeScript, Vite, pytest, Vitest y Docker Compose.
- Cuatro políticas de interfaz: `proponer_valor`, `proponer_opciones`, `solo_evidencia` y `oculto`.
- Toda propuesta textual debe incluir evidencia literal verificable.
- La revisión completa debe poder realizarse con teclado.

## 4. Correcciones estructurales necesarias antes del desarrollo funcional

La especificación v2 es una base válida, pero su modelo de datos inicial no representa completamente los ficheros reales. El desarrollo debe incorporar estas correcciones mediante decisiones formales:

1. Separar documentos fuente, versiones de documento, registros destino y vínculos entre ambos.
2. Tratar los bloques repetibles como ocurrencias explícitas.
3. Ampliar el catálogo con subbloque, rol del campo, cardinalidad, columna de exportación, fuente prioritaria y obligatoriedad condicional.
4. Modelar la procedencia de cualquier valor, no solo citas textuales de ficha técnica.
5. Conservar versiones inmutables de las fichas y enlazar a ellas cada propuesta y validación.
6. Definir el papel de los maestros existentes como línea base de consolidación.
7. Separar el alcance de interacciones del piloto de extracción, salvo decisión contraria explícita.
8. Formalizar el contrato exacto de exportación con el proveedor.
9. Usar tipos portables de SQLAlchemy en SQLite; no asumir `jsonb` ni arrays nativos.

## 5. Entidades conceptuales recomendadas

```text
documento_fuente
  └── documento_version
        └── seccion_version

registro_destino
  ├── principio_activo
  ├── medicamento
  ├── especialidad
  └── transversal

vinculo_documento_registro

instancia_bloque
  └── valor_campo
        ├── valor_base
        ├── propuesta
        ├── evidencia/procedencia
        ├── validacion_primera
        └── validacion_segunda

auditoria
exportacion
incidencia_datos
```

Esta estructura es una recomendación de partida, no una decisión aprobada. Debe validarse mediante el caso de ida y vuelta de omeprazol y documentarse en un ADR.

## 6. Regla de seguridad clínica central

La IA puede localizar información y, en campos directos, proponer una transcripción. Para campos interpretables o de criterio clínico, debe mostrar evidencia u opciones sin preselección. La decisión final siempre pertenece a una persona identificada y queda auditada.

## 7. Criterio rector del piloto

La principal métrica de producto es el tiempo por campo validado sin degradar la calidad. La precisión del extractor es importante, pero el sistema debe seguir aportando valor aunque ciertos campos se degraden a `solo_evidencia`.
