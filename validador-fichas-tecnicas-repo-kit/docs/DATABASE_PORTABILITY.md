# Portabilidad de la base de datos: SQLite y PostgreSQL

## Decisión vigente

El motor del piloto es **SQLite**, como fija la especificación v2 (§ "Base de
datos: SQLite. Con 500 documentos no hay ninguna razón para PostgreSQL").

Este documento **no cambia esa decisión**. Registra qué haría falta para
ejecutar el sistema sobre PostgreSQL, y qué se ha verificado, de modo que la
decisión pueda revisarse con datos y no rehacerse desde cero. Migrar de verdad
exigiría un ADR, porque contradice una decisión ya tomada.

## Por qué se planteó

El encargo de preparar «Excel maestros → PostgreSQL → API consumible» asumía
PostgreSQL como destino. Al medir el sistema con los maestros reales importados
(7.189 registros, 35.945 valores) el cuello de botella resultó **no ser el
motor**, sino la ausencia de índices sobre las claves foráneas: cada consulta
recorría la tabla entera.

Corregido eso (migración `f19a4c7b6d82`), SQLite responde el listado paginado en
torno a **1 s** y una búsqueda en **0,5 s**. Cambiar de motor no era lo que
faltaba.

## Estado de la portabilidad

Lo que **ya es portable**, verificado por inspección:

- `migrations/env.py` toma la URL de `APP_DATABASE_URL` cuando está definida, de
  modo que apuntar a PostgreSQL no exige tocar `alembic.ini`.
- Las migraciones usan sólo tipos genéricos (`String`, `Text`, `Integer`,
  `DateTime`, `LargeBinary`) y restricciones estándar. No hay `AUTOINCREMENT`,
  ni `batch_alter_table`, ni SQL específico de un dialecto.
- `database.py` ya condiciona el `PRAGMA foreign_keys=ON` a las URLs `sqlite`:
  en PostgreSQL las claves foráneas se aplican siempre y el PRAGMA no se envía.
- Los identificadores son UUID en columnas `String(36)` generados por la
  aplicación, no secuencias del motor.

Lo que **faltaría** para usar PostgreSQL en serio:

- Añadir el controlador (`psycopg[binary]`) a las dependencias del backend. Hoy
  no está: `pyproject.toml` sólo declara SQLAlchemy.
- Revisar las pruebas que construyen bases SQLite por fichero (`tmp_path`), que
  son la mayoría de las de importadores y migraciones.
- Decidir el comportamiento en concurrencia. El piloto es de un solo revisor y
  SQLite basta; con varios revisores simultáneos escribiendo decisiones, ésta es
  la razón real por la que podría interesar PostgreSQL, no el volumen.
- Un ADR que registre el cambio y su motivo.

## Cómo verificar el esquema contra PostgreSQL

El servicio está en `compose.yaml` tras el perfil `postgres`, de modo que
`docker compose up` **no** lo levanta y el piloto no cambia de motor por
descuido.

```sh
docker compose --profile postgres up -d postgres

pip install 'psycopg[binary]'

APP_DATABASE_URL=postgresql+psycopg://validator:validator@localhost:5432/validator \
  python -m alembic -c backend/alembic.ini upgrade head
```

La ingesta acepta la misma URL, así que el mismo camino sirve para cargar los
maestros sobre PostgreSQL:

```sh
python scripts/ingest_masters.py \
  --database-url postgresql+psycopg://validator:validator@localhost:5432/validator
```

> Nota: la verificación descrita aquí es la ruta prevista, no una ejecución
> registrada. Estas órdenes no se han ejecutado todavía en este entorno: falta
> instalar `psycopg` y levantar el contenedor. Mientras no se ejecuten, la
> portabilidad está razonada por inspección del esquema, no comprobada.

## Rendimiento medido (SQLite, maestros reales)

Medido sobre 7.189 registros y 35.945 valores importados de
`PrincipioActivoCargaMaster-22062026.xlsx` y el catálogo.

| Petición | Sin índices | Con índices |
|---|---|---|
| `GET /records?limit=25` | 152 s | ~1,1 s |
| `GET /records?limit=25&offset=100` | 136 s | ~2,0 s |
| `GET /records?q=OMEPRAZOL&limit=5` | 320 s | ~0,5 s |

El listado sin paginar sobre el maestro completo se estimó en unas 5,8 horas
antes de estos cambios.
