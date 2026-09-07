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
