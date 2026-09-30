# Sistema visual de Farmalidación

Estado: consolidado tras la migración y la fase de UI polish. La fuente de verdad es `frontend/src/design-system.css`, importada después de `styles.css` desde `main.tsx`. Las reglas históricas con consumidores activos permanecen por compatibilidad.

## Dirección

Interfaz clínica para sesiones largas: fondo neutro, texto legible y morado reservado para navegación activa, acción principal y foco. Éxito, aviso, error e información tienen colores semánticos y etiquetas textuales. La agrupación se resuelve con espacio, tipografía y líneas discretas.

## Tokens vigentes

| Familia | Variables | Uso |
|---|---|---|
| Marca | `--accent`, `--accent-strong`, `--accent-soft`, `--focus-ring` | Acción principal, activo y foco |
| Neutros | `--ink`, `--ink-soft`, `--ink-faint`, `--surface`, `--canvas`, `--line`, `--line-soft` | Jerarquía y separación |
| Estado | `--success`, `--warn`, `--danger`, `--info` y pares `-soft` | Estado semántico |
| Espacio | `--space-1/2/3/4/5/6/8` | 4, 8, 12, 16, 20, 24, 32 px |
| Forma | `--radius-small`, `--radius-control`, `--radius`, `--shadow` | Radios 4, 6, 8 px; sombra mínima |
| Tipo | `--text-xs/sm/base/lg/title`, `--weight-*`, `--line-*` | Metadatos, cuerpo y encabezados |
| Capas | `--z-sticky`, `--z-popover` | Cabeceras y menús |

## Patrones definitivos

- Shell y navegación compactos en 1280 px; el contenido puede crecer hasta 2200 px en pantallas anchas. En resoluciones intermedias se conserva el acceso a todas las secciones.
- Controles de altura mínima 36 px y foco visible sólido de 2 px. Los campos de texto sin atributo `type` comparten el mismo borde y fondo que los campos explícitos.
- Botones con jerarquía primaria, secundaria y discreta. Disabled conserva legibilidad. No se añadieron animaciones decorativas.
- Filtros del catálogo en dos columnas para las opciones de condición; filtros activos se muestran junto a resultados. Al retirar un filtro activo, el foco vuelve al encabezado de resultados.
- Tablas con cabeceras sin mayúsculas forzadas, números tabulares alineados a la derecha y filas compactas. El catálogo conserva la cabecera sticky y el desplazamiento horizontal.
- Carga de resultados con altura estable y superficie neutra para reducir saltos de layout. Vacíos y errores conservan textos útiles y sobrios.
- `PageHeader`, `SectionWorkspace`, `AsyncBoundary` y `FilterWorkspace` son los patrones compartidos. Los estados semánticos siempre incluyen texto.

## Revisión de pantallas

Se revisaron Inicio, Catálogo, Novedades CIMA, Cola, Segunda revisión, Fuentes, Importaciones, Cuarentena, Exportaciones, Revisores, expediente de revisión e identidad canónica a nivel de estructura y estilos. La Cola se inspeccionó visualmente a 1280×720, 1440×900, 1920×1080 y 2560×1440; se comprobó la navegación y el formulario de alta a 1280 px. Catálogo, Novedades CIMA, Exportaciones y Revisores se inspeccionaron visualmente a 1440×900. Se ajustaron navegación, icono del buscador, densidad de filtros, anchura del formulario de exportación, números y estados de carga. Se retiraron reglas CSS sin consumidores comprobados y dos tokens no utilizados. No se modificaron reglas clínicas ni llamadas de negocio.

El backend no estuvo disponible y Docker Desktop no respondió durante esta revisión. Por ello, las capturas verifican shell y estados de carga/error; las tablas pobladas y los diálogos no pudieron contrastarse visualmente con datos reales a las cuatro resoluciones. Sus flujos se cubren con pruebas de componentes. No se debe interpretar esta limitación como validación visual completa de datos poblados.

## Incidencias funcionales preexistentes observadas

Estas incidencias requieren una tarea funcional/accesibilidad separada, pues no se ha acreditado que sean regresiones del rediseño:

- `ReviewerSelect` abre con flecha abajo, pero no ofrece navegación completa de opciones con teclado ni restitución del foco al cerrar.
- Al plegar `FilterWorkspace`, el botón que tiene el foco se desmonta y el foco se pierde.
- El editor de segunda revisión ciega aparece sin mover el foco al nuevo contexto.
- El expediente de revisión añade una parada de tabulación por envoltorio de campo; algunos desplegables anuncian expansión sin vincular el contenido con `aria-controls`.

## Verificación

Pruebas, lint, typecheck y build del frontend ejecutados al cierre de esta fase. El CSS legado con posibles consumidores dinámicos se conserva deliberadamente.
