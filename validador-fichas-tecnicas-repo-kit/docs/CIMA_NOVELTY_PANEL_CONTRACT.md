# Contrato del registro y panel de novedades CIMA

## Registro

Cada fila de `maintenance_change_event` conserva de forma inmutable:

- identidad y tipo del cambio CIMA;
- áreas literales notificadas;
- hash y fecha de la respuesta original;
- versiones anterior y nueva, cuando existen;
- diff reproducible completo;
- número de campos cuya revisión se reabrió.

El identificador deriva de la identidad del cambio, independiente del hash de
la respuesta acumulativa. Las filas anteriores con identificador antiguo se
reconocen por sus campos literales. Reprocesar la misma observación conserva el
evento existente y no vuelve a descargar, versionar ni reabrir campos. Los
cambios sin `ft` también se registran para que
estado y comercialización no desaparezcan, pero no se presentan como una nueva
versión documental.

La migración `e5f6a7b8c9d0` es aditiva y reversible. La tabla rechaza UPDATE y
DELETE mediante la misma barrera de inmutabilidad que las versiones fuente.

## API

- `GET /maintenance/changes` devuelve hasta 100 resúmenes por defecto,
  ordenados por Epoch descendente; admite un límite entre 1 y 500.
- `GET /maintenance/changes/history` devuelve el histórico paginado con
  `items`, `page`, `page_size` y `total`. Admite página 1..10.000, tamaño
  1..100 y filtro literal exacto por `nregistro`. El orden es estable por
  fecha del cambio CIMA descendente e identificador.
- `GET /maintenance/changes/{id}` añade hash de fuente, captura y diff.

La lista no incluye el cuerpo del diff: cargar todos los textos para mostrar
una tabla haría crecer la respuesta con el corpus. El detalle se solicita sólo
cuando el usuario lo abre.

## Interfaz

`Novedades CIMA` muestra tipo, áreas y campos reabiertos. El detalle diferencia
claramente un cambio sin nueva ficha de uno con diff y presenta cada artefacto
sin resumir ni reinterpretar su texto.
La pantalla muestra el total de avisos conservados, permite buscar por número
de registro y recorrer o elegir cualquier página. También ofrece los intentos
recientes de consulta diaria. El histórico de novedades no queda limitado a la
primera página de avisos.

El panel es informativo. Decidir que una validación anterior continúa siendo
válida se realiza en la pantalla de revisión y conserva las reglas existentes
para salir de `revision_pendiente`.
