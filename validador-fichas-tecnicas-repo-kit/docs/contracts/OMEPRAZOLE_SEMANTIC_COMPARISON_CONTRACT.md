# Contrato de comparación semántica del round-trip de omeprazol

- Estado: definido para implementación posterior
- Fase: 0B
- Caso: `OMEPRAZOL 20 MGrelleno.xlsx`, 22 hojas
- Fuera de alcance: implementar importador/exportador, aceptar ADR-0001 o fijar el esquema definitivo

## 1. Objetivo

Demostrar que una futura importación y exportación conserva todas las hojas, filas materialmente pobladas, columnas, claves, relaciones, ocurrencias repetibles y valores del libro original. La comparación no corregirá ni reinterpretará el original y no incluye el maestro general de interacciones en el piloto FT, aunque sí conserva las hojas de interacciones presentes en el caso de omeprazol para probar cardinalidad y round-trip.

## 2. Evidencias de entrada

El informe fija: hash SHA-256 del original, hash/configuración del perfilado, versión del contrato, versiones de importador/modelo candidato/exportador/comparador, parámetros de serialización y hashes de los artefactos comparados. El original se abre en solo lectura y su hash se verifica antes y después.

Ninguna herramienta ejecuta fórmulas ni sigue enlaces externos durante la prueba. El libro reconstruido no puede introducir macros, DDE/OLE, conexiones o relaciones externas activas; su presencia original se compara como estructura inerte y cualquier contenido activo nuevo es defecto.

La unidad mínima es una celda de una ocurrencia localizada por libro, hoja, fila y columna. La unidad de comparación de bloque es una fila materialmente poblada con todas sus celdas, identidad candidata, ordinal y relaciones. Varias ocurrencias jamás se concatenan.

## 3. Representación comparable

Para cada lado se conserva un registro observado con:

- hoja y ordinal; fila/columna y coordenada; cabecera y ordinal si está duplicada;
- bloque, subbloque, `occurrence_index` y orden de origen;
- valor original, tipo de celda, fórmula, valor cacheado y formato relevante;
- clave/relación usada para alinear, regla y evidencia;
- procedencia hasta el fichero, hash y coordenada de entrada.

La alineación se ejecuta en este orden: hoja exacta; bloque/ocurrencia explícitos; clave natural solo si está aprobada; y, mientras D-004 siga abierta, identidad técnica provisional `(hoja, ordinal_fila_material, ordinal_ocurrencia)`. Esta identidad no es una clave canónica. Las coincidencias candidatas o ambiguas se informan y no se fuerzan.

## 4. Comparaciones y prohibiciones

### 4.1 Igualdad literal

Compara presencia, tipo y representación original exacta. Distingue vacío, cadena vacía, espacios, `0`, texto numérico, número, fecha, booleano, fórmula, error y ausencia. Es la comparación predeterminada.

### 4.2 Igualdad semántica autorizada

Solo puede aplicarse una regla con identificador, versión, decisión/ADR aceptado, ámbito de campo/hoja, función determinista, ejemplos y reversibilidad o justificación de no pérdida. El informe conserva ambos valores literales y la regla aplicada. En este contrato no se autoriza ninguna normalización concreta.

Quedan prohibidas implícitamente: `trim`, cambio de caja/tildes, número↔texto, eliminación de ceros iniciales, redondeo, conversión de unidades o fechas, cambio de separador decimal, sustitución de nulos/estados, ordenación, deduplicación, concatenación, equivalencias clínicas y recálculo de fórmulas.

## 5. Clasificación exhaustiva de diferencias

Cada diferencia pertenece exactamente a una categoría primaria:

- `order_only`: mismos elementos literales y multiplicidad, distinto orden; no se acepta hasta que el orden se declare irrelevante mediante decisión aprobada;
- `format_only`: mismo valor subyacente y distinta presentación de celda; no equivale automáticamente a igualdad;
- `authorized_normalization`: coincide únicamente por una regla aceptada y registrada;
- `defect`: valor, tipo, presencia, fórmula, fila, clave, relación, multiplicidad o procedencia perdido, añadido o alterado;
- `unresolved`: alineación ambigua o semántica pendiente de decisión humana.

No existe categoría “equivalente” libre. Toda diferencia debe conservar evidencia a ambos lados, impacto, regla si aplica y estado de revisión.

## 6. Reglas por nivel

- Libro: existe una única salida asociada al hash de entrada.
- Hoja: las 22 hojas existen una vez, con nombre y ordinal registrados; renombrar/omitir es defecto salvo regla aceptada.
- Estructura: se comparan cabeceras, columnas y filas materialmente pobladas; columnas/filas perdidas o añadidas son defecto.
- Bloque: misma cantidad de ocurrencias y multiplicidad; fusionar, dividir sin mapeo reversible o deduplicar es defecto.
- Valor: presencia, literal y tipo iguales, salvo regla autorizada explícita.
- Clave/relación: se preservan valores originales, cardinalidad y enlaces; huérfanos existentes siguen visibles y nuevos huérfanos son defecto.
- Procedencia: todo valor exportado vuelve a coordenadas de entrada; ausencia o ambigüedad es defecto.

## 7. Formato del informe

Se emite `omeprazole-roundtrip-report.json` como fuente estructurada y `omeprazole-roundtrip-report.md` como resumen generado. El JSON contiene:

- `schema_version`, `contract_version`, `run_id` y versiones de herramientas;
- entradas/salidas/configuración con hashes;
- resultado global y código de salida;
- por hoja: recuentos de filas, columnas, ocurrencias, claves y relaciones en ambos lados;
- `differences[]`: identificador estable, categoría, severidad, localizaciones origen/salida, valores/tipos literales, regla autorizada, evidencia, impacto y estado;
- totales por categoría y declaración de originales intactos.

El Markdown incluye matriz de 22 hojas, conciliación de conteos, diferencias clasificadas, reglas autorizadas utilizadas, defectos, pendientes y conclusión de gate.

## 8. Resultado y código de salida

- `pass`, código `0`: cero defectos, cero diferencias no clasificadas, cero truncamientos/descartes, multiplicidades y relaciones conservadas; solo se admiten diferencias amparadas por reglas aceptadas.
- `fail`, código distinto de `0`: cualquier defecto, diferencia `unresolved`, normalización sin autorización, pérdida de procedencia, hoja/ocurrencia omitida o imposibilidad de verificar hashes.

Las diferencias `order_only` y `format_only` no pasan por sí solas: requieren una regla/decisión aceptada y entonces quedan además registradas como `authorized_normalization` sin borrar la observación original.

## 9. Criterios de aceptación futuros

- Hash original estable antes/después y 22/22 hojas comparadas.
- Cero filas, columnas, ocurrencias, claves, relaciones y valores descartados o añadidos sin explicación.
- Cero concatenaciones de bloques repetibles.
- Cero normalizaciones implícitas; cada regla aplicada referencia decisión aceptada.
- Todas las diferencias tienen una categoría primaria, localizaciones y literales en ambos lados.
- Huérfanos y duplicados originales se preservan; los nuevos son defecto.
- El informe estructurado y su resumen concilian exactamente.
- Una segunda ejecución equivalente produce el mismo contenido reproducible.

ADR-0001 continuará `propuesto` hasta ejecutar satisfactoriamente este round-trip y el perfilado reproducible; este contrato no supera el gate 0B.
