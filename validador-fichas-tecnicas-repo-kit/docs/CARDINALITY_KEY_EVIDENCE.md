# Evidencia de cardinalidades y claves — DEV-004

## Alcance

Análisis dirigido y reproducible de cuatro maestros para contrastar relaciones padre-hijo y 35 hipótesis de clave. No es un esquema físico, no materializa relaciones fila a fila y no convierte unicidad observada en identidad canónica.

- Herramienta: `scripts/analyze_reference_relationships.py`
- Evidencia final: `artifacts/dev004-complete/` (ignorada por Git)
- Hash reproducible: `c685c293172fd3702db881eff6823409a6f9b8447772ab283ef159bba2f23a6c`
- Entradas: hashes inventariados de principio activo, medicamento, especialidades e interacciones.
- Originales modificados: no.

## Relaciones observadas

| Relación | Clave de enlace observada | Filas hijas | Cardinalidad observada | Padres sin hijos | Huérfanos |
|---|---|---:|---:|---:|---:|
| principio activo → frecuencia | `IDEXTERNO` → `PA_IDEXTERNO` | 0 | 0..0 | 7.189 | 0 |
| principio activo → vía | `IDEXTERNO` → `PA_IDEXTERNO` | 0 | 0..0 | 7.189 | 0 |
| principio activo → consejo | `IDEXTERNO` → `PA_IDEXTERNO` | 0 | 0..0 | 7.189 | 0 |
| principio activo → dato analítico | `IDEXTERNO` → `PA_IDEXTERNO` | 0 | 0..0 | 7.189 | 0 |
| medicamento → composición | `MED_IDEXTERNO` | 4.211 | 0..22 | 3.148 | 0 |
| medicamento → indicación | `MED_IDEXTERNO` | 19.766 | 0..89 | 1.086 | 0 |
| medicamento → frecuencia | `MED_IDEXTERNO` | 0 | 0..0 | 6.342 | 0 |
| medicamento → vía | `MED_IDEXTERNO` | 5.723 | 0..27 | 1.086 | 0 |
| medicamento → prescripción | `MED_IDEXTERNO` | 0 | 0..0 | 6.342 | 0 |
| medicamento → enlace | `MED_IDEXTERNO` | 22.214 | 1..74 | 0 | 0 |
| especialidad → excipiente | `BN_IDEXTERNO` | 18.620 | 0..11 | 16.855 | 275 filas / 184 claves distintas |
| interacción → aplicación | `IDEXTERNO` → `IN_IDEXTERNO` | 436.148 | 1..21 | 0 | 0 |

`0..0` describe únicamente el fichero recibido con hoja sin datos; no demuestra que el bloque sea 1:1, obligatorio ni inexistente en el dominio. Los máximos son máximos observados, no límites normativos.

## Unicidades observadas

| Libro / hoja | Columnas | Filas completas | Resultado |
|---|---|---:|---|
| principio activo / General | `IDEXTERNO` | 7.189 | única en esta versión |
| medicamento / General | `MED_IDEXTERNO` | 6.342 | única en esta versión |
| medicamento / Links | `LI_IDEXTERNO` | 22.214 | única en esta versión |
| medicamento / Links | `MED_IDEXTERNO + LI_IDEXTERNO` | 22.214 | única, pero no mínima mientras `LI_IDEXTERNO` sea único |
| especialidades / General | `BN_IDEXTERNO` | 29.850 | única en esta versión |
| especialidades / General | `CODIGO_NACIONAL` | 29.850 | única en esta versión |

Estas son claves **candidatas observadas**. Falta demostrar estabilidad entre versiones, autoridad del emisor, reglas de altas/bajas, reutilización y alcance temporal. No se deduce una clave natural por conveniencia técnica.

## Hipótesis rechazadas o no evaluables

- Las variantes `ID_*` internas aparecen vacías en los maestros y no pueden actuar como claves en esta versión.
- Las hojas vacías no prueban unicidad de sus combinaciones candidatas.
- Varias combinaciones de bloques poblados contienen duplicados observados; se conservan como multiplicidad y no se califican como error.
- `IDEXTERNO` de interacciones no es único: se observaron 17.238 repeticiones respecto a las filas completas. La identidad de esta línea permanece separada.
- La evidencia no relaciona `nregistro` con CN, medicamento, especialidad o principio activo; D-006 y DEV-005 siguen abiertos.

## Criterio de interpretación

La evidencia permite implementar posteriormente enlaces de importación trazables usando identificadores de fuente, pero no autoriza restricciones canónicas definitivas. D-004 permanece propuesta hasta validación humana y round-trip.
