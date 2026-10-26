# Sincronización personal de Nomenclátor

Cada cuenta corporativa puede sincronizar su propia instalación SQL Server. En
**Datos → Fuentes → Mi Nomenclátor**, el usuario descarga el conector de Windows,
lo inicia en su ordenador y elige servidor, puerto, base y autenticación. El
valor `localhost` designa ese ordenador, no el servidor web. La copia resultante
queda asociada al identificador corporativo de la sesión; otro usuario no puede
reemplazarla, consultarla ni ver su historial o sus decisiones. La configuración
central anterior se mantiene sólo para administración y no interviene en este
flujo. Decisión técnica: ADR-0018.

## Conector sólo para actualizar

El conector es necesario **únicamente para traer una versión nueva** desde SQL
Server. La copia verificada se guarda en el servidor de Farmalidación
(`APP_NOMENCLATOR_SNAPSHOT_DIR/<sha256 de la cuenta>/nomenclatur-<sha256>.tsv`)
con sus 73 columnas originales, y cada sincronización queda registrada en la
tabla append-only `nomenclator_user_snapshot`. Por tanto:

- Cerrar la ventana del conector o reiniciar el navegador no borra ni desactiva los datos.
- El catálogo, la comparación por presentación, «Ver información» e «Historial» leen sólo la copia guardada.
- La interfaz separa tres estados: **datos disponibles** (hay versión vigente), **conector conectado** (se puede actualizar) y cambios reales detectados tras una actualización. Un conector cerrado no se presenta como «actualización pendiente».

## Garantías de una actualización

1. El conector valida las 73 columnas y las posiciones relevantes, y rechaza tabuladores o saltos de línea.
2. La API recibe el TSV en un fichero temporal y vuelve a validar 73 columnas, CN de 6 dígitos únicos, UTF-8 y hash.
3. Sólo después se mueve atómicamente a su nombre definitivo y se registra la versión. Si algo falla (desconexión, fichero truncado, CN duplicado), se borra el temporal y la versión vigente sigue intacta.
4. Si el contenido coincide con la versión vigente, se registra la sincronización pero se informa «ya estaban al día».
5. La respuesta incluye registros nuevos, modificados (alguna de las 73 celdas difiere) y que ya no figuran, por CN. Las versiones anteriores se conservan y sus diferencias pueden consultarse en «Historial».

No se usa sincronización incremental: no hay evidencia de una marca de cambio
fiable en la fuente.

## Relación con el catálogo

- Una fila corresponde a una presentación del catálogo sólo si su CN es **idéntico** al código de exactamente una presentación activa. Varias identidades con ese CN se muestran como «ambiguo»; ninguna, como «sin correspondencia». No se usan nombres ni similitud.
- La ficha de presentación compara los campos definidos en `nomenclator_snapshot.FIELDS` con el maestro (`coincide`, `difiere`, `complemento`, `sin_comparacion`). Aceptar un dato exige rol farmacéutico y queda como decisión append-only; **no** reescribe el maestro, CIMA ni la exportación.
- Usar campos de Nomenclátor para filtros o búsqueda del catálogo está pendiente de D-035.

## API

| Método y ruta | Uso |
|---|---|
| `GET /nomenclator/snapshot` | Versión vigente: filas, fecha de origen, fecha de sincronización, número de versiones |
| `POST /nomenclator/snapshots` | Recibe la copia del conector (requiere sesión corporativa) |
| `GET /nomenclator/snapshots` | Historial propio, del más reciente al más antiguo |
| `GET /nomenclator/snapshots/{id}/changes` | Cambios de esa versión frente a la anterior distinta; 404 si no es propia |
| `GET /nomenclator/rows?q=&offset=&limit=` | Consulta paginada de la copia, con su correspondencia en el catálogo |
| `GET /nomenclator/reconciliation` | Recuento de correspondencias exactas, ambiguas y ausentes |

## Seguridad del conector

- Escucha exclusivamente en `127.0.0.1:8765`.
- Sólo responde al origen web exacto indicado al arrancar (`Origin`); cualquier otro recibe 403, también en `/health` y `/shutdown`.
- Consulta sólo `dbo.nomenclatur`, en modo lectura. No registra peticiones ni guarda contraseñas. Se aconseja un usuario SQL con permiso `SELECT` únicamente sobre esa tabla.
- Admite una sola lectura a la vez; `POST /shutdown` lo cierra desde Farmalidación salvo durante una lectura.
- La contraseña de SQL Server, si se usa, sólo viaja a `127.0.0.1` y nunca al backend. El navegador recuerda servidor, puerto, base y tipo de autenticación, nunca la contraseña.

## Preparación de cada ordenador

1. Descargar `conector-nomenclator.zip` desde Farmalidación y descomprimirlo.
2. Abrir `iniciar-conector.cmd`. La primera vez pide la dirección de Farmalidación y la guarda en `%LOCALAPPDATA%\Farmalidacion\NomenclatorConnector\origen.txt`; las siguientes arranca directamente. Para cambiarla, borrar ese fichero. El primer inicio instala el controlador `mssql-python` en el perfil de Windows; requiere Python 3.11 o posterior y acceso al repositorio de paquetes.
3. En «Mi Nomenclátor», pulsar «Comprobar» y después «Actualizar datos». «Configurar conexión» permite cambiar servidor, puerto (`0` = automático), base y autenticación.
4. Si el navegador lo solicita, permitir el acceso a la red local para esa web.
5. Al terminar, «Cerrar conector» o cerrar la ventana. Los datos siguen disponibles.

El cifrado está activado por defecto; si el SQL Server local no admite TLS se
puede desactivar para ese intento. Para un servidor remoto, mantener el cifrado y
verificar su certificado.

Este flujo no demuestra que una instalación concreta pueda autenticarse en SQL
Server ni sustituye la prueba con la base real de ese equipo. Tampoco convierte
los datos sincronizados en valores canónicos o de exportación.

## Pendiente

- Instalador o ejecutable firmado que no requiera Python (hoy: script + venv en el perfil del usuario).
- D-035: enriquecimiento del catálogo (filtros/búsqueda) con campos de Nomenclátor.
