# Contrato operativo del mantenimiento diario CIMA

## Modelo de ejecución

`scripts/run_cima_maintenance.py` realiza una pasada finita y está diseñado
para ser invocado diariamente por cron, systemd timer, Task Scheduler o el
orquestador de despliegue. No mantiene un segundo planificador residente dentro
de la aplicación.

La fecha inicial es explícita (`--start-date dd/mm/yyyy`). La fecha final puede
indicarse con `--through-date`; por defecto es el día anterior, evitando
consultar como cerrado un día que todavía está creciendo.

## Cursor y recuperación

El cursor se deriva del último `maintenance_run` completado. Se procesan en
orden todos los días posteriores hasta la fecha final. Si no hay ejecuciones
completadas se comienza en la fecha inicial declarada.

Cada día tiene intentos numerados. Un fallo:

- conserva un intento `failed` con tipo y mensaje de error;
- detiene los días posteriores;
- no adelanta el cursor;
- provoca que la siguiente pasada repita el mismo día con otro intento.

El cliente CIMA conserva sus límites, timeout y reintentos exponenciales. El
historial operativo no sustituye esos reintentos: registra el resultado final
de la pasada.

## Observabilidad

`GET /maintenance/runs` devuelve las ejecuciones más recientes, incluyendo
fecha consultada, intento, estado, eventos, error e instantes de inicio/fin. El
panel muestra como alerta el último fallo con su intento y detalle.

Un proceso interrumpido puede dejar `running`, que permanece visible. No se
declara éxito por ausencia de error en logs: sólo `completed` mueve el cursor.

## Ejemplo

```powershell
$env:APP_DATA_MODE = 'real'
$env:APP_DATABASE_URL = 'sqlite:///./data/local/real.db'
python scripts/run_cima_maintenance.py --start-date 09/09/2026
```

El comando rechaza el modo DEMO y una ruta SQLite REAL sin fichero, antes de
abrir una conexión o llamar a CIMA.

La programación concreta pertenece a infraestructura y debe invocar este
comando una vez al día. El comando devuelve código distinto de cero si una
fecha falla, permitiendo alertas del orquestador además de la alerta interna.

## Ejecutor para un host con Docker Engine permanente

El mismo trabajo puede ejecutarse como contenedor finito, sin sesión de
Windows, desde la raíz del repositorio desplegado en un host que permanezca
encendido:

```text
docker compose --profile maintenance run --build --rm maintenance-real
```

El servicio comparte `data/local/real.db` y la caché CIMA con el backend REAL.
`CIMA_START_DATE` permite cambiar la primera fecha (por defecto 27/09/2026);
el cursor persistido procesa los días pendientes y evita repetir días completos.
La fecha final implícita es el día anterior en UTC; para una pasada fuera del
horario diario previsto se puede fijar `--through-date` explícitamente al usar
la CLI.
El servicio no se arranca con `--profile real`: el planificador del host debe
invocarlo una vez al día y registrar su código de salida. Antes de programarlo,
hay que verificar que `real.db` existe, está migrada y contiene los maestros;
además se requiere copia y restauración probada de los datos humanos según
`HUMAN_DATA_PROTECTION.md`. La tarea actual de Windows continúa activa hasta
que exista el host permanente y se complete esa transición.
