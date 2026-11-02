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
versión documental. Desde D-040 se guardan **todos** los avisos, también los
que no tienen registro en el catálogo; estos no refrescan la ficha técnica ni
generan acciones (salvo las altas).

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
Cada aviso muestra un resumen compacto de fecha, registro, tipo, áreas, campos
reabiertos y registros del catálogo. Si hay más de dos registros relacionados,
los enlaces restantes se despliegan dentro del aviso; ninguno se descarta.

El panel es informativo. Decidir que una validación anterior continúa siendo
válida se realiza en la pantalla de revisión y conserva las reglas existentes
para salir de `revision_pendiente`.

## Acciones de mantenimiento (ADR-0019, D-040)

Capa derivada e idempotente sobre los eventos (diseño:
`docs/design/novedades-cima-accionables.md`). Migración `e1f2a3b4c5d6`, aditiva
y reversible.

### Tablas

- `maintenance_action` (insert-only; rechaza UPDATE y DELETE). Id determinista
  (uuid5 de evento, tipo, registro, CN, campo; las consultas sin respuesta CIMA
  añaden `:nodata`). Guarda valor del maestro, valor CIMA literal, puntero JSON
  (RFC 6901) a la respuesta CIMA persistida como versión inmutable
  (`source_document_version`, tipos `cima_api_presentacion` y
  `cima_api_presentaciones`), `proposed_value` y `rule_id` solo con regla
  aceptada, `data_origin` (`real`/`demo`) y `derivation_version`.
- `maintenance_action_decision` (append-only): `aceptada`, `descartada`,
  `enviada_revision`, `reabierta`, con `sequence` y actor. El estado vigente es
  la última decisión; sin decisiones, `pendiente`; `reabierta` vuelve a
  pendiente.

### Tipos de acción

| Tipo | Cuándo | Valor propuesto |
|---|---|---|
| `proponer_activo_n` | Baja (`tipoCambio=2`) o `estado.rev` presente en la respuesta capturada | `ACTIVO = N` con `ADR-0019:baja-revocacion-activo:v1`; solo propuesta |
| `revisar_estado` | Cambio de estado sin revocación | Ninguno (`sin_correspondencia`) |
| `revisar_comercializacion` | Cambio de comercialización | Ninguno (`sin_correspondencia`) |
| `revisar_archivo` | Baja | Ninguno; aceptar archiva la identidad con justificación (D-031) |
| `proponer_alta` | Alta (`tipoCambio=1`) con CN de CIMA que no está en el maestro | Fila con la cabecera exacta del maestro importado; `CODIGO_NACIONAL` y las dos descripciones con el `nombre` literal de CIMA (`ADR-0019:alta-nombre-descripcion:v1`), el resto `sin_fuente` |

Sin respuesta CIMA citable la acción se crea con `cima_no_disponible`, sin
valor ni propuesta; no se puede aceptar ni enviar. Cuando CIMA responde, la
derivación crea otra acción que sustituye a la anterior (la antigua no se
modifica ni se muestra).

### Efectos de aceptar

Solo `aceptada` escribe, con el servicio y el historial existentes:
`revisar_archivo` archiva con `catalog_store.revise_identity`;
`proponer_activo_n` añade una `field_maintenance_revision` con `ACTIVO = N`
(omite la escritura si el maestro ya dice `N`); `proponer_alta` crea una
identidad borrador (`cima_novedades_alta`) con registro, valores y procedencia
CIMA, y la encola en `corpus`. En DEMO no se crean borradores. Los demás tipos
solo registran «revisado». Cada decisión emite un `audit_event`
(`maintenance_action.decision`).

### API

| Ruta | Capacidad |
|---|---|
| `GET /maintenance/actions` (bandeja, contadores por tipo), `GET /maintenance/actions/history`, `GET /maintenance/actions/unlinked`, `GET /maintenance/actions/{id}` | `sources.read` |
| `GET /catalog/identities/{id}/maintenance-actions` | `catalog.read` |
| `POST /maintenance/actions/{id}/decisions` (`expected_sequence`; 409 si cambió), `POST /maintenance/actions/send-to-review` (máx. 200) | `review.write`, `actor_id` |
| `POST /maintenance/actions/backfill` (202, segundo plano, `maintenance_lock`) | `sources.manage` |
| `GET /catalog/identities?maintenance=pending` | `catalog.read` |

Toda consulta filtra por un único origen (`origin`, por defecto el del
despliegue); nunca devuelve REAL y DEMO a la vez.

### Backfill

`python -m pharma_validator_api.cli.maintenance_actions backfill [--origin REAL|DEMO] [--limit N]`
o el endpoint. Reanudable e idempotente; una petición CIMA por CN y pasada;
progreso en `maintenance_run` con `requested_date="backfill1"`. Toma el valor
CIMA **actual**: la interfaz dice «Valor en CIMA a fecha X», nunca «valor tras
la novedad».

### Interfaz

`Novedades CIMA` tiene tres pestañas: **Por atender** (cifras por tipo solo de
acciones con registro; grupos plegables; selección por grupo y «Enviar a
Revisión»; «Marcar revisada», «Archivar» y «Descartar» con justificación
obligatoria; sin controles preseleccionados), **Histórico** (los avisos de
siempre más las acciones decididas) y **Sin registro en el catálogo**. El
expediente muestra «Novedades CIMA sin atender» en la pestaña Fuentes, junto a
los paneles CIMA y Nomenclátor, y un contador en la cabecera. El catálogo
filtra con «Con novedades CIMA sin atender». Las acciones pendientes no
bloquean la exportación ni añaden avisos al Excel.
