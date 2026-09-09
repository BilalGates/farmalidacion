# Contrato de refresco y revisión selectiva CIMA

## Alcance

`pharma_validator_api.maintenance_refresh` conecta los cambios `ft` detectados
por DEV-701 con el versionado inmutable y los estados de validación. Implementa
el núcleo técnico de DEV-702 sin programar todavía la tarea diaria ni construir
el panel de novedades.

## Adquisición y versión

- Cada comprobación descarga de nuevo metadatos, índice y contenido por
  sección. La caché de corpus no puede ocultar una versión regulatoria nueva.
- El índice debe declarar secciones únicas y no vacías; una forma incompatible
  falla sin escribir.
- Una captura con contenido idéntico reutiliza la versión content-addressed.
  Cambiar sólo la hora o cabeceras HTTP no fabrica una versión clínica nueva y
  se conserva inmutable la primera captura.
- Un contenido nuevo crea otra versión y copia los vínculos a registros sin
  borrar los vínculos históricos.
- El diff conserva todos los cambios. Para reabrir una decisión se consideran
  cambios de contenido, altas, bajas o cambio de localizador del apartado; una
  nueva hora de descarga por sí sola no afecta la validación.

## Selección de campos

La selección parte de `ValueProvenance` y `SourceFragment`, no del nombre del
campo. Sólo se marcan valores cuya procedencia apunta a un apartado modificado.
Si la procedencia antigua sólo identifica el documento completo, se marcan
conservadoramente todos sus valores. Si no existe procedencia vinculable, no se
inventa una relación y el resultado informa cero campos marcados.

Una decisión resuelta recibe un nuevo evento append-only con estado
`revision_pendiente`, actor técnico `system:cima-maintenance` y referencia al
diff y a ambas versiones. La decisión anterior permanece íntegra. Un campo sin
decisión, pendiente o ya pendiente de revisión no recibe eventos redundantes.

## Atomicidad y reanudación

Crear la versión, copiar vínculos y registrar reaperturas ocurre en una única
transacción. Cualquier error revierte todo el refresco. Repetir una captura
idéntica no crea versiones, vínculos ni decisiones.

Un lote procesa sólo entradas que contienen el código `ft` y deduplica cada
`nregistro` conservando el orden de aparición. Cambios de estado o
comercialización quedan para el panel/flujo de novedades de DEV-703.
