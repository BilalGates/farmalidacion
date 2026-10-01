# Plan de gestión de fuentes e intercambio de datos

Fecha: 1 de octubre de 2026. Estado: diseño técnico actualizado; conectores externos pendientes de contratos y accesos.

La página de Fuentes se convertirá en el punto de gestión de los archivos y conexiones que alimentan el catálogo, así como de sus importaciones y exportaciones. Permitirá añadir, configurar, sustituir y retirar fuentes conservando los datos originales y las decisiones realizadas sobre ellos. Este documento prepara el desarrollo; las integraciones descritas no están implementadas ni se consideran aprobadas por la existencia del plan.

## Situación actual

`SourcesScreen.tsx` consulta los documentos registrados en la base de datos y muestra versiones, hashes, hojas e incidencias. Las descripciones y accesos de exploración de los tres maestros Excel dependen de nombres de archivo concretos. La pantalla ofrece consulta, pero no alta, configuración o archivo de fuentes.

Existen importadores específicos, infraestructura de lotes, cuarentena, mantenimiento de campos, integración CIMA y una pantalla de exportaciones. También existe una reconstrucción de los maestros XLSX con revisiones, sujeta a configuración y verificaciones pendientes descritas en `MEDICATION_CATALOG_REDESIGN_PLAN.md`. Se reutilizarán estas capacidades tras comprobar sus contratos; no se partirá de cero ni se presentará una función pendiente como disponible.

El contrato exacto de salida al proveedor continúa pendiente en D-011. D-033 ya recoge la integración BOT PLUS mediante un servicio contratado. ADR-0007 exige prioridad por campo y conflictos visibles; ADR-0011 conserva la regla de vinculación exacta CN–CIMA. El diseño seguirá las identidades y revisiones del rediseño del catálogo.

## Qué se podrá gestionar

| Acción | Comportamiento propuesto |
| --- | --- |
| Añadir fuente | Crear una configuración de archivo o conexión; probarla antes de usar sus datos |
| Modificar fuente | Cambiar nombre, descripción, conexión, periodicidad o mapeo, conservando cada revisión |
| Cambiar un Excel | Cargar una versión nueva de la misma fuente y revisar sus diferencias antes de activarla |
| Corregir un dato | Registrar una revisión con usuario y motivo, manteniendo el literal original |
| Desactivar fuente | Detener futuras cargas; los datos y evidencias existentes permanecen consultables |
| Quitar fuente | Archivar y ocultar del listado habitual, con posibilidad de recuperación |
| Eliminar configuración vacía | Sólo si nunca produjo versiones, lotes, evidencias o decisiones |

Archivar una fuente no retira automáticamente sus valores del catálogo. La retirada de su contribución será una operación separada que mostrará los registros afectados, otras fuentes disponibles y las revisiones necesarias. Tampoco se borrarán decisiones humanas por sustituir un archivo.

Una fuente es la configuración estable; cada archivo o captura de conexión es una versión; cada ejecución es un lote; los valores conservan su procedencia. Por ejemplo, «Maestro de medicamentos» seguirá siendo la misma fuente aunque cambie el nombre del XLSX o se cargue una revisión mensual.

## Organización de la página

La página se llamará «Fuentes de datos» y tendrá cuatro pestañas:

1. **Fuentes**: listado, alta, configuración, activación, archivo y detalle de versiones.
2. **Importaciones**: nueva carga, vista previa, ejecución, incidencias y descarga de informes.
3. **Exportaciones**: selección de finalidad, perfil, vista previa, generación e historial de descargas.
4. **Historial**: cambios de configuración, versiones activadas, cargas y acciones, con filtros por fuente, fecha y usuario.

Cada fuente mostrará tipo, ámbito de datos, estado de configuración, última carga correcta, antigüedad de los datos, próxima ejecución cuando proceda y errores. «Configurada», «conectada» y «con datos cargados» serán estados distintos. Una conexión que falle conservará visible la fecha de los últimos datos correctos.

El detalle incluirá configuración, campos y hojas mapeadas, versiones, registros relacionados, incidencias y acciones aplicables. Las vistas de los Excel se identificarán mediante el perfil de importación, sin depender del nombre literal del archivo. Las rutas actuales de importaciones y exportaciones podrán dirigir a estas pestañas para conservar los accesos existentes.

## Fuentes previstas y configuración

| Fuente | Papel propuesto | Configuración necesaria |
| --- | --- | --- |
| Maestros Excel actuales y adicionales | Línea base y datos internos | Archivo, ámbito, hojas, cabeceras, claves, campos y política de carga |
| Nomenclátor disponible en la organización | Complementar el catálogo con los datos realmente presentes | Motor y versión, acceso o exportación, tablas o vistas, claves, fecha de vigencia y diccionario |
| CIMA | Metadatos y documentos oficiales ya integrados | Alcance de sincronización, caché, frecuencia y estado de mantenimiento |
| BOT PLUS | Fuente adicional según el servicio contratado | Licencia aplicable, servicio técnico, credenciales, campos disponibles y permisos de uso |

### Excel

Se ofrecerán perfiles iniciales para especialidades, medicamentos y principios activos. Añadir otro libro del mismo formato reutilizará el perfil. Un formato distinto requerirá un asistente de mapeo y una previsualización; no se asumirá que cualquier Excel puede importarse automáticamente.

El mapeo versionado conservará hojas, posición de columna y cabeceras repetidas, así como bloques con múltiples filas. Las columnas desconocidas se conservarán en el origen y se diagnosticarán. No se descartarán valores por carecer de correspondencia.

### Nomenclátor

Se trata de la base de datos que tiene la organización. El responsable confirmó el 1 de octubre de 2026 que usa **SQL Server**. No se presupone que su esquema sea idéntico al Nomenclátor público del Ministerio.

La pantalla permite guardar servidor, puerto, nombre de base y usuario con responsable y motivo. Una prueba mediante el driver de Microsoft establece una conexión cifrada y ejecuta únicamente `SELECT DB_NAME()`. La contraseña introducida se usa sólo en esa petición y no se persiste; para operación continua podrá suministrarse mediante `APP_NOMENCLATOR_PASSWORD`. La prueba no equivale todavía a inventario ni importación. La cuenta debe tener permisos de lectura.

Primero se inventariarán tablas, relaciones, volumen, claves y frecuencia de actualización. Se elegirá entre una conexión de sólo lectura a vistas acordadas y una importación de exportaciones CSV/XLSX. La segunda opción permite avanzar si no existe acceso de red. No se escribirá sobre la base de origen.

El conector guardará capturas reproducibles con fecha de extracción y vigencia. La carga incremental sólo se habilitará si existen indicadores fiables de cambio y eliminación; en otro caso se compararán capturas completas. La desaparición de una fila generará una incidencia o baja candidata, sin borrar automáticamente una identidad del catálogo.

### BOT PLUS

El enlace web proporcionado servirá como acceso de consulta. La ingestión se realizará mediante el mecanismo de integración que el proveedor autorice y documente, conforme a D-033. Una URL o una cuenta de consulta no permiten dar por disponible una API de datos.

El Consejo General documenta integración con programas de gestión y una clave KEY asociada al usuario y a su proveedor informático. Esa documentación se refiere a farmacia comunitaria; por tanto, se debe confirmar expresamente la modalidad aplicable a esta herramienta hospitalaria. No se han verificado endpoints, formatos ni credenciales para nuestro proyecto. Referencia: [generación de clave KEY](https://www.farmaceuticos.com/botplus/soporte-ayuda/generacion-de-clave-key/).

Antes del adaptador se confirmarán servicio, alcance de campos, acceso de pruebas, límites, actualización, almacenamiento local y posibilidad de exportar datos derivados. Hasta entonces la interfaz muestra «Pendiente de integración», con acceso a consulta web. El plan no contempla automatizar la navegación de BOT PLUS Web. El usuario indicó que facilitará las credenciales de su cuenta más adelante; aún no se ha conectado esa cuenta.

### CIMA y funcionamiento sin conexión

CIMA seguirá presente y su mantenimiento se incorporará al panel de Fuentes. Se conservarán las versiones documentales y las reglas actuales de enlace. Las nuevas fuentes no sustituirán sus documentos ni modificarán silenciosamente los vínculos existentes.

Las consultas externas se ejecutarán durante la adquisición o actualización. La revisión utilizará las capturas locales para conservar el funcionamiento sin internet previsto en el piloto, sujeto a las condiciones de almacenamiento de BOT PLUS.

## Flujo de importación

1. Elegir fuente y perfil; subir archivo o ejecutar la lectura de la conexión.
2. Guardar el original o captura, su hash, fecha y versión de configuración.
3. Analizar formato, claves, duplicados, relaciones, tipos y longitudes.
4. Mostrar filas aceptables, filas en cuarentena, campos sin mapear y diferencias respecto a la versión activa.
5. Presentar altas, cambios, posibles bajas y conflictos con datos ya mantenidos o validados.
6. Confirmar la aplicación de ese lote y activar la versión de forma controlada.
7. Consultar el resultado y descargar los diagnósticos.

La vista previa quedará vinculada al hash y configuración analizados; si cambian, se repetirá. Reimportar el mismo contenido con el mismo perfil no duplicará datos. Los fallos no dejarán una versión parcialmente activa. Para volúmenes grandes se utilizarán tareas persistentes con progreso y recuperación; el alcance de cancelación se definirá antes de publicarlo en la interfaz.

En una sustitución de maestro, la comparación distinguirá valores fuente, correcciones de mantenimiento y decisiones farmacéuticas. Un cambio externo producirá una nueva afirmación y una revisión cuando corresponda, nunca una sustitución automática de una decisión humana. Volver a una versión anterior también registrará qué cambia y qué validaciones necesitan revisión.

## Consolidación entre fuentes

Cada valor identificará fuente, versión, lote y localización: hoja/fila/columna, clave de fila en Nomenclátor, respuesta del servicio o sección documental. La prioridad se configurará por campo conforme a ADR-0007; no habrá una regla global «BOT PLUS gana» o «CIMA gana».

Se elaborará una matriz campo → fuentes disponibles → mapeo verificado → regla aceptada → tratamiento del conflicto. Si falta una regla, se mostrará la discrepancia para revisión. Las relaciones se crearán con claves y reglas demostradas; nombres parecidos no bastan para fusionar medicamentos o presentaciones. Las nuevas reglas del CN requerirán contrato versionado y auditoría de colisiones, manteniendo el literal de origen.

## Flujo de exportación

La página distinguirá tres finalidades:

| Finalidad | Contenido y límites |
| --- | --- |
| Descargar origen o reconstruir maestro | Original conservado o XLSX con revisiones e informe; identificar cuál se entrega |
| Exportar para revisión y diagnóstico | Datos seleccionados y estados de revisión; señalar que no es una carga validada al sistema destino |
| Exportar al sistema destino | Datos que cumplen el perfil, validaciones exigidas y contrato del proveedor |

La configuración propuesta incluirá fuente o conjunto de registros, bloques, columnas, formato, codificación y delimitador según el perfil. CSV será la salida por defecto y TXT/XLSX se ofrecerán cuando el adaptador esté verificado. Una vista previa mostrará cantidades incluidas y excluidas y motivos antes de generar el archivo.

Cada exportación conservará artefacto, hash, fecha, usuario, perfil versionado y procedencias suficientes para reproducirla. No se exportarán al destino registros con discrepancias de doble validación abiertas. La descarga del maestro con correcciones no acreditará validación farmacéutica. La disponibilidad de cada modalidad y los permisos de BOT PLUS se comprobarán antes de habilitarla. D-011 seguirá pendiente hasta acordar el contrato con el proveedor.

## Diseño técnico propuesto

Se mantendrá FastAPI, SQLAlchemy, SQLite y React. Se añadirá un registro de configuraciones de fuente y sus revisiones, conectado con documentos/versiones y lotes existentes. El modelo distinguirá versión disponible y versión activa, mapeos de importación, ejecuciones de sincronización y perfiles de exportación. La ampliación será aditiva para conservar los datos actuales.

Los importadores Excel y CIMA se envolverán en adaptadores comunes de adquisición, análisis y aplicación; Nomenclátor y BOT PLUS implementarán ese contrato cuando sus entradas estén verificadas. El navegador no accederá directamente a bases externas. Las credenciales permanecerán en el servidor mediante referencias a secretos y nunca se incluirán en respuestas, informes o historial.

La configuración y activación requerirán usuario identificado y motivo. En el piloto se respetará la identidad declarada existente; los permisos efectivos de administración se coordinarán con el plan Entra ID sin presentar el selector de usuario como autenticación.

### Configuración de una fuente

Cada fuente tendrá un identificador interno inmutable y un perfil versionado. La revisión de configuración incluirá como mínimo:

- identidad operativa: nombre visible, tipo, propietario y finalidad;
- entrada: fichero/carpeta gestionada o conexión, sin persistir secretos en claro;
- perfil: formato, esquema, mapeo de columnas/hojas/tablas y ámbito de datos;
- operación: activada/pausada, frecuencia si aplica, política de captura y límites;
- gobernanza: actor, motivo, fecha y revisión anterior.

La pantalla distinguirá configuración guardada, conectividad comprobada, importación correcta y datos vigentes. «Probar conexión» será de sólo lectura y no importará ni activará datos. Toda edición creará revisión; una conexión se probará antes de habilitar sincronización. Los secretos se pedirán a través del gestor del servidor o variables protegidas y se mostrará únicamente el estado configurado, nunca el valor.

### Alta e incorporación por etapas

1. **Registrar sin conectar:** crear la fuente y su perfil en estado «pendiente de configuración».
2. **Inventariar:** obtener diccionario/esquema, versión, claves, relaciones, vigencia, volumen y condiciones de uso; para una BD, acceso de sólo lectura.
3. **Mapear:** enlazar campos y entidades con el modelo tipado; los campos no mapeados permanecen visibles y conservados en la captura.
4. **Ensayar:** hacer una extracción limitada en entorno de prueba o muestra sin datos de paciente; guardar hash, fecha y diagnóstico.
5. **Conciliar:** medir claves vacías/duplicadas, filas huérfanas, cardinalidades e identidades no enlazadas; aceptar reglas sólo con evidencia.
6. **Activar:** importar una instantánea transaccional, revisar incidencias y dejar explícito qué captura está vigente.
7. **Operar:** actualizar según calendario acordado, alertar fallos y conservar la última captura buena.

La carga inicial no declara autoridad de negocio ni fusiona identidades por nombre. En versiones siguientes, una clave puede actuar como candidata de conciliación sólo si su emisor, ámbito y estabilidad están documentados y aceptados. ADR-0005 y D-027 impiden inferir estabilidad a partir de una columna llamada `IDEXTERNO` o de su unicidad en un único archivo. La sustitución de un Excel distinto sigue desactivada hasta acordar e implementar identidad y reconciliación por entidad.

### Importaciones y exportaciones en la página

Las ejecuciones se consultarán por fuente, perfil y versión; sus estados visibles serán pendiente, analizando, requiere revisión, aplicada y fallida. La ficha de ejecución mostrará actor, motivo, hash/captura, recuentos, incidencias, versión previa/nueva y artefactos descargables. Reintentar un mismo hash será idempotente; cancelar sólo estará disponible si el trabajo aún no ha aplicado cambios. El historial no permitirá borrar ejecuciones completadas.

Las exportaciones tendrán perfiles propios con columnas, orden, formato, codificación, delimitador, filtros y propósito versionados. Antes de generar se mostrará la muestra, el número de filas incluidas/excluidas y los motivos. El artefacto final quedará ligado al hash de entradas, versión del perfil y actor. Una exportación técnica para inspección se etiquetará como tal y nunca se confundirá con una entrega aceptada por un proveedor.

## Decisiones y bloqueos que se mantienen

- **Sustitución de los tres maestros:** no se activa con el comparador de filas únicamente. Hace falta una regla de identidad aprobada por entidad para asociar las filas nuevas con registros canónicos y presentar altas, cambios y bajas candidatas. La carga de hash idéntico continúa siendo idempotente.
- **Nomenclátor local:** la conexión permanece sólo de lectura y sin ejecutar consultas de datos hasta conocer motor/versión, ubicación, esquema, diccionario, claves, calendario de actualización y autorización del responsable. Se preferirá una vista de lectura limitada o una exportación controlada.
- **BOT PLUS:** la configuración puede registrarse como pendiente, pero no se activará el adaptador hasta confirmar BOT PLUS Integración, alcance contractual, documentación técnica, entorno de prueba, campos y permisos de caché/exportación. Las credenciales se configuran después, por canal seguro y como secreto de servidor; no se solicitan ni se escriben en este documento.
- **CIMA:** se incorpora el estado del mantenimiento ya existente a la página sin crear otro cliente ni modificar enlaces; la gestión de su calendario y credenciales respetará el mecanismo operativo actual.
- **Autenticación:** el actor y el motivo de la interfaz son trazabilidad declarada según el piloto; no sustituyen la autenticación ni una autorización administrativa real.

## Orden de implementación y aceptación

| Entrega | Resultado verificable |
| --- | --- |
| FUE-001 Registro de fuentes | En curso: nombre visible configurable y archivo reversible, con historial de actor y motivo. Pendiente: perfiles estables independientes del nombre del archivo y acciones de alta/retirada completas |
| FUE-002 Importación desde la página | En curso: carga de los tres formatos maestros, vista previa de estructura/hash, confirmación ligada al mismo hash, registro de responsable/motivo y conservación del XLSX original. Cualquier segundo contenido distinto para un maestro ya importado queda bloqueado hasta implementar comparación y enlace de identidades sin duplicados |
| FUE-003 Exportación integrada | Acceso a modalidades verificadas, vista previa, exclusiones y artefacto reproducible; rutas existentes conservadas |
| FUE-004 Nomenclátor | En curso: configuración no secreta versionada y prueba de acceso SQL Server. Pendiente: credenciales, inventario del esquema, mapeo y captura/importación de una muestra |
| FUE-005 CIMA en Fuentes | Configuración, última ejecución, caché e incidencias consultables; documentos y enlaces históricos intactos |
| FUE-006 BOT PLUS | Adaptador probado contra el servicio autorizado; campos, licencia y procedencias comprobados antes de activar datos |
| FUE-007 Consolidación y operación | Conflictos por campo visibles, revisión offline con capturas y recuperación de fallos comprobadas |

La gestión de archivos y exportaciones puede avanzar mientras se resuelven los accesos externos. Se probarán migración de fuentes existentes, cabeceras repetidas, filas huérfanas, sustitución con decisiones humanas, archivo/reactivación, idempotencia, interrupciones y exclusión de discrepancias en la salida. Se verificará una muestra y después el volumen real de los maestros sin alterar los originales.

## Información que falta para concretar los conectores

Para Nomenclátor: motor, esquema o diccionario, muestra sin datos de pacientes, claves, forma de acceso y responsable de actualización. Para BOT PLUS: modalidad contratada y contacto técnico, documentación del servicio y permisos aplicables. Para las salidas: quién consumirá cada archivo y qué formatos son necesarios, manteniendo separado el contrato final del proveedor.

La recomendación es completar FUE-001 y FUE-002 antes de conectar otras bases. FUE-001 tiene un primer corte de nombre visible, archivo reversible e historial. FUE-002 valida y previsualiza los tres perfiles, registra el responsable y conserva la versión original. Para evitar duplicar identidades, el servidor solo acepta la primera carga de un maestro o una repetición idéntica; bloquea un libro distinto mientras no exista comparación y enlace de identidades. El siguiente trabajo es construir ese comparador para que se pueda sustituir con seguridad un maestro ya cargado. Nomenclátor y BOT PLUS podrán incorporarse al flujo una vez resueltos sus accesos.
