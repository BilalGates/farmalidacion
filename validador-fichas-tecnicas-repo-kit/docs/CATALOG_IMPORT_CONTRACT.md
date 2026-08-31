# Contrato de importación del catálogo de campos

- Issue: DEV-302
- Fase: 3
- Estado: implementado
- Fuente: `Catalogo_campos_clinicos_medicamentos.xlsx`
- SHA-256: `a10160ebe5c7fe0b5d2a35a12d4597c982bacdafe04cb0f8d98c437183d19eac`

## Selección reproducible

El importador abre únicamente la hoja literal `Eval. solo Ficha Técnica` y exige una sola fila de cabecera que contenga `Entidad`, `Campo` y `Tipo`. La primera columna material de esa cabecera gobierna la secuencia activa, que debe ser exactamente 1..353. Una cabecera, hoja o secuencia incompatible falla el lote y conserva un diagnóstico.

No se usa el nombre de campo como identidad: cinco pares `(bloque, campo)` aparecen repetidos y deben permanecer como filas distintas.

## Conservación

Cada definición persiste:

- lote, hoja y número de fila física;
- secuencia, entidad, bloque y campo literales;
- obligatoriedad, clasificación FT, sección y comentario literales cuando existen;
- tipo declarado literal;
- payload JSON reproducible con índice de columna, cabecera, tipo OOXML observado, valor literal y fórmula;
- tipo efectivo y decisión de override separadas del original.

No se recortan espacios, convierten números, interpretan `S*`/`N*`, deduplican filas ni corrigen conflictos. La tabla usa la fila física dentro del lote como identidad técnica; no declara una clave natural de dominio.

## Overrides aceptados

| Ámbito | Tipo original observado | Tipo efectivo interno | Decisión |
|---|---|---|---|
| `EX_DESCRIPCION` | `CHAR(20)` | `CHAR(100)` | D-021 |
| `ME_DESCRIPCION` | `CHAR(20)` | `CHAR(100)` | D-021 |
| `Medicamento - Composición / DESCRIPCION` | `CHAR(50)` y `CHAR(100)` | `CHAR(100)` | D-026 |
| `Medicamento - Links / DESCRIPCION` | `CHAR(100)` y `CHAR(255)` | `CHAR(255)` | D-026 |

Los overrides son restricciones canónicas internas. No confirman límites físicos del proveedor y nunca autorizan truncamiento.

## Diagnósticos reales

La importación conserva y registra siete diagnósticos ya reproducidos por DEV-009:

- cinco identidades `(bloque, campo)` repetidas;
- dos conflictos de tipo declarado.

Estos diagnósticos no excluyen filas. La importación finaliza con 353 definiciones.

## Idempotencia y reversibilidad

La identidad content-addressed de DEV-301 incluye fichero, versión literal opcional, bytes exactos e importador `catalog_fields` versión `1.0.0`. Dos ejecuciones sobre la fuente actual producen un lote y 353 definiciones. La migración `b72f41c9e805` es reversible y no modifica la fuente.

## Fuera de alcance

DEV-302 no importa maestros de principio activo, medicamento o especialidad; no crea registros destino; no asigna prioridades concretas; no interpreta modificadores de obligatoriedad; no resuelve conflictos y no define el contrato de exportación.
