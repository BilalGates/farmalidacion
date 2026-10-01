# Plan global de rediseño de Farmalidación

Fecha: 1 de octubre de 2026. Estado: planificación autorizada; implementación no autorizada en esta etapa.

El responsable ha aprobado preparar un rediseño global inspirado en la captura aportada: navegación lateral, herramientas compactas, superficies claras y contenido organizado mediante líneas y espacio. Se conserva la paleta actual y se recupera el degradado rosa–violeta como acento sutil. El catálogo será la pantalla guía. Este documento contiene el inventario inicial, la distribución propuesta y las entregas necesarias para avanzar sin omitir flujos.

## Alcance y evidencia

Inventario obtenido por lectura de `App.tsx`, `navigation.ts`, pantallas, componentes y documentación del repositorio. Describe la estructura presente en el árbol de trabajo, que incluye modificaciones previas; no certifica que todos los flujos funcionen en ejecución. No se ha arrancado la aplicación, consultado una base real ni capturado sus pantallas en esta etapa.

La imagen aportada es una referencia visual, no una especificación funcional. Sus tareas, prioridades, avatares y vistas de calendario no se trasladan automáticamente al programa. La escala del texto se adaptará al trabajo farmacéutico y al zoom.

Este plan complementa `UI_REDESIGN_AUDIT.md`, `UI_REDESIGN_PLAN.md`, `UI_DESIGN_SYSTEM.md`, `MEDICATION_CATALOG_REDESIGN_PLAN.md` y `SOURCE_MANAGEMENT_PLAN.md`. La documentación anterior conserva su valor histórico. Para esta propuesta prevalece la preferencia actual del responsable por navegación lateral y degradado discreto. Las reglas de dominio y los ADR aceptados permanecen vigentes.

## Decisiones y puntos por concretar

| Tema | Situación |
| --- | --- |
| Cobertura global y prioridad del catálogo | Aceptadas por el responsable en esta conversación |
| Conservación de paleta y degradado sutil | Aceptada; valores y aplicaciones finales pendientes de maqueta |
| Navegación lateral plegable | Dirección aceptada; anchura y comportamiento pendientes de maqueta |
| Catálogo, trabajo de revisión y segunda revisión | Vistas existentes que se mantienen reconocibles |
| Panel de consulta rápida | Propuesta por comprobar; no sustituye todavía al detalle completo |
| Columnas por nivel farmacéutico | Propuesta; comprobar disponibilidad de datos y legibilidad |
| Exportaciones | La ubicación definitiva debe reconciliarse con el plan de fuentes; conservar enlaces actuales |
| Vistas guardadas, agrupaciones y selección masiva | Opcionales; no se consideran funciones existentes ni compromisos de este rediseño |
| Funciones de fuentes previstas pero incompletas | Diseñar su encaje; habilitarlas sólo mediante sus entregas funcionales |

## Inventario de pantallas y rutas

La cobertura se cierra por pantalla, superficie interna y estado, no contando solamente destinos del menú.

| Pantalla | Rutas actuales | Superficies y acciones que deben cubrirse |
| --- | --- | --- |
| Inicio | `#/`, `#/inicio` | Métricas, etapas, actualización, ayuda de uso y accesos a trabajo |
| Catálogo | `#/fichas`, alias `#/registros` | Búsqueda, orden, libro de origen, nivel farmacéutico, clase comercial, condiciones, archivados, filtros activos, resultados, paginación, apertura y envío a revisión |
| Identidad canónica | `#/catalogo/:id` | Datos editables, fuente original, relaciones, composición, clasificación, archivo, motivo, historial y trabajo de revisión |
| Expediente de revisión | `#/fichas/:id`, `#/registros/:id` | Bloques y ocurrencias, campos, editor, discrepancias, evidencia, procedencia, borradores, guardado y avance |
| Cola | `#/catalogo/trabajo`, `#/revision/cola`, alias `#/cola` | Alta de trabajo, filtros, asignación, transiciones, bloqueo y apertura del registro |
| Segunda revisión | `#/catalogo/segunda`, `#/revision/validaciones`, alias `#/validaciones` | Pendientes, lectura ciega, guardado, discrepancias, conciliación y cerradas |
| Novedades CIMA | `#/novedades`, `#/catalogo/novedades` | Consulta de cambios, detalle, diferencias, versión y acciones de mantenimiento |
| Fuentes | `#/datos/fuentes`, alias `#/fuentes` | Fuentes registradas, detalle, versiones, hojas, exploración de maestros, análisis/carga XLSX, configuración/prueba del Nomenclátor y mantenimiento disponible |
| Importaciones | `#/datos/importaciones`, alias `#/importaciones` | Historial de lotes, estado, responsable, motivo, recuentos por hoja, diagnósticos y detalle |
| Cuarentena | `#/datos/cuarentena`, alias `#/cuarentena` | Listado de incidencias, datos originales, contexto y resolución disponible |
| Exportaciones | `#/exportaciones` | Perfil y alcance, elegibilidad, exclusiones, generación, resultado, errores y descarga |
| Revisores | `#/revisores` | Listado y acciones de mantenimiento disponibles; coherencia con el selector global |
| Ruta desconocida | Cualquier hash no reconocido | Diseñar estado de página no encontrada y retorno; requiere una entrega funcional explícita |

`RecordsWorkspace` representa un patrón compacto de listado y revisión ya documentado, pero no aparece montado directamente por `App.tsx` en la lectura actual. Se evaluará como patrón reutilizable; no se contará como una página adicional disponible sin comprobar su acceso.

## Superficies internas y componentes

| Familia | Cobertura |
| --- | --- |
| Estructura | Marca, navegación, plegado, cabecera contextual, pestañas, revisor, actualización y aviso REAL/DEMO |
| Consulta | Búsqueda, filtros simples y avanzados, chips activos, orden, tablas, acciones de fila, paginación y retorno al listado |
| Edición | Campos de texto, selects, checks, radios, áreas de texto, validación, motivo, cambios sin guardar y conflicto de versión |
| Identidad | Relaciones, composición múltiple, clasificación comercial, condiciones independientes, fuente e historial |
| Revisión | `FieldRow`, `BlockEditor`, ocurrencias repetidas, estados por campo, guardado incremental y atajos |
| Evidencia | `ProvenanceList`, origen, celda y vecinas, fila completa, literal, versión y acceso al documento |
| CIMA | Documento legible, búsqueda por apartado, comparación campo a campo, falta de dato y requiere criterio |
| Equipo | `CatalogReviewPanel`, asignación, bloqueo sin revisor y continuidad hacia la cola |
| Fuentes | Detalle de fuente, carga y vista previa, conexión, prueba, errores, versiones y lotes |
| Resultados | Detalle de importación, detalle de cambio, exclusiones de exportación y resolución de cuarentena |
| Apoyo | Chat contextual con citas, notas de funciones pendientes y ayuda accesible |
| Interacciones | Menús, desplegables, confirmaciones y paneles; diseñar diálogos sólo donde ayuden a la tarea |

## Distribución general propuesta

Barra lateral de aproximadamente 208–224 px desplegada, con marca discreta y nombres visibles. Variante plegada de aproximadamente 56–64 px, con nombres accesibles y ayudas al foco. Son medidas iniciales para maqueta, no especificaciones cerradas.

La cabecera superior contiene ubicación, revisor activo y contexto operativo. Las acciones de la tarea se sitúan junto al contenido que afectan. La búsqueda del catálogo pertenece al catálogo; no se promete un buscador global sin contrato funcional.

La navegación contextual presenta las vistas de cada módulo sin repetir grandes cabeceras. El modo REAL/DEMO permanece visible. Los fallos y bloqueos requieren mensajes específicos; una fecha reciente de importación no demuestra por sí sola que todos los datos estén actualizados.

Propuesta inicial de destinos: Inicio, Catálogo, Novedades CIMA, Datos y Revisores. Exportaciones puede conservar un acceso directo hacia la pestaña correspondiente de Datos. La maqueta comparará esta opción con el destino independiente antes de cerrar la arquitectura; `SOURCE_MANAGEMENT_PLAN.md` propone reunir fuentes, importaciones, exportaciones e historial.

## Primera distribución del catálogo

Esquema de baja fidelidad. Los controles opcionales se distinguen más abajo y sólo aparecerán si están disponibles.

```text
┌──────────────────┬─────────────────────────────────────────────────────┐
│ Farmalidación    │ Catálogo                         Revisor · Modo      │
│                  ├─────────────────────────────────────────────────────┤
│ Inicio           │ Todos los registros · Trabajo · Segunda revisión    │
│ Catálogo         ├─────────────────────────────────────────────────────┤
│ Novedades CIMA    │ Buscar nombre, CN o principio activo                │
│ Datos            │ Nivel · Filtros · Orden                             │
│ Revisores        │ Filtros activos eliminables                         │
│                  ├─────────────────────────────────────────────────────┤
│                  │ Nombre       Identificador   Tipo   Estado  Acción  │
│                  │ Resultado    CN / código     Nivel  Estado  Abrir   │
│                  │ Resultado    CN / código     Nivel  Estado  Abrir   │
│                  │ …                                                   │
│                  ├─────────────────────────────────────────────────────┤
│                  │ Resultados de esta consulta       Página anterior > │
└──────────────────┴─────────────────────────────────────────────────────┘
```

### Búsqueda y filtros

- Búsqueda siempre visible en la zona superior, con un nombre accesible y un alcance explícito.
- Nivel farmacéutico como criterio de exploración; origen como criterio de procedencia separado.
- Mantener acceso a todo el catálogo, sin imponer una vista inicial restringida por una suposición de uso.
- Filtros avanzados en panel plegable. Al abrirlo, la tabla conserva espacio útil; al cerrarlo, el foco vuelve al control de apertura.
- Mostrar condiciones compatibles con el nivel elegido. Mantener la semántica actual de cumplimiento de todas las condiciones seleccionadas.
- Chips activos con eliminación individual y limpieza general. Orden y filtros no deben confundirse.
- Al cambiar criterios, indicar carga sin vaciar bruscamente toda la interfaz ni presentar resultados antiguos como actuales.

### Tabla y densidad

Base común: descripción, identificador, tipo, estado y acciones. La revisión y el origen se mantienen accesibles; su posición final se comprobará con la anchura disponible. Las variantes por nivel sólo incorporarán atributos realmente disponibles.

El nombre tendrá mayor jerarquía que los códigos y etiquetas. Se permitirá texto en varias líneas cuando sea necesario, con acceso al literal completo mediante teclado. La selección y el hover tendrán fondos suaves diferenciados. Los estados incluirán texto.

La primera columna y la cabecera podrán permanecer visibles si la comprobación de desplazamiento lo justifica. No se reducirá la letra para encajar todas las columnas. La paginación mostrará el total de la consulta real; no utilizará un total global como si correspondiera a un subconjunto pendiente.

Agrupar visualmente por autorización o producto es una alternativa futura: sólo usando relaciones existentes y procedencia conocida. No agrupar por parecido del nombre. Sin vínculo confirmado, mostrar la relación pendiente, no construir una jerarquía ficticia.

### Consulta y detalle

Abrir una fila conduce al detalle completo conservando filtros, página, orden y posición del catálogo. La consulta rápida lateral se probará primero en monitor ancho; si comprime demasiado la tabla o necesita demasiadas acciones, se mantendrá la apertura del detalle.

Distribución propuesta del detalle:

```text
Catálogo / nivel / nombre                      Volver · acciones disponibles
Nombre completo · identificadores · estado · situación de revisión

Datos | Relaciones | Fuentes y CIMA | Historial

Contenido activo                              Contexto de fuente/evidencia
Secciones legibles                            Literal y versión
Edición sólo donde corresponde                Comparación y acceso completo
Estado de guardado y mensajes de conflicto
```

Las pestañas son una propuesta de organización. La maqueta comprobará si ocultan información necesaria simultáneamente. Los motivos, errores y cambios sin guardar permanecen junto a la operación. La lectura de fuente original se distingue de la modificación del estado vigente.

### Revisión y segunda revisión

Mantener la relación entre campo activo y evidencia. Evitar que el menú lateral, un listado persistente y la evidencia formen demasiadas columnas estrechas. En portátil se podrá plegar la navegación y el listado; los campos y la evidencia tienen prioridad.

Los bloques repetibles conservan ocurrencias separadas. El avance requiere acción explícita y guardado confirmado. Un error conserva el borrador. La segunda lectura no muestra decisiones del primer revisor antes de la fase permitida; tampoco las revelará una vista rápida, una etiqueta o el chat contextual.

## Reglas visuales iniciales

| Elemento | Propuesta |
| --- | --- |
| Superficies | Blanco para trabajo; gris neutro muy claro para fondo; líneas de baja intensidad |
| Marca | Morado operativo actual; rosa como complemento; degradado existente rosa–violeta |
| Degradado | Marca y un acento pequeño de orientación; sin grandes fondos, tablas ni texto degradado |
| Estados | Éxito, aviso, error e información con su paleta semántica y etiqueta |
| Tipografía | Texto de trabajo inicial de 14–15 px; metadatos de 12–13 px; títulos contenidos de 20–24 px; validar zoom |
| Controles | Altura inicial 36 px; variante más amplia cuando la interacción lo requiera |
| Filas | Densidad inicial aproximada 40–48 px, creciendo para nombres extensos; no fijar altura que recorte contenido |
| Espaciado | Escala común basada en 4 y 8 px |
| Radios y sombras | Radios discretos, sombra limitada a menús y superficies superpuestas |
| Foco | Visible, consistente y separado del estado seleccionado |

Los colores hexadecimales y medidas definitivos se cerrarán después de probar contraste y maquetas. `design-system.css` sobrescribe parte de los tokens históricos: conservar la identidad requiere resolver la paleta efectiva, no copiar sin más el último bloque de `styles.css`.

## Matriz de estados obligatorios

Para cada superficie aplicable, registrar evidencia de estos estados:

| Estado | Qué debe quedar claro |
| --- | --- |
| Primera carga | Qué está cargando y qué controles se pueden usar |
| Actualización | Qué consulta está vigente; evitar saltos de altura innecesarios |
| Sin datos | Qué falta y cuál es la acción disponible |
| Sin resultados | Qué filtros produjeron el vacío y cómo retirarlos |
| Error parcial o total | Qué falló, qué se conserva y cómo reintentar |
| Acción en curso | Evitar envío duplicado y anunciar progreso sin inventar porcentajes |
| Éxito | Qué se guardó o generó y qué sigue disponible |
| Deshabilitado o bloqueado | Razón accesible: revisor, estado, configuración o regla |
| Borrador y salida | Qué queda sin guardar y cómo recuperarlo |
| Conflicto de versión | Rechazo legible, sin sobrescribir ni perder el borrador |
| Fuente ausente o relación desconocida | Ausencia explícita, sin sustitución inferida |
| Archivado | Estado y acceso al historial; no equivalencia con borrado |
| Nombre o evidencia extensos | Lectura completa, sin truncamiento silencioso |
| Menú o panel abierto | Foco, escape cuando proceda y retorno al control |

## Recorridos de aceptación

1. Buscar una presentación por CN, filtrar, abrir su detalle y volver exactamente al contexto anterior.
2. Consultar un medicamento con varias sustancias y recorrer relaciones confirmadas sin fusionarlas.
3. Consultar un resultado sin relación o dato CIMA y entender lo que falta.
4. Corregir un dato con responsable y motivo; distinguir literal, estado vigente e historial.
5. Revisar varias ocurrencias del mismo bloque con evidencia completa y sólo teclado.
6. Guardar y avanzar; simular rechazo, carga tardía y recarga conservando trabajo confirmado y borradores según su contrato.
7. Realizar lectura ciega con otra persona y pasar a conciliación sin filtraciones prematuras.
8. Abrir un cambio CIMA y reconocer versión, fragmento, diferencia y trabajo pendiente.
9. Analizar un XLSX, revisar diagnósticos y consultar el lote; diferenciar aviso, error y cuarentena.
10. Probar una conexión fallida y conservar visible la última carga correcta cuando exista.
11. Preparar una exportación, entender exclusiones y comprobar bloqueo de discrepancias abiertas.
12. Cambiar de revisor, plegar filtros, abrir/cerrar menús y navegar entre secciones conservando foco útil.

## Entregas y puertas de revisión

| Entrega | Resultado | Condición para avanzar |
| --- | --- | --- |
| RD-01 Inventario y distribución | Este documento y cobertura de rutas/superficies | Revisar omisiones y prioridades; auditoría visual actual pendiente |
| RD-02 Línea base visual | Capturas pobladas y estados a resoluciones representativas | Diferenciar datos reales, DEMO y escenarios preparados; documentar cualquier limitación |
| RD-03 Fundamentos y shell | Maquetas de navegación, paleta, tipografía y componentes | Validar legibilidad, degradado, contexto y navegación de Datos/Exportaciones |
| RD-04 Catálogo | Maquetas de listado, filtros y detalle; variante de consulta rápida | Completar recorridos 1–4 y probar nombres largos/composición múltiple |
| RD-05 Revisión | Maquetas de campos, evidencia, errores y segunda revisión | Completar recorridos 5–7 y conservar políticas |
| RD-06 Resto de módulos | Maquetas de Inicio, Novedades, Datos, Exportaciones y Revisores | Completar recorridos 8–12 y matriz de estados |
| RD-07 Cierre del diseño | Matriz de cobertura y decisiones visuales consolidadas | Sin superficies olvidadas; pendientes identificados y alcance de implementación explícito |
| RD-08 Implementación posterior | Cambios pequeños, reversibles y verificados | Requiere autorización posterior para tocar código |

Comprobar inicialmente 1280×720, 1440×900, 1920×1080 y 2560×1440; añadir anchuras reducidas y zoom al 200 %. Son escenarios de comprobación, no una garantía de columnas idénticas. En pantallas pequeñas se preserva el acceso completo mediante reorganización y desplazamiento cuando sea necesario.

Cada entrega de diseño registra lo revisado, lo pendiente y la decisión tomada. La implementación futura incorpora pruebas de comportamiento donde el cambio lo requiera, verificaciones de teclado y capturas comparables; no basta con pasar tests de componentes para declarar validación visual completa.

## Límites y riesgos que se deben conservar visibles

- No cambiar modelo, relaciones, valores, contratos de importación/exportación o políticas clínicas para facilitar el diseño.
- No preseleccionar campos protegidos, ocultar evidencia ni convertir diferencias CIMA en decisiones automáticas.
- No mostrar funciones previstas como disponibles; BOT PLUS, autenticación y reconciliación de nuevas fuentes conservan sus dependencias.
- No inventar DCPF o agrupaciones donde los datos no los proporcionan.
- Distinguir ajustes puramente visuales de mejoras funcionales: ruta desconocida, cambios de foco, nuevas vistas y nuevas acciones requieren alcance y comprobación propios.
- La auditoría anterior ya señaló problemas de foco y teclado. Revalidarlos en la línea base actual antes de considerarlos pendientes o resueltos.
- Hay cambios previos en el árbol de trabajo. Este documento no los modifica ni los da por verificados.

## Estado de esta entrega

Completados: inventario estático inicial, reconciliación con planes existentes, esquema de catálogo y detalle, cobertura de estados, recorridos y secuencia de trabajo.

Pendientes: capturas de la aplicación actual con datos representativos, auditoría visual en ejecución, maquetas de alta fidelidad, medición de contraste y validación de distribución con datos extensos. El próximo paso es RD-02; todavía no comienza implementación.
