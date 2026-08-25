# Contrato de perfilado agregado y reproducible de los Excel

- Estado: implementado en DEV-002
- Fase: 0B
- Versión: 1.0.0
- Entradas: los siete Excel de `docs/SOURCE_INVENTORY.md`
- Fuera de alcance: importación, modelo canónico, comparación round-trip y reconstrucción detallada de relaciones

## Objetivo

Describir de forma agregada la estructura y calidad observable de cada libro, hoja y columna sin modificar los originales ni convertir observaciones en decisiones de dominio.

El perfilador no vuelca celdas, valores o coordenadas de forma exhaustiva. Tampoco materializa relaciones fila a fila. Las claves y relaciones detalladas corresponden a DEV-004 y DEV-006.

## Seguridad e integridad

- Las entradas se limitan a los nombres y hashes inventariados bajo `data/reference/raw/`.
- Los hashes se verifican antes y después de la ejecución.
- Los XLSX se leen como ZIP/XML inerte y en streaming.
- Se rechazan traversal, ratios/tamaños excesivos, macros, ActiveX, OLE, embeddings y relaciones externas activas.
- No se ejecutan fórmulas, macros, enlaces ni conexiones; no se recalculan ni guardan libros.
- Los resultados se generan en staging y se publican mediante renombrado atómico.
- Los artefactos usan rutas lógicas; no incluyen usuarios, secretos ni rutas absolutas.

## Filas materialmente pobladas

Una fila materialmente poblada contiene al menos una celda con valor almacenado, texto, fórmula, booleano, fecha o error. Las celdas creadas únicamente por estilo o formato no cuentan como contenido. Se informa por separado la dimensión declarada por Excel y las filas observadas.

## Estadísticas agregadas

Por libro y hoja:

- orden, nombre y visibilidad;
- dimensión declarada;
- filas físicas y materialmente pobladas;
- columnas observadas;
- fila candidata de cabecera;
- rangos combinados;
- filas duplicadas y método de cardinalidad.

Por columna:

- índice, letra, cabecera original y ordinal si se repite;
- primera y última fila observadas;
- valores materiales y nulos respecto a las filas materiales;
- tipos observados;
- fórmulas y errores;
- longitud máxima;
- cardinalidad y método;
- duplicados;
- clave candidata solo cuando la cardinalidad es exacta, no hay nulos y todos los valores son distintos.

Una clave candidata es una observación y no cierra D-004. Para columnas con más de 100.000 valores distintos, la cardinalidad se estima mediante linear counting y queda identificada explícitamente; esas columnas nunca se declaran clave candidata.

## Artefactos

- `run-manifest.json`: entradas, hashes, versiones, configuración, duración, estado y hash reproducible.
- `workbooks/{workbook_id}.json`: agregados por libro, hoja y columna.
- `columns.csv`: una fila por columna observada.
- `incidents-summary.csv`: incidencias agregadas por libro, hoja y código.
- `summary.md`: resumen generado de libros y hojas.

No se generan artefactos por celda, listados exhaustivos de valores, `relations.csv` ni `orphans.csv`.

## Reproducibilidad

El hash reproducible cubre los JSON por libro, `columns.csv` e `incidents-summary.csv`. Excluye el manifiesto, timestamps, duración, metadatos no semánticos y el resumen Markdown que muestra el propio hash.

Dos ejecuciones sobre los mismos hashes, configuración y versión deben producir el mismo hash reproducible.

## Incidencias y salida

- Código `0`: siete libros procesados, artefactos publicados y hashes posteriores iguales.
- Código distinto de `0`: entrada ausente/cambiada, XLSX inseguro/ilegible, error XML, salida existente o fallo de publicación.
- Fórmulas sin cache, cabeceras repetidas y filas duplicadas se resumen sin volcar valores.

## Criterios de aceptación

- Referencias `8/8 OK`, código 0.
- Siete Excel y todas sus hojas presentes en los agregados.
- Originales con hashes intactos antes y después.
- Salidas agregadas únicamente; cero serialización por celda o relación.
- Dos corridas completas con el mismo hash reproducible.
- Tests de traversal, macros/contenido activo, CSV injection, agregación y reproducibilidad superados.
- Relaciones detalladas y huérfanos permanecen pendientes de DEV-004/DEV-006.

## Pendientes explícitos

- Cardinalidad exacta de columnas masivas que superan el umbral agregado.
- Claves naturales y reglas de identidad de D-004.
- Relaciones, cardinalidades entre bloques y huérfanos de D-006.
- Semántica de estados D-010.
