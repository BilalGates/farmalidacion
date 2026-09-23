# Cobertura de los tres libros maestros

## Ejecución reproducible

`python -m scripts.audit_master_import_coverage` ejecuta el importador de
catálogo y los importadores productivos de principios activos, medicamentos y
especialidades en una base SQLite en memoria. Después compara el inventario y
las cabeceras de todas las hojas, el payload literal de cada fila y cada campo
editable por su columna fuente. Verifica también los hashes de los libros antes
y después. No escribe en `real.db`, no modifica los Excel y no exporta libros.

Resultado del 23 de septiembre de 2026:

| Libro | Hojas | Filas fuente | Filas editables | En cuarentena | Valores fuente | Valores como campos | Valores solo en payload de cuarentena |
|---|---:|---:|---:|---:|---:|---:|---:|
| `PrincipioActivoCargaMaster-22062026.xlsx` | 5 | 7.189 | 7.189 | 0 | 35.945 | 35.945 | 0 |
| `Medicamento-cargaMaster25062026.xlsx` | 7 | 58.256 | 58.256 | 0 | 509.496 | 509.496 | 0 |
| `Especialidades-CargaMaster190626.xlsx` | 2 | 48.470 | 48.195 | 275 | 1.625.459 | 1.623.810 | 1.649 |
| **Total** | **14** | **113.915** | **113.640** | **275** | **2.170.900** | **2.169.251** | **1.649** |

Las 275 filas en cuarentena tienen razón `MISSING_PARENT`. El importador
conserva su payload íntegro y verificable (1.649 valores), pero no crea
`FieldValue` ni asigna un padre. Se añadió una capa separada de mantenimiento
append-only por fila/columna, con interfaz de cuarentena propia; las pruebas API
verifican que no altera el payload fuente ni resuelve automáticamente el padre.
La UI está implementada pero no verificada en navegador porque faltan las
dependencias frontend y el contenedor actual no está disponible. La auditoría
tampoco prueba la reconstrucción/exportación productiva de los tres libros ni
la equivalencia farmacéutica del modelo.

Los hashes antes/después coincidieron por libro; no se detectaron fórmulas en
las filas de datos. El resultado no elimina el requisito de ida/vuelta por hoja,
incluidas celdas vacías, duplicados de cabecera y hojas secundarias.
