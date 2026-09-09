# Contrato del registro y panel de novedades CIMA

## Registro

Cada fila de `maintenance_change_event` conserva de forma inmutable:

- identidad y tipo del cambio CIMA;
- áreas literales notificadas;
- hash y fecha de la respuesta original;
- versiones anterior y nueva, cuando existen;
- diff reproducible completo;
- número de campos cuya revisión se reabrió.

El identificador deriva del hash de la respuesta y del cambio. Reprocesar la
misma observación devuelve el evento existente y no vuelve a descargar,
versionar ni reabrir campos. Los cambios sin `ft` también se registran para que
estado y comercialización no desaparezcan, pero no se presentan como una nueva
versión documental.

La migración `e5f6a7b8c9d0` es aditiva y reversible. La tabla rechaza UPDATE y
DELETE mediante la misma barrera de inmutabilidad que las versiones fuente.

## API

- `GET /maintenance/changes` devuelve hasta 100 resúmenes por defecto,
  ordenados por Epoch descendente; admite un límite entre 1 y 500.
- `GET /maintenance/changes/{id}` añade hash de fuente, captura y diff.

La lista no incluye el cuerpo del diff: cargar todos los textos para mostrar
una tabla haría crecer la respuesta con el corpus. El detalle se solicita sólo
cuando el usuario lo abre.

## Interfaz

`Novedades CIMA` muestra tipo, áreas y campos reabiertos. El detalle diferencia
claramente un cambio sin nueva ficha de uno con diff y presenta cada artefacto
sin resumir ni reinterpretar su texto.

El panel es informativo. Decidir que una validación anterior continúa siendo
válida se realiza en la pantalla de revisión y conserva las reglas existentes
para salir de `revision_pendiente`.
