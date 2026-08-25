# Evidencia DEV-009 — Incidencias de integridad

El analizador localiza la cabecera por `Entidad`, `Campo` y `Tipo`, limita el catálogo a 1..353 y cruza por `(bloque origen, campo)`. Dos corridas produjeron el hash `987129be4c8d7b62517c0962e19279e01b00299c7c51490e179137b3040579e7`.

## Hallazgos

- 275 filas huérfanas de excipientes y 184 claves distintas; `warning`, sin reparación.
- Seis incidencias agregadas de duplicado procedentes de DEV-002; los duplicados de fila son `info` y no se consideran errores automáticamente.
- Cinco pares `(bloque, campo)` repetidos.
- Conflictos `error`: `Composición / DESCRIPCION` declara `CHAR(50)` y `CHAR(100)`; `Links / DESCRIPCION` declara `CHAR(100)` y `CHAR(255)`.

| Bloque / campo | Límite | Máximo |
|---|---:|---:|
| Medicamento - Composición / DESCRIPCION | 50 | 100 |
| Medicamento - Links / DESCRIPCION | 100 | 197 |
| Interacciones / IDEXTERNO | 20 | 31 |
| Interacciones - GP / IDEXTERNO | 20 | 34 |

Otros 24 pares alcanzan exactamente el límite. El JSON regenerable conserva ejemplos acotados y localizaciones. Los duplicados grandes de interacciones mantienen el método estimado de DEV-002. Los overrides `EX_DESCRIPCION` y `ME_DESCRIPCION` aplican `CHAR(100)` por D-021. No se eligen tipos, deduplican filas ni reparan huérfanos; los originales permanecen intactos.
