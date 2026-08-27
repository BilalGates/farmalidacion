# Contrato del informe de composición CIMA

- Issue: DEV-204
- Fase: 2
- Versión: `cima-composition-v1`
- Estado: implementado y verificado offline

## Objetivo y entrada

El informe describe una ejecución de muestreo ya cerrada mediante las
respuestas originales cacheadas de `GET /medicamento?nregistro=...`. Exige
exactamente una respuesta por cada `nregistro` seleccionado; un faltante, un
duplicado o una respuesta ajena a la muestra detienen la generación.

No descarga documentos, no selecciona medicamentos y no altera la ejecución de
muestreo. Cada respuesta se referencia por su SHA-256.

## Dimensiones

### Primer nivel ATC

Se deriva exclusivamente del primer carácter literal de cada `atcs[].codigo`.
El carácter debe ser `A`–`Z`; no se cambia mayúsculas/minúsculas ni se corrige
un código incompatible. Un medicamento con varios ATC participa en todas las
categorías observadas.

### Forma farmacéutica

Usa literalmente `formaFarmaceutica.id` y `formaFarmaceutica.nombre`. No se
agrupan etiquetas parecidas ni se sustituyen por catálogos externos.

### Vía de administración

Usa cada ocurrencia de `viasAdministracion[]`, conservando `id` y `nombre`.
Varias vías o repeticiones no se concatenan ni deduplican en el recuento de
ocurrencias.

La ausencia de una dimensión se informa mediante el identificador interno
`__MISSING__` y la etiqueta diagnóstica `Sin dato en respuesta CIMA`. No se
interpreta como `no_consta` ni `no_aplica`.

## Política multilabel

Cada fila contiene dos recuentos diferentes:

- `document_count`: un documento por categoría distinta;
- `occurrence_count`: todas las ocurrencias recibidas, incluidos duplicados.

El porcentaje usa `document_count / sample_size` y cuatro decimales. Como un
documento puede pertenecer a varias categorías, los porcentajes de una
dimensión pueden sumar más del 100 %. Esto es deliberado y evita elegir una
categoría por comodidad.

## Salidas reproducibles e inmutables

El directorio de salida contiene:

- `composition.json`: contrato completo, hashes fuente y política de recuento;
- `composition.csv`: filas exportables por dimensión y categoría;
- `composition.md`: resumen legible.

El identificador del informe es SHA-256 de la versión, la ejecución de muestra
y la lista ordenada de respuestas fuente. Repetir las mismas entradas produce
los mismos bytes. Un fichero existente distinto genera error y nunca se
sobrescribe.

Markdown escapa separadores y saltos de línea únicamente para representarlos en
la tabla; JSON y CSV conservan las etiquetas literales completas.

## Evidencia y límites

Las pruebas offline cubren dimensiones multilabel, categorías ausentes,
ocurrencias duplicadas, orden de entrada, tres formatos idénticos, conflicto de
salida, respuesta faltante/duplicada/ajena y ATC incompatible sin normalizar.

No se ha generado todavía un informe sobre el corpus real de 500. Por tanto,
D-016 permanece abierta y no se recomienda un modo de muestreo. La descarga del
corpus, las versiones documentales y Gate 2 tampoco quedan cerrados por este
issue.
