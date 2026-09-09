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
python scripts/run_cima_maintenance.py --start-date 09/09/2026
```

La programación concreta pertenece a infraestructura y debe invocar este
comando una vez al día. El comando devuelve código distinto de cero si una
fecha falla, permitiendo alertas del orquestador además de la alerta interna.
