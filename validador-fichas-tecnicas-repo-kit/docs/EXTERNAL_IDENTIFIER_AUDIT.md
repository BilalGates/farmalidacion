# Auditoría de `ExternalIdentifier` en REAL y DEMO

- Fecha: 7 de septiembre de 2026
- Decisiones rectoras: D-004/ADR-0005 y D-006/ADR-0006
- Estado: evidencia preparada; materialización pendiente de decisión

`external_identifier` tiene cero filas en `real.db`. Los identificadores del
maestro se conservan como `FieldValue` con procedencia `master_excel`; DEMO sí
usa la entidad `ExternalIdentifier`. Es una inconsistencia de materialización,
no evidencia de que ambos deban copiar el mismo criterio.

## Identificadores observados

| Campo | Valores | Distintos | Semántica observada |
|---|---:|---:|---|
| `IDEXTERNO` | 7.189 | 7.189 | identificador de principio activo del maestro |
| `MED_IDEXTERNO` | 58.256 | 6.342 | referencia/identificador de medicamento |
| `ME_IDEXTERNO` | 29.850 | 6.342 | medicamento padre de especialidad |
| `BN_IDEXTERNO` | 48.195 | 29.850 | especialidad y referencia desde excipientes |
| `CODIGO_NACIONAL` | 48.195 | 29.850 | CN de presentación; no identidad canónica |
| `PA_IDEXTERNO` | 4.211 | 1.376 | principio activo referenciado por composición |
| `LI_IDEXTERNO` | 22.214 | 22.214 | ocurrencia de enlace |
| `IN_IDEXTERNO` | 19.766 | 3.566 | indicación referenciada |

También existen identificadores de catálogo (`EX_`, `FF_`, `GT_`, `PR_`,
`TEV_`, `UN_`, `VIA_`). Su repetición es coherente con referencias y bloques;
no autoriza fusionarlos como entidades canónicas.

Todos están ligados por procedencia a una versión documental y lote, pero la
carga actual tiene `source_version = null`. Por tanto son versionables por el
modelo, pero esta entrega concreta no aporta etiqueta de versión; el hash del
fichero sigue identificando inmutablemente el contenido.

## Propuesta para decisión posterior

Materializar `ExternalIdentifier` sólo para identificadores de entidad cuya
semántica y ámbito estén aceptados, usando `source_system + source_identifier +
source_version/hash`, conservando simultáneamente el `FieldValue` original. No
materializar como equivalentes CN, `*_IDEXTERNO` y `nregistro`, ni trasladar a
la tabla los identificadores de ocurrencia/catálogo sin definir antes su entidad
destino. Hace falta un ADR de mapeo por campo y regla de reejecución histórica;
esta auditoría no lo acepta ni migra datos.
