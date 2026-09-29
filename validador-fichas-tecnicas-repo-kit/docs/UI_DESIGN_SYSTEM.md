# Base visual de Farmalidación

Estado: primera implementación. Alcance: tokens, shell, navegación, cabeceras, controles, pestañas, badges y tablas compartidas. Las pantallas conservan su estructura y comportamiento; su migración específica sigue `UI_REDESIGN_PLAN.md`.

## Dirección

Interfaz clínica empresarial para sesiones largas: fondo neutro, texto legible, violeta de marca reservado para navegación activa, acción principal y foco. Éxito, aviso, error e información usan colores independientes y siempre se acompañan de texto. Agrupar mediante espacio, tipografía y líneas discretas antes que añadir tarjetas.

## Fuente de verdad

`frontend/src/design-system.css` se importa después de `styles.css` en `main.tsx`. Es la capa de tokens y patrones vigente mientras se migran reglas históricas. Las clases existentes (`.button`, `.field`, `.table`, `.badge`, `.panel`, `.screen__head`) son el contrato de compatibilidad. `PageHeader` inicia la adopción de componentes reutilizables en Inicio.

## Tokens

| Familia | Variables | Uso |
|---|---|---|
| Marca | `--accent`, `--accent-strong`, `--accent-soft`, `--focus-ring` | Acción principal, activo y foco |
| Neutros | `--ink`, `--ink-soft`, `--ink-faint`, `--surface`, `--canvas`, `--line`, `--line-soft` | Jerarquía y separación |
| Estado | `--success`, `--warn`, `--danger`, `--info` y pares `-soft` | Estado semántico |
| Espacio | `--space-1/2/3/4/5/6/8` | 4, 8, 12, 16, 20, 24, 32 px |
| Forma | `--radius-small`, `--radius-control`, `--radius`, `--shadow` | Radios 4, 6, 8 px; sombra mínima |
| Tipo | `--text-xs/sm/base/lg/title`, `--weight-*`, `--line-*` | Metadatos, cuerpo y encabezados |
| Capas | `--z-sticky`, `--z-popover`, `--z-dialog` | Elementos superpuestos |

## Patrones

- Shell compacto con navegación subrayada, fecha de datos y selector de revisor integrados. Contenedor de hasta 1600 px; el catálogo mantiene su layout de alto completo.
- Botones y controles de altura mínima 36 px, radio 6 px, foco visible de 2 px y disabled legible. Los controles nativos preservan semántica y teclado.
- Pestañas de `SectionWorkspace` conservan enlaces y `aria-current` y marcan el activo con línea inferior.
- Badges, alertas y modo REAL/DEMO mantienen etiquetas textuales; el color sólo complementa.
- Tablas con números tabulares, filas compactas, hover tenue y cabecera clara. El catálogo conserva sticky header y scroll. El truncado requiere decidir por columna qué puede recortarse y cómo mostrar el literal completo de forma accesible.
- `AsyncBoundary` sigue siendo el patrón común de carga, error y vacío; `FilterWorkspace` conserva su estado persistente.

## Componentes aplazados

No se añaden `Switch`, `SegmentedControl`, `Tooltip`, `Popover`, `Dropdown`, `Modal`, `Toast`, `Skeleton`, `Drawer` ni `Breadcrumb`: aún no hay un caso compartido que justifique definir su API. `ReviewerSelect` ya cubre su menú específico. Se introducirán cuando una pantalla real los necesite, con contrato de teclado y accesibilidad.

## Regla de migración

Por pantalla: revisar 1440×900, 1920×1080 y 2560×1440, recorrer con teclado, validar carga/error/vacío y mantener rutas, filtros, evidencias, decisiones y resultados. Retirar CSS histórico sólo cuando no tenga consumidores.
