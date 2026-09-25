# Plan de rediseño del catálogo de medicamentos

## Resultado buscado

Convertir la aplicación en la herramienta cotidiana para explorar, mantener,
comparar y revisar el catálogo completo. La validación farmacéutica se realiza
progresivamente en el producto; no bloquea la ingeniería del rediseño.

## Principios de entrega

- Cortes verticales pequeños y reversibles.
- Datos originales inmutables y estado canónico editable.
- Ninguna relación o clasificación inferida por comodidad.
- Nueva experiencia en paralelo a la actual hasta verificar equivalencia.
- Pruebas con el volumen real desde el primer listado.

## Secuencia

### CAT-001 — Contrato de dominio y casos de aceptación (`P0`)

Estado: contrato, fixtures e inventario de las 14 hojas completados. La posición
de columna ya se conserva y las cabeceras repetidas se distinguen sin
renombrarlas. El mapa estructural campo→nivel está en
`docs/MEDICATION_SOURCE_FIELD_MAP.md`; queda la revisión farmacéutica de las
asignaciones candidatas y documentar las que aún carecen de autoridad.
La pasada con los importadores productivos de los tres maestros conserva y
coteja sus 113.915 filas/2.170.900 valores en SQLite temporal; el detalle y el
límite de las 275 filas en cuarentena están en
`docs/MASTER_IMPORT_COVERAGE_EVIDENCE.md`.

- Adoptar ADR-0012 y un vocabulario único para autorización, presentación, CN,
  DCPF, DCP, DCSA y principio activo específico.
- Materializar fixtures de aceptación representativos sin datos de paciente.
- Inventariar los campos actuales que identifican cada nivel.
- Publicar discrepancias y campos sin autoridad conocida.

Aceptación: cada caso puede dibujarse sin fusionar identidades ni concatenar
composiciones; farmacia reconoce la terminología de la pantalla.

### CAT-002 — Contrato del CN (`P0`)

Estado: parser conservador implementado y probado; el listado del catálogo ya
acepta búsqueda por siete dígitos contra el CN de seis del registro canónico.
Los registros importados conservan literal fuente y código de trabajo aparte.
El dígito de control no se valida ni se usa para enlazar registros. Queda probar
la experiencia de búsqueda con farmacia y definir el tratamiento de CN manuales.

- Introducir valor canónico de seis dígitos y literal fuente separado.
- Aceptar búsqueda con seis o siete dígitos.
- Validar el séptimo dígito únicamente con regla aprobada y versionada.
- Auditar duplicados y colisiones antes de crear restricciones.

Aceptación: ningún literal fuente cambia; los enlaces existentes siguen siendo
reproducibles; entradas equivalentes localizan la misma presentación sólo
cuando la regla lo demuestra.

### CAT-003 — Identidades y relaciones tipadas (`P0`)

Estado: esquema aditivo, contrato puro y primera proyección conservadora
implementados. La proyección crea presentación, DCP y sustancia activa desde
registros inequívocos, además de composición DCP→sustancia. Funciona en
diagnóstico por defecto, es idempotente y conserva el CN literal. No fabrica
DCPF: los vínculos históricos especialidad→medicamento quedan diagnosticados
como puente pendiente. No se ha poblado ninguna base real. El gate técnico
Omeprazol pasó en una BD ORM temporal con mapeo por coordenadas y una corrección
reversible; esto no cierra la validación de equivalencias ni la aceptación
funcional del modelo.

- Migración aditiva para producto comercial/autorización, presentación, DCPF,
  DCP, DCSA y composición.
- Relaciones explícitas con fuente, versión y vigencia.
- Proyección desde `TargetRecord` sin borrar estructuras existentes.
- Informe de filas resueltas, ambiguas y no enlazadas.

Aceptación: los fixtures y una muestra real recorren ambos sentidos de la
jerarquía; una composición admite varios principios activos.

### CAT-004 — Estado canónico editable (`P0`)

Estado: núcleo de persistencia implementado para alta, modificación y archivo
de identidades, con historial append-only y bloqueo optimista. API de
identidades e historial implementada. Primer corte de mantenimiento de campos
fuente añadido: cada corrección guarda antes/después, actor, motivo y secuencia
en una tabla append-only independiente de las decisiones farmacéuticas; el
literal importado permanece intacto y los conflictos de versión devuelven 409.
La API y un primer editor contextual dentro del expediente del catálogo ya lo
exponen para campos de `TargetRecord` enlazados. Quedan registros no enlazados,
UX sobre volumen real y conexión con la reconstrucción/exportación de los tres
libros. El editor de mantenimiento se incorporó también a la ficha fuente para
registros no enlazados. Las 275 filas de especialidades conservan su payload y
cuentan con API e interfaz separadas de mantenimiento por fila/columna; el
estado de cuarentena no se elimina ni se crea un padre. La API está probada;
Vitest/build de estas pantallas sigue sin poder ejecutarse en el entorno actual.
El primer adaptador de reconstrucción conserva el paquete XLSX original y
aplica revisiones por libro/hoja/fila/columna, con comprobación del hash de
origen y del lote importado. La descarga de los tres libros existe tras una
bandera apagada por defecto y exige configurar la carpeta de origen. Pasó una
prueba con un libro sintético y una revisión real en la BD ORM; aún faltan la
cobertura diferencial de más hojas y tipos y la verificación de la interfaz
antes de habilitar la función.
La verificación del 25-09-2026 reconstruye los tres maestros reales sin
revisiones (72 partes XLSX idénticas) y con una corrección temporal por libro
(`General!A2`, sólo cambian la hoja y `sharedStrings.xml`). El adaptador también
crea una celda originalmente ausente en una prueba sintética. Quedan pendientes
la cobertura de correcciones de otras hojas/tipos y la revisión visual.
Una ampliación del mismo comprobador valida ocho correcciones distribuidas en
ocho hojas reales: 1 de principio activo, 5 de medicamento y 2 de
especialidades. Sólo cambian las hojas revisadas y `sharedStrings.xml`; los
originales mantienen su hash. Seis hojas no contienen una celda editable
enlazada para este recorrido y se informan como cobertura pendiente. Faltan
la reversión, los tipos numéricos y la validación frontend en este punto del
recorrido; las dos primeras comprobaciones se completan a continuación.
La suite sintética del exportador cubre ahora una segunda revisión que restaura
el libro original byte a byte, números, booleanos, texto inline con espacios y
rechazo de fórmulas. La validación de esos tipos en los maestros reales
sigue pendiente.
El comprobador real también añade una segunda revisión a las ocho celdas
corregidas y confirma que los tres XLSX restaurados tienen cero cambios y sus
72 partes internas vuelven a coincidir byte a byte con el origen. Quedaban
los tipos numéricos reales y las seis hojas sin celda editable enlazada.
El inventario OOXML confirma que los tipos observados en estos tres libros son
únicamente cadenas compartidas y números. Dos celdas numéricas enlazadas
(`General!T2` de medicamento y `General!W2` de especialidades) pasan
corrección conservando el tipo y reversión sin diferencias. Los demás tipos
permanecen cubiertos en pruebas sintéticas; falta la cobertura diferencial de
las seis hojas sin celda editable enlazada.
El comprobador cierra esa clasificación: las seis hojas tienen cero filas y
cero valores de datos según la importación, no contienen celdas materiales bajo
la cabecera en OOXML y permanecen byte a byte intactas durante corrección y
reversión. Las ocho hojas con datos del conjunto recibido tienen prueba
diferencial. Siguen las verificaciones de interfaz, modelo y aceptación.
El frontend pasa Vitest (138 pruebas), ESLint y build. Una revisión de navegador
con backend DEMO temporal confirma catálogo poblado, expediente y cuarentena
vacía. Se corrigió la solicitud de clasificaciones de niveles no presentación
y el ancho de la tabla en ventana estrecha. Permanece la prueba de uso con
datos reales y la aceptación del modelo con farmacia.
El expediente ya permite completar una celda vacía de una fila fuente enlazada:
selecciona una columna ausente de la cabecera importada, conserva `null` como
literal y registra procedencia, actor, motivo y valor vigente. La prueba
API→exportador confirma su escritura en un XLSX sintético. Falta la validación
frontend/runtime. La descarga permanece apagada.
La pantalla de cuarentena también permite completar columnas ausentes de una
hoja importada. La revisión conserva `raw_payload` y el motivo original; el
listado muestra el nuevo valor de trabajo con su historial. La API está probada
con una fila huérfana sintética. Falta ejecutar Vitest y revisar ambas pantallas
en runtime antes de considerar la experiencia validada.

- Crear, modificar, archivar, sustituir, relacionar y clasificar.
- Historial append-only de antes/después, actor y motivo.
- Bloqueo optimista y transacciones para cambios compuestos.
- Separar borrador, dato vigente, fuente y decisión farmacéutica.
- Permisos de operación preparados aunque el piloto conserve identidad
  declarada.

Aceptación: una edición nunca cambia la afirmación fuente y puede reconstruirse
completa; un conflicto concurrente no deja escritura parcial.

### CAT-005 — Explorador de catálogo (`P0`)

Estado: listado conectado al catálogo tipado, con búsqueda, filtro explícito por
Presentación/DCPF/DCP/DCSA/Sustancia, vigencia y paginación en servidor.
Las presentaciones muestran etiquetas de clasificación y admiten filtros
combinables por clase comercial y una o varias condiciones; jerarquía expandible,
vistas guardadas y columnas configurables siguen pendientes.

Primer corte por fuente: se añaden vistas separadas y filtro server-side por
procedencia exacta (`Especialidades-CargaMaster190626.xlsx`,
`Medicamento-cargaMaster25062026.xlsx` y
`PrincipioActivoCargaMaster-22062026.xlsx`). La pestaña se resuelve desde el
`SourceFragment` importado, no desde el tipo visual. Se mantiene una vista global
para identidades sin libro maestro asociado. Esto no completa aún la edición de
todos los campos/hojas ni la exportación de vuelta.

Mejora de uso con catálogos extensos: el listado anuncia el rango visible y la
página actual, y la tabla puede desplazarse vertical/horizontalmente con cabecera
fija y foco de teclado. Sigue paginando en servidor y limita cada página a 50;
se puede ordenar por nombre o código (ascendente/descendente) antes de paginar;
el retorno desde un expediente conserva filtros, orden, página y posición de lectura.
No añade vistas guardadas, jerarquía expandible ni configuración de columnas.

- Entradas por productos, presentaciones, productos clínicos y principios
  activos.
- Búsqueda por nombre, `nregistro`, CN, DCPF, DCP, DCSA y sustancia.
- Filtros server-side combinables y vistas guardadas.
- Columnas configurables, densidad, cabecera fija y panel lateral de detalle.
- Agrupación expandible de marca a presentación y composición.
- Conservar filtros, página y posición al abrir/cerrar un registro.

Aceptación: el catálogo real es utilizable sin descargarlo al navegador; las
consultas calientes responden dentro del presupuesto medido y la tarea de
localizar una presentación no exige conocer su tipo interno.

### CAT-006 — Expediente editable (`P0`)

Estado: primer corte navegable implementado. Permite corregir nombre y código,
exige revisor y motivo, aplica bloqueo optimista, conserva el literal fuente,
archiva sin borrar y presenta el historial. Las relaciones tipadas entrantes y
salientes y la composición ya son navegables; si falta un nivel, se explica sin
fabricar el enlace. Edición de relaciones, clasificaciones y comparación CIMA
siguen pendientes.

En la revisión de datos importados, el tipo de registro identifica el libro
maestro y cada bloque muestra su hoja original; las ocurrencias siguen separadas.

- Cabecera que explique qué se está editando y su lugar en la jerarquía.
- Resumen, composición, presentación, clasificaciones, fuentes e historial.
- Formularios por sección con validación accesible.
- Acciones sensibles con resumen previo y motivo.
- Navegación completa por teclado y borradores recuperables.

Aceptación: el farmacéutico corrige un registro multicomponente y vuelve al
listado sin perder contexto; la auditoría refleja el recorrido.

### CAT-007 — Lector y comparación CIMA (`P0`)

- Ficha técnica completa, índice, búsqueda y versión visibles en el expediente.
- Comparación automática por campo con evidencia literal.
- Separar coincidencia, diferencia, ausencia y no comparabilidad.
- Aceptar como corrección, descartar o dejar pendiente siempre mediante acción
  humana y con el documento exacto enlazado.
- Reutilizar el historial de versiones y diffs ya existente.

Aceptación: el usuario entiende por qué se señala una diferencia y puede abrir
el apartado fuente sin abandonar el registro.

### CAT-008 — Clasificación farmacéutica (`P1`)

Estado: consulta y edición implementadas en el expediente de presentaciones.
La clase comercial se mantiene exclusiva; las condiciones son combinables.
Cada cambio exige revisor y motivo y queda en el historial append-only. Falta
validar la pantalla en el contenedor y revisar la taxonomía final con farmacia.

- Dimensión comercial: original, genérico, biosimilar o sin clasificar.
- Condiciones no excluyentes: huérfano, estupefaciente, psicotrópico, especial
  control médico, uso hospitalario y futuras condiciones catalogadas.
- Fuente, vigencia y revisión independiente para cada afirmación.

Aceptación: combinar condiciones no sobrescribe la clasificación comercial y
ninguna etiqueta aparece sin procedencia.

### CAT-009 — Spike BOT PLUS Integración (`P1`, externo)

- Confirmar licencia, servicios web, coste, entorno y límites.
- Seleccionar sólo contenidos necesarios y su precedencia por campo.
- Diseñar adaptador sustituible, caché, vigencia y observabilidad.
- Crear fixtures contractuales sin credenciales ni respuestas propietarias.
- Prohibir scraping o automatización de BOT PLUS Web.

Aceptación: contrato autorizado y prueba en sandbox; si no existe acceso de
integración, el resto del rediseño continúa sin degradarse.

### CAT-010 — Calidad, migración y retirada de la vista antigua (`P0`)

- Pruebas de migración, pérdida cero, accesibilidad, rendimiento y concurrencia.
- Comparación de recuentos y relaciones antes/después.
- Piloto de usabilidad con tareas concretas sobre datos reales.
- Activación gradual mediante capacidad configurable.
- Retirar la vista plana sólo después de aceptación y plan de reversión.

Aceptación: gate integral correcto, informe de migración sin pérdidas y tareas
principales completadas por farmacia sin asistencia técnica.

## Orden inmediato

1. Revisar con farmacia el mapa estructural campo→hoja→tipo de registro y
   confirmar o rechazar las asignaciones candidatas pendientes.
2. Validar CAT-002 en el buscador con códigos reales, dejando visible que no se
   calcula ni verifica el dígito de control.
3. Gate técnico Omeprazol: comparación OOXML directa y recorrido por BD ORM
   temporal completados con 22 hojas/616 ocurrencias/2.674 valores, cero
   diferencias tras restaurar la edición y hash fuente intacto. También pasó la
   auditoría de cobertura con los importadores productivos de los tres maestros
   (113.915 filas y 2.170.900 valores; 275 filas quedan preservadas en
   cuarentena). Sigue pendiente revisar el modelo canónico con farmacia y
   completar la prueba del adaptador de exportación hoja por hoja sobre los tres
   maestros reales. El primer adaptador y su descarga protegida ya están
   implementados y probados con un Excel sintético.
4. Verificar visualmente el editor de todas las filas (incluida cuarentena) en
   el contenedor actual y probar la reconstrucción de los tres maestros con
   cambios y reversión, incluidos vacíos y hojas secundarias; mantener bloqueada
   la exportación productiva hasta superar esa prueba y el gate de farmacia.
5. Implementar lector y comparación CIMA reutilizando versiones y diferencias
   existentes; las decisiones siguen siendo humanas.
6. Verificar frontend en el contenedor actual y hacer la prueba de usabilidad
   con farmacia. BOT PLUS permanece como dependencia externa de autorización.

Las migraciones CAT-003/CAT-004 son aditivas, pero no se ha proyectado ni
sobrescrito `real.db`. Omeprazol también pasó por una BD ORM temporal del
esquema de la aplicación y una edición/reversión append-only; véase
`docs/OMEPRAZOLE_ROUNDTRIP_EVIDENCE.md`. La prueba usa identidad por coordenadas,
no el pipeline productivo de los tres maestros. La edición integral y la
exportación final siguen bloqueadas hasta cerrar ese recorrido de extremo a
extremo y validar el modelo canónico.
