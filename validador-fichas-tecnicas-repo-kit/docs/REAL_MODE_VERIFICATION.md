# Verificación operativa del modo REAL

- Fecha: 7 de septiembre de 2026
- HEAD auditado: `4205155611beb4dab709f24b49b45a404a8d2951`
- Base: `data/local/real.db`, Alembic `4d7a6b2c1e90`

## Estado comprobado

La carga operativa contiene 43.381 registros, 2.169.251 valores con
procedencia, cuatro lotes `completed` y 275 filas en cuarentena. Estas cifras
describen la base servida; no son equivalentes a que los importadores de Fase 3
estén verificados por pruebas.

`#/fichas` consulta exclusivamente `origin=real`, con 50 filas por página. La
búsqueda, total y paginación se ejecutan en backend. DEMO permanece en
`#/registros` y no se ofrece dentro de Fichas técnicas.

Se corrigió una regresión de HEAD: «Abrir ficha» navegaba desde `#/fichas` a
`#/registros/{id}`. Ahora conserva `#/fichas/{id}` y, por tanto, usa el detalle
REAL. Los estados loading, success, empty, error y retry están cubiertos por
`AsyncBoundary` y pruebas de interfaz; el cliente corta a los 30 segundos.

## Smoke real

`q=omeprazol` devuelve actualmente 576 coincidencias. El primer resultado
`005cc4d8-72ae-5d84-8482-d9e16d63f3cc` contiene:

- `CODIGO_NACIONAL = 707703`;
- fuente `master_excel`;
- fichero `Especialidades-CargaMaster190626.xlsx`;
- localizador `General`, fila 15991;
- lote `b377ce6337ca295803369ca4b9d5e6942e5f59443038ecb5f6a43082d0236c72`;
- hash `2117c3e33c05158dd10f81ce07424dd1ea2d0f36747faea3ad9c630b2d4ab37b`.

La versión fuente es `null`: la carga se ejecutó sin `--source-version`; no se
ha inferido desde el nombre del fichero.

## Rendimiento observado

Instancia local Uvicorn, SQLite, tres rondas consecutivas:

| Consulta | Ronda fría | Rondas calientes | Objetivo piloto |
|---|---:|---:|---:|
| dashboard | 1.393 ms | 352–356 ms | <500 ms |
| primera página | 215 ms | 146–185 ms | <800 ms |
| búsqueda `omeprazol` | 159 ms | 144–173 ms | <800 ms |
| segunda página | 110 ms | 125–219 ms | <800 ms |
| detalle | 49 ms | 38–71 ms | <800 ms |

El dashboard supera el objetivo sólo en primera lectura con caché fría de
SQLite. El cuello anterior de búsqueda se eliminó con un índice cubriente
justificado por `EXPLAIN QUERY PLAN` y una sola consulta para total+página; no
se modificaron datos ni cardinalidades.

## Fuentes e importaciones

Fuentes e Importaciones están activas y leen la base. Hay tres documentos
maestro visibles; el lote de catálogo es una importación real, pero no aparece
como documento porque no crea `SourceDocument`. Los cuatro lotes muestran
fichero, hash, fecha, estado, recuentos, cuarentena e incidencias. CIMA y fichas
técnicas existen como corpus reproducible local, pero no están enlazados a los
registros de `real.db`; la interfaz los declara pendientes y no inventa vínculo.

## Reverificación independiente — 7 de septiembre de 2026

HEAD `69fa28fe820e07a06190d5e386140cbce71d6935` reverificado contra la base y
los endpoints en ejecución, sin apoyarse en las cifras ya documentadas.

Cifras confirmadas por consulta directa a `real.db`: 43.381 `target_record`,
2.169.251 `field_value`, 2.169.251 `value_provenance` (relación 1:1), cuatro
lotes `completed`, 275 filas en cuarentena, `external_identifier` con cero
filas y Alembic en `4d7a6b2c1e90`.

`scripts/smoke_real_mode.py` devuelve **PASS**: `omeprazol` sigue dando 576
coincidencias y `CODIGO_NACIONAL = 707703` conserva fichero, hoja `General`,
fila 15991, lote y hash. `/database-info` responde `mode=real`,
`records_real=43381`, `records_demo=0` y `consistent=true`.

`scripts/analyze_master_cima_links.py` se reejecutó y reprodujo la auditoría sin
desviaciones: 706 CN con match exacto único, 0 CN con varios candidatos, 186
`nregistro` con varios CN y 0 incidencias estructurales.

### Configuración de lectura de SQLite

Se detectó que el motor sólo fijaba `foreign_keys=ON`, dejando la caché por
defecto (~2 MB) para una base de 1,7 GB. Con caché fría el recuento de
`value_provenance` costaba 11,3 s y 10 ms con las páginas ya residentes. Se
reservan ahora 256 MB de caché y 2 GB de `mmap`, con prueba de regresión en
`backend/tests/test_database_engine.py`. No se tocaron esquema, índices ni
datos.

Medición sobre el backend en modo REAL tras el cambio (cinco rondas):

| Consulta | Ronda fría | Rondas calientes | Objetivo piloto |
|---|---:|---:|---:|
| dashboard | 600 ms | 236–333 ms | <500 ms |
| primera página | 845 ms | 384–434 ms | <800 ms |
| búsqueda `omeprazol` | 1.607 ms | 313–397 ms | <800 ms |
| segunda página | 466 ms | 242–498 ms | <800 ms |
| detalle | 293 ms | 77–93 ms | <800 ms |

Todas las consultas calientes cumplen el objetivo. Las rondas frías dependen del
almacenamiento del host y no de la estructura de la base.
