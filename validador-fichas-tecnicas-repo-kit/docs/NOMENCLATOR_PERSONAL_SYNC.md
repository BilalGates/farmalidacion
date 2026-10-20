# Sincronización personal de Nomenclátor

Cada cuenta corporativa puede sincronizar su propia instalación SQL Server. En
**Datos → Fuentes → Mi Nomenclátor**, el usuario descarga el conector de Windows,
lo inicia en su ordenador y elige servidor, puerto, base y autenticación. El
valor `localhost` designa ese ordenador, no el servidor web. La copia resultante
queda asociada al identificador corporativo de la sesión; otro usuario no puede
reemplazarla ni consultar sus decisiones. La configuración central anterior se
mantiene sólo para administración y no interviene en este flujo.

El conector escucha exclusivamente en `127.0.0.1:8765`, acepta el origen web
indicado al arrancar, consulta sólo `dbo.nomenclatur` y no persiste contraseñas.
Admite autenticación integrada de Windows y usuario de SQL Server. Valida las 73
columnas y sus posiciones relevantes antes de transmitir; rechaza valores con
tabuladores o saltos de línea para no alterar la exportación. La API vuelve a
validar las 73 columnas, CN únicos y el hash antes de activar una copia con
nombre basado en SHA-256. Conserva un historial de versiones por cuenta.

## Preparación de cada ordenador

1. Descargar `conector-nomenclator.zip` desde Farmalidación y descomprimirlo.
2. Abrir `iniciar-conector.cmd`, pegar la dirección web de Farmalidación y dejar
   abierta esa ventana durante la sincronización. El primer inicio instala el
   controlador `mssql-python` en el perfil de Windows; requiere Python 3.11 o
   posterior y acceso al repositorio de paquetes.
3. En «Mi Nomenclátor», introducir el servidor. Para una instancia local usar
   `localhost`; para una remota, un nombre/IP alcanzable desde ese ordenador.
   Puerto `0` deja que el controlador resuelva el puerto o la instancia; indicar
   un puerto explícito si SQL Server escucha en uno conocido.
4. Elegir la misma autenticación que funciona en SQL Server Management Studio.
   Si se usa SQL Server, la contraseña sólo se envía al conector local y se
   borra del formulario después del intento. El cifrado está activado por
   defecto; si el SQL Server local no admite TLS se puede desactivar para ese
   intento. Para un servidor remoto, mantener el cifrado y verificar su
   certificado.
5. Si el navegador lo solicita, permitir el acceso a la red local para esa web.

La sesión de Farmalidación y la red de cada ordenador deben permitir la
transferencia. Este cambio no demuestra que una instalación concreta pueda
autenticarse en SQL Server ni sustituye la prueba con la base real de ese equipo.
Tampoco convierte automáticamente los datos sincronizados en valores canónicos o
de exportación; las diferencias se revisan en cada presentación.
