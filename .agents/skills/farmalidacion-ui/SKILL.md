---
name: farmalidacion-ui
description: "Sistema visual de Farmalidación: identidad decidida, capas CSS y tokens, componentes comunes (FilterBar, estados, distintivos), voz de los textos y verificación con capturas. Cárgala para cualquier cambio de pantalla, estilo o texto de la interfaz."
---

# farmalidacion-ui

Todas las rutas son relativas a `validador-fichas-tecnicas-repo-kit/frontend/src/`.

## Identidad (decidida; no se rediscute)

- Herramienta profesional de validación farmacéutica: sobria, precisa, con aire de documento técnico. **Identidad propia**: nada calcado de otras apps y nada que delate «hecho por IA» (degradados decorativos, tarjetas redondeadas para todo, sombras difusas, emojis, iconos de chispa, textos de relleno, todo centrado).
- **Tres letras** (servidas con `@fontsource`, sin red): IBM Plex Sans (interfaz), Newsreader (títulos de página, de sección y de recuadro), IBM Plex Mono (códigos, CN, versiones, literales de origen, cifras).
- **Todo sobre el mismo papel**: recuadros y tablas comparten el fondo cálido (`--surface` = `--canvas`) y se separan con líneas. Solo es blanco (`--field`) donde se escribe o se elige.
- **Violeta solo con intención**: acción principal, selección, campo activo, filtro aplicado.
- Estados: un tono por significado y siempre con texto (sin empezar = neutro, en curso = acento, corregido = información, resuelto = éxito, requiere atención = aviso, fallo = peligro).

## Dónde va cada cosa

| Capa | Fichero | Regla |
|---|---|---|
| Tokens | `ui/tokens.css` | Única definición de variables en `:root` (claro, oscuro, densidad compacta). |
| Componentes comunes | `ui/components.css` | Botones, campos, distintivos, tablas, estados, pestañas, diálogo. |
| Estructura | `ui/shell.css` | Barra lateral, barra superior, pantalla de acceso. |
| Filtros | `ui/filters.css` + `components/FilterBar.tsx` | La única forma de filtrar. |
| Por pantalla | `screens/{catalog,work,sources,review}.css` | Lo propio de una pantalla. Se importan en `main.tsx` tras los comunes. |
| Históricas | `styles.css`, `studio.css` | **Solo se vacían**, nunca se les añade nada. |

- Un CSS importado desde un componente se carga **antes** que las hojas históricas y pierde: las hojas nuevas se importan en `main.tsx`.
- Sin colores ni tamaños de letra escritos a mano en las hojas nuevas: `styles.test.ts` lo comprueba. Si falta un valor, se crea el token.
- Controles a la misma altura: `--control-height` (36/32 px) y `--control-height-sm` (28 px). Recuadros con `--panel-pad`.

## Patrones

- **Filtros:** `FilterBar` con `search` (buscador y orden), `aside` (controles de vista) e hijos `FilterSelect` / `FilterChecks` / `FilterText` / `FilterToggle`. Se aplican al momento (el texto, con Intro o al salir); `name` lleva el nombre accesible completo y `label` el texto corto visible. Nada de paneles laterales ni botón «Aplicar».
- **Estados:** `LoadingState` (esqueleto), `EmptyState` (título + explicación + salida), `ErrorState` (con «Reintentar»). Un estado vacío dentro de un recuadro no dibuja otra caja.
- **Distintivos:** `badge badge--<estado>`; el mapa de tonos vive en `ui/components.css`.
- **Cabeceras:** `PageHeader` (antetítulo, título, descripción, acciones). Cifras en `--font-ui`; los numerales de Newsreader confunden el 0 con la O.
- **Iconos:** `lucide-react`, nunca caracteres sueltos (◷, ✓, ⌕).

## Voz

Castellano, tratando de **tú**, frases cortas, vocabulario del dominio (`domain/vocabulary.ts`, `domain/fieldLabels.ts`). Los avisos de falta de identidad dicen dónde resolverlo: «Identifícate en Equipo y preferencias para…». Nunca se muestra un error técnico en inglés: `api/client.ts` traduce los genéricos del servidor.

## Verificar un cambio visual

Con el backend (DEMO) y `npx vite --port 5173` en marcha, desde `validador-fichas-tecnicas-repo-kit/`:

```bash
REVIEWER=jlopez node scripts/ui/capturar.mjs light <antes> fichas trabajo datos/fuentes   # antes del cambio
REVIEWER=jlopez node scripts/ui/capturar.mjs light <despues> fichas trabajo datos/fuentes  # después
node scripts/ui/comparar.mjs <antes> <despues> light-fichas.png light-trabajo.png …
```

- Repite en `dark`, a 390 px (`WIDTH=390 HEIGHT=844`) y con `CLICK=".catalog-row__name"` para el diálogo del expediente.
- Una limpieza sin cambio visible debe dar capturas **idénticas**; el panel de filtros y algunos botones tienen ruido de animación: repite la captura antes de dar por real una diferencia pequeña.
- `node scripts/ui/auditar-controles.mjs <rutas>` agrupa variantes de botones, campos y recuadros: útil para detectar piezas que deberían ser la misma.
- Tests, lint y build siguen siendo obligatorios: `npx vitest run`, `npm run lint`, `npm run build`.

## Con `ui-ux-pro-max`

Sirve para revisar accesibilidad, contraste, interacción y formularios. Sus recomendaciones de estilo, paleta o tipografía no sustituyen esta identidad.
