# Contrato de consulta incremental de cambios CIMA

## Alcance

`pharma_validator_api.cima_changes` implementa el núcleo técnico de DEV-701.
Consulta `GET /registroCambios`, valida su forma documentada y devuelve una
representación estable de altas, bajas y modificaciones.

No descarga todavía nuevas fichas, no marca validaciones ni crea tareas. Esas
mutaciones pertenecen a DEV-702 y se incorporarán sobre este resultado
validado. La programación y las alertas pertenecen a DEV-704.

## Reglas

- La fecha solicitada usa exactamente `dd/mm/yyyy`.
- `fecha` se conserva como el entero Epoch recibido; no se interpreta una zona
  horaria que el contrato AEMPS deja ambigua.
- `tipoCambio` sólo admite 1 (alta), 2 (baja) y 3 (modificación).
- Los códigos conocidos de `cambios` se conservan literalmente.
- Un código nuevo no se descarta ni bloquea toda la respuesta: se incluye en
  el cambio y se declara en `unknown_areas` para hacerlo visible.
- Filas idénticas y áreas repetidas se deduplican de forma determinista.
- Una forma incompatible falla explícitamente; nunca produce un informe vacío.
- Los filtros `nregistro` conservan su orden y se deduplican sin normalizarlos.

## Frescura e idempotencia

Las respuestas de `registroCambios` no usan la caché inmutable del cliente.
Ese registro puede crecer durante el día y reutilizar indefinidamente la
primera respuesta ocultaría cambios posteriores. Las demás operaciones CIMA
mantienen su comportamiento cacheado.

El informe conserva el SHA-256 y la fecha de captura de la respuesta original,
permitiendo identificar dos observaciones iguales sin inventar una versión.

## Verificación

Las pruebas offline cubren los tres tipos, cambios de ficha técnica, códigos
nuevos, duplicados, filtros repetibles, fecha inválida, JSON o formas
incompatibles y dos consultas sucesivas que llegan realmente al transporte.

## Forma viva observada el 9 de septiembre de 2026

La API viva devuelve un envoltorio paginado con `totalFilas`, `pagina`,
`tamanioPagina` y `resultados`, y usa `cambio` para las áreas. El cliente recorre
todas las páginas y construye un cuerpo agregado con hash propio; el parser
mantiene compatibilidad con la lista plana y `cambios` de fixtures anteriores.
Una variación del total o de la página durante la lectura falla explícitamente.
