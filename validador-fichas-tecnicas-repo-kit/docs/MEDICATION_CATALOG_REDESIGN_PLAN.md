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

Estado: contrato y fixtures estructurales completados; mapeo de campos reales
pendiente.

- Adoptar ADR-0012 y un vocabulario único para autorización, presentación, CN,
  DCPF, DCP, DCSA y principio activo específico.
- Materializar fixtures de aceptación representativos sin datos de paciente.
- Inventariar los campos actuales que identifican cada nivel.
- Publicar discrepancias y campos sin autoridad conocida.

Aceptación: cada caso puede dibujarse sin fusionar identidades ni concatenar
composiciones; farmacia reconoce la terminología de la pantalla.

### CAT-002 — Contrato del CN (`P0`)

Estado: parser conservador implementado y probado; integración en búsqueda,
persistencia y auditoría real pendiente.

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
como puente pendiente. No se ha poblado ninguna base real.

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
identidades e historial implementada; formularios del expediente pendientes.

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

1. Terminar CAT-001 con fixtures y mapeo de campos reales.
2. Diseñar y probar CAT-002 sin migrar `real.db`.
3. Prototipar CAT-005 con contratos de API simulados.
4. Revisar esos artefactos con farmacia.
5. Sólo entonces crear las migraciones de CAT-003 y CAT-004.
