# Contrato técnico de versionado documental CIMA

- Issue: DEV-205
- Fase: 2
- Estado: aceptado para el modelo interno; D-020 cerrada

## Alcance

Este contrato permite almacenar y reconstruir sin pérdida paquetes adquiridos
de CIMA. No interpreta secciones, no calcula diferencias, no determina cuál es
la versión vigente y no infiere la fecha de revisión del apartado 10.

El documento técnico se localiza mediante `source_type =
cima_document_type_{tipoDoc}` y el `nregistro` literal como nombre. Esta
convención de servicio no fusiona `nregistro` con CN ni añade una clave natural
irreversible al esquema.

## Versión content-addressed

Una versión agrupa ocurrencias ordenadas de artefactos. El hash del paquete se
calcula sobre:

- versión literal de fuente, si fue proporcionada;
- rol y ordinal de cada artefacto;
- localizador;
- URL fuente;
- estado HTTP;
- tipo de contenido;
- SHA-256 del cuerpo original.

Cabeceras y fecha de captura se conservan, pero no se usan para declarar un
cambio de contenido. Si el mismo paquete aparece con metadatos distintos, se
genera un conflicto visible en lugar de sobrescribir o escoger unos datos.

`source_version` es opcional y literal. DEV-205 no deriva ese valor de Epoch,
cabeceras HTTP, orden de descarga ni texto documental.

## Artefactos y reconstrucción

Cada `source_document_artifact` conserva:

- versión documental;
- rol, ordinal y localizador;
- URL, estado HTTP, tipo y cabeceras ordenadas;
- fecha de captura original con su zona horaria;
- cuerpo binario original y SHA-256.

Los artefactos pueden representar metadatos, secciones u otras respuestas sin
forzar JSON, HTML o texto. Las repeticiones se representan mediante ordinales;
no se concatenan. La reconstrucción devuelve los bytes almacenados y vuelve a
verificar el hash antes de entregarlos.

## Inmutabilidad e idempotencia

- Repetir el mismo paquete devuelve la versión existente y no duplica filas.
- Cambiar cualquier cuerpo o metadato que forma parte del hash crea otra
  versión y conserva la anterior.
- `UPDATE` y `DELETE` de versiones o artefactos se rechazan desde el ORM.
- Una modificación externa por SQL directo no está autorizada; la lectura
  detecta al menos cualquier discrepancia entre cuerpo y hash.
- La migración puede revertirse hasta DEV-203 sin afectar las tablas previas.

## Evidencia automatizada

Fixtures offline verifican:

- ingestión idéntica idempotente;
- nueva versión ante cambio de una sección;
- coexistencia y reconstrucción exacta de ambas versiones;
- cuerpo binario no decodificable preservado byte a byte;
- colisión de cabeceras visible;
- bloqueo de mutación ORM;
- detección de cuerpo corrupto;
- ocurrencias repetidas rechazadas y downgrade reversible.

## Aceptación y límites

D-020 fue aceptada el 31 de agosto de 2026 tras verificar el corpus real de 500
documentos. La aceptación conserva `source_version` opcional y literal; no
autoriza inferirla de fechas, orden, cabeceras o contenido ni declarar vigencia
regulatoria. DEV-206 describe diferencias sin decidir cuál versión es vigente.
