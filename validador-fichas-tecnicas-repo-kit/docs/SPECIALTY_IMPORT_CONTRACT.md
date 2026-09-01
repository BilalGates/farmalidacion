# Contrato de importación del maestro de especialidades

## Alcance

DEV-305 importa `Especialidades-CargaMaster190626.xlsx` como línea base versionada. El SHA-256 esperado es `2117c3e33c05158dd10f81ce07424dd1ea2d0f36747faea3ad9c630b2d4ab37b`.

La operación requiere que DEV-303 y DEV-304 hayan importado previamente principios activos y medicamentos. No modifica el libro fuente ni completa, normaliza, deduplica o corrige valores.

## Hojas y recuentos

| Hoja | Filas fuente | Ocurrencias importadas | Filas en cuarentena |
|---|---:|---:|---:|
| General | 29.850 | 29.850 | 0 |
| Excipientes | 18.620 | 18.345 | 275 |
| **Total** | **48.470** | **48.195** | **275** |

Las ocurrencias importadas contienen 1.623.810 valores y 1.623.810 registros de procedencia `master_baseline`.

## Representación canónica

- Cada fila de `General` crea un `TargetRecord` de tipo `specialty` y una ocurrencia `specialty_general`.
- Cada fila válida de `Excipientes` crea una ocurrencia repetible `specialty_excipient` sobre su especialidad padre.
- Cada celda material conserva valor literal, tipo OOXML observado, hoja, fila y columna mediante su valor y fragmento fuente.
- `BN_IDEXTERNO`, `CODIGO_NACIONAL` y `ME_IDEXTERNO` se conservan como identificadores observados de fuente; no se convierten en PK canónica ni se consideran equivalentes a `nregistro`.

## Relaciones e integridad

Las 29.850 filas generales enlazan a un medicamento solo cuando `ME_IDEXTERNO` coincide literal y unívocamente con una fila general importada por DEV-304. No se usa nombre, descripción, semejanza ni normalización.

Las filas de excipiente se relacionan mediante `BN_IDEXTERNO` literal. Se reproducen 275 filas sin padre, correspondientes a 184 identificadores distintos. Cada fila permanece íntegra en `quarantined_source_row`, con hoja/fila, payload literal, hash y motivo `MISSING_PARENT`; no se crea una ocurrencia canónica huérfana ni se intenta repararla.

Un duplicado fuente no implica error y no se fusiona. La cardinalidad observada especialidad→excipiente es repetible; el orden se conserva mediante ordinal por especialidad.

## Idempotencia y fallo

La identidad del lote combina sistema, localizador, versión literal opcional, hash, importador y versión del importador. Repetir el mismo lote devuelve los mismos recuentos sin crear valores, ocurrencias, vínculos ni cuarentenas adicionales.

Un OOXML inválido deja el lote fallido y el diagnóstico `SPECIALTY_IMPORT_INVALID`. No se silencian cabeceras ausentes o vacías.

## Fuera de alcance

DEV-305 no resuelve los huérfanos, no concilia CIMA, no decide prioridades entre fuentes, no implementa conflictos generales, no define exportación y no inicia DEV-306.
