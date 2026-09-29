# Auditoría final del rediseño de Farmalidación

Fecha: 29-09-2026. Alcance: revisión de las rutas del frontend, componentes compartidos, estilos vigentes y pruebas existentes desde las perspectivas de diseño de producto, ingeniería frontend y uso farmacéutico prolongado. No se modificó código.

## Método y límites de la evidencia

Se contrastaron los hallazgos con JSX, CSS y pruebas de componentes. La revisión visual disponible de la fase anterior cubre la Cola a 1280×720, 1440×900, 1920×1080 y 2560×1440, y Catálogo, Novedades CIMA, Exportaciones y Revisores a 1440×900. Esa revisión mostró shell y estados de carga/error. El backend no estuvo disponible y Docker Desktop no respondió: no hay comprobación visual con tablas pobladas, expedientes reales ni diálogos en las cuatro resoluciones. Las observaciones que dependen de esos estados se señalan como inferencias del código, no como defectos visuales observados. No se ha medido contraste WCAG automáticamente ni se ha hecho una sesión con usuarios farmacéuticos.

La clasificación describe el impacto esperado, no atribuye automáticamente cada problema al rediseño. **P0: ninguno confirmado.** La revisión no encontró una ruta demostrada que guarde una propuesta sin evidencia, preseleccione un campo protegido o exporte una discrepancia sin resolver.

## Hallazgos

### P1 — importantes

| Ruta | Componente | Problema y evidencia | Impacto | Recomendación concreta |
|---|---|---|---|---|
| Global, todas las rutas | `ReviewerSelect` (`frontend/src/components/ReviewerSelect.tsx`) | El botón con rol `combobox` abre una lista de botones con rol `option`, pero sólo gestiona Escape y ArrowDown para abrir; no mueve el foco ni ofrece ArrowUp/ArrowDown para recorrer opciones, Home/End o selección con Enter desde el disparador. Al elegir o cerrar, tampoco restituye explícitamente el foco. | La selección de quién firma decisiones, operación transversal y de seguridad, resulta impredecible con teclado y lector de pantalla. Contradice el requisito de revisión completa con teclado. | Usar un `<select>` nativo si cubre el caso, o implementar el patrón completo de listbox: opción activa, navegación, selección, Escape y retorno del foco; añadir prueba de teclado real. |
| `/fichas` y `/revision/cola` | `FilterWorkspace` (`frontend/src/components/FilterWorkspace.tsx`) | El botón «Ocultar filtros» está dentro del panel que se oculta y se desmonta al pulsarlo; el botón «Mostrar filtros» se monta como otro nodo. No hay transferencia de foco entre ambos. | La persona pierde su posición de teclado tras plegar filtros; en sesiones largas obliga a volver a recorrer la página. | Mantener un único disparador persistente o mover el foco al botón recién montado al cerrar y devolverlo al control equivalente al abrir. Probar Tab/Shift+Tab y lector de pantalla. |
| `/revision/validaciones` | `SecondReviewScreen` (`frontend/src/screens/SecondReviewScreen.tsx`) | «Revisar a ciegas» inserta el editor en otra columna después de una respuesta asíncrona, sin foco, anuncio de región ni desplazamiento al nuevo contenido. El control que inició la acción conserva el foco en la lista. | El farmacéutico puede no detectar que ya se cargó el campo y seguir en la lista; dificulta la segunda lectura con teclado. | Al completar la carga, anunciar el campo y enfocar el encabezado o primer control del editor; al cancelar o registrar, devolver el foco al elemento de origen o a un destino estable. |
| `/revision/cola` | `QueueScreen` (`frontend/src/screens/QueueScreen.tsx`) | Si una consulta filtrada devuelve cero elementos, `items.length === 0` hace aparecer «La cola está al día» y el texto de ausencia de registros. El estado «No hay resultados» sólo se muestra si `items.length > 0`, imposible cuando `visibleItems = items` y la respuesta filtrada es vacía. | Comunica falsamente que no hay trabajo pendiente cuando el filtro simplemente no coincide; puede hacer que se abandone una tarea. | Distinguir «cola global vacía» de «filtro aplicado sin coincidencias» usando el estado de filtros realmente aplicado; ofrecer limpiar filtros desde ese vacío. |
| `/fichas` | `RealRecordListScreen` (`frontend/src/screens/RealRecordListScreen.tsx`) | El vacío se decide por `data.total === 0`, pero el título «No hay identidades en este nivel» y el detalle «todavía no se ha podido proyectar desde una fuente fiable» se usan también si hay condiciones, clase, archivados o libro que dejan cero resultados sin texto de búsqueda. | El mensaje atribuye a falta de datos fiables lo que puede ser una combinación de filtros demasiado restrictiva. Es una explicación equivocada en una herramienta de procedencia de datos. | Diferenciar catálogo realmente vacío, nivel vacío y filtros sin coincidencias; mostrar filtros activos y una acción para limpiarlos. |

### P2 — mejoras

| Ruta | Componente | Problema y evidencia | Impacto | Recomendación concreta |
|---|---|---|---|---|
| `/revision/cola` frente a `/fichas` | `QueueScreen` y `RealRecordListScreen` | Catálogo aplica de inmediato chips, checks y orden, pero exige «Buscar» para texto; Cola exige «Aplicar filtros» y también ofrece «Actualizar», que recarga con los valores editados aunque aún no se hayan aplicado. El contador de filtros de Cola cuenta el borrador, no necesariamente la consulta que produjo la lista. | Hay dos modelos de interacción para filtros similares y el usuario no puede saber con certeza si la lista refleja los controles visibles. | Definir un único contrato: filtros inmediatos o borrador/aplicación explícita. Si se conserva aplicación explícita, separar y etiquetar filtros editados y aplicados; «Actualizar» debe repetir la consulta aplicada. |
| `/revision/cola` | `QueueScreen` | Tras un fallo de carga, se muestra una alerta que dice «Recargue para consultar el estado actual», mientras la lista anterior puede seguir visible y el contador conserva `items.length`. No se marca ese contenido como potencialmente obsoleto. | Un farmacéutico puede interpretar la lista anterior como estado actual después de una operación o consulta fallida. | Mantener el resultado previo sólo si se etiqueta claramente como última carga correcta, con hora o estado «no actualizado», y ofrecer una acción de reintento junto a la alerta. |
| `/registros/:id` | `ReviewScreen` y `FieldRow` | Cada campo tiene un envoltorio `tabIndex={0}` antes de sus botones y controles internos. Además, los botones que abren edición, estructura y ayuda declaran `aria-expanded` sin `aria-controls` que identifique el contenido. | La tabulación añade una parada por cada campo, costosa en expedientes largos; las regiones expandidas son menos fáciles de relacionar con su disparador. | Usar navegación entre campos con flechas o un único punto de entrada por región, preservando los atajos existentes; asignar IDs estables y `aria-controls` a cada desplegable. |
| `/fichas` | `RealRecordListScreen` | La región «Tabla de registros» recibe `tabIndex={0}` siempre, aunque no haya desbordamiento horizontal. La tabla tiene un ancho mínimo de 820 px y la primera columna de 260 px; el foco adicional no depende de que exista scroll real. | Se añade una parada de teclado incluso cuando no hace falta desplazarse. El comportamiento visual con nombres muy largos sigue pendiente de verificar. | Hacer focalizable la región sólo cuando desborde y validar anchuras con nombres y códigos máximos reales. |
| Global | `styles.css` + `design-system.css` | La capa nueva se importa después de reglas históricas y vuelve a definir patrones activos. Ejemplo: el primer `filter-choice-list` del libro usa tres columnas en `styles.css`, mientras `design-system.css` lo redefine a dos; el resultado depende del orden de carga. También hay reglas duplicadas de topbar, tablas y paneles. | Cada ajuste posterior obliga a rastrear cascadas en dos archivos y aumenta el riesgo de regresiones de 1–2 px o de estados responsivos. | Inventariar selectores usados con pruebas/recorrido de rutas y consolidar los patrones activos en una sola ubicación por componente, retirando sólo reglas demostrablemente obsoletas. No hacer borrado masivo. |
| `/revision/validaciones` | `SecondReviewScreen` | Las listas de pendientes, discrepancias y cerradas muestran el identificador del registro como dato principal; la fila no incluye el nombre del campo aunque el editor trabaja un campo concreto. | Cuando hay varias asignaciones del mismo registro, cuesta distinguir qué lectura abrir y recordar cuál se completó. | Mostrar el campo o un resumen estable de la asignación junto al identificador, siempre que el endpoint ya lo entregue; si no, planificar el dato en la API antes de cambiar el diseño. |

## Cobertura por ruta

| Ruta o grupo | Revisado | Límite o resultado |
|---|---|---|
| Inicio | Estructura, métricas y estilos | Sin hallazgo suficientemente verificado; métricas pobladas pendientes de inspección visual. |
| Catálogo | Filtros, carga, tabla, paginación y pruebas | Dos mensajes de vacío y densidad/truncado requieren atención; tabla poblada pendiente de inspección visual. |
| Novedades CIMA | Estructura y estado visible a 1440 px | Sin hallazgo confirmado; diff con documentos reales pendiente de inspección visual. |
| Cola | Shell a cuatro resoluciones, filtros y estados por código | Estado vacío filtrado incorrecto y modelo de aplicación de filtros confuso. |
| Segunda revisión | Flujo y estructura por código | Foco del editor y diferenciación de asignaciones. |
| Fuentes, Importaciones, Cuarentena | Tablas, formularios y estados por código | Sin hallazgo suficientemente verificado; datos y desbordamientos reales pendientes de inspección visual. |
| Exportaciones | Formulario y estado visible a 1440 px; historial por código | Sin hallazgo confirmado; historial poblado y exclusiones pendientes de inspección visual. |
| Revisores | Formulario y estado visible a 1440 px; tabla por código | Selector global de revisor afecta a este flujo; tabla poblada pendiente de inspección visual. |
| Expediente de revisión e identidad canónica | Estructura de campos, evidencia y controles por código | Tabulación del expediente; estados poblados pendientes de inspección visual. |

## Orden recomendado

1. Resolver los P1 que afectan a firma, teclado y estados vacíos engañosos.
2. Unificar el contrato de filtros y revisar los flujos poblados con datos representativos de farmacia durante una jornada de trabajo.
3. Consolidar CSS activo después de capturar referencias visuales y pruebas de regresión de las cuatro resoluciones.


## Seguimiento de correcciones — 29-09-2026

### P0/P1

- **P0:** no había ninguno confirmado.
- **P1 · selector de revisor:** navegación de opciones con flechas, Inicio/Fin, selección con Intro/Espacio, Escape y foco conservado en el disparador. Prueba de teclado añadida.
- **P1 · panel de filtros:** al plegar o desplegar, el foco pasa al botón equivalente que queda visible. Prueba de ambos sentidos añadida.
- **P1 · segunda revisión:** al cargar la lectura ciega, el foco pasa al encabezado del editor; al cancelar vuelve a la asignación; al registrar pasa a un encabezado estable de la lista. Pruebas de apertura y cancelación añadidas.
- **P1 · cola vacía:** la pantalla distingue respuesta global vacía de respuesta filtrada sin coincidencias según los filtros de la consulta aplicada y ofrece limpiar filtros. Prueba de ambos estados añadida.
- **P1 · catálogo vacío:** mensaje y acción de limpieza específicos cuando los filtros generan cero resultados; mensaje de catálogo sin datos cuando no hay filtros. Prueba añadida.

### P2 dentro del alcance

- **Parcial · expediente de revisión:** los controles expandidos de campo, estructura y atajos enlazan el contenido visible con `aria-controls`. Se conserva la navegación actual; reducir la cantidad de paradas Tab exige diseñar otro patrón de teclado y queda pendiente.
- **Parcial · CSS duplicado:** se retiró la regla de tres columnas del primer grupo de filtros, que quedaba sobreescrita por la regla vigente de dos columnas. La consolidación general requiere inventario visual de estados poblados y queda pendiente.

### P2 aplazados por el límite solicitado

- Contrato de aplicación de filtros Catálogo/Cola: requiere decidir y cambiar comportamiento.
- Marcado de datos obsoletos tras fallo de la Cola: requiere modelo de último resultado válido y reintento.
- Tabulación condicional de tabla de Catálogo: requiere detección de desbordamiento y validación con datos reales.
- Nombre del campo en las listas de segunda revisión: el endpoint de resumen no lo entrega; requiere cambio de API.

No se corrigieron P3. Los datos poblados y diálogos siguen pendientes de verificación visual con backend operativo. Las correcciones de este seguimiento no alteran reglas clínicas, decisiones ni exportación.

### Resultado de validación de esta corrección

- Frontend: 149/149 pruebas, ESLint, TypeScript y build Vite correctos.
- Backend: Ruff correcto; `docker compose config --quiet` correcto; Alembic `upgrade head` y `downgrade base` correctos sobre base temporal.
- Suite Python completa: **774 passed, 1 skipped, 3 failed**. Dos fallos en `backend/tests/test_maintenance_job.py` proceden de un doble `ChangesClient` sin método `medication`; el tercero, en `backend/tests/test_medication_importer.py`, compara un hash de maestro local diferente del esperado. Ninguno toca archivos modificados en esta corrección.
- Mypy: cinco errores en `cima_comparison.py`, `catalog_api.py` y `maintenance_job.py`, todos fuera de los archivos modificados.
- `scripts/verify_reference_files.py`: ocho originales locales faltantes. El gate integral no puede declararse verde en este entorno. No se modificaron tests backend ni originales para ocultar estos resultados.
