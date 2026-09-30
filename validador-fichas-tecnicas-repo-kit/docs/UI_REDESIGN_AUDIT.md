# Auditoría UI para el rediseño visual de Farmalidación

Fecha: 2026-09-29. Alcance: frontend existente en `frontend/src`; análisis estático, sin cambios de interfaz. Producto interno de trabajo farmacéutico. La especificación v2 y las decisiones aceptadas conservan prioridad sobre cualquier propuesta visual.

## Arquitectura y mapa de rutas

React 19, TypeScript 6 y Vite 8. `main.tsx` monta `App.tsx`; no hay React Router ni Tailwind. `navigation.ts` interpreta `location.hash`; `App.tsx` contiene layout, navegación principal y despacho de pantallas. `SectionWorkspace` aporta pestañas secundarias. `api/client.ts` y `api/useQuery.ts` concentran acceso a datos; `domain/` contiene formatos, borradores, foco y atajos. Estilos en `styles.css` y `review-workspace.css`.

| URL hash | Pantalla | Acceso |
|---|---|---|
| `#/`, `#/inicio` | DashboardScreen | Inicio |
| `#/fichas` | RealRecordListScreen | Catálogo |
| `#/fichas/:id`, `#/registros/:id` | ReviewScreen, expediente y editor de campos/bloques | Listado/enlace profundo |
| `#/catalogo/:id` | CatalogIdentityScreen, identidad canónica y edición | Listado/enlace profundo |
| `#/catalogo/novedades`, `#/novedades` | MaintenanceScreen, novedades CIMA y detalle de cambio | Navegación principal |
| `#/revision/cola`, `#/cola` | QueueScreen | Revisión/pestaña |
| `#/revision/validaciones`, `#/validaciones` | SecondReviewScreen | Revisión/pestaña |
| `#/datos/fuentes`, `#/fuentes` | SourcesScreen y detalle de fuente | Datos/pestaña |
| `#/datos/importaciones`, `#/importaciones` | ImportsScreen y detalle de importación | Datos/pestaña |
| `#/datos/cuarentena`, `#/cuarentena` | QuarantinedRecordsScreen | Datos/pestaña |
| `#/exportaciones` | ExportsScreen, exclusiones y resultados | Navegación principal |
| `#/revisores` | ReviewersScreen | Navegación principal |
| `#/registros` | Alias del listado `#/fichas` | Compatibilidad |
| Cualquier otra ruta | Sin pantalla; `parseRoute` devuelve `seccion` | Estado no encontrado sin UI explícita |

No se detecta otra ruta administrativa. Hay superficies internas sin URL propia: `SourceDetail`, `ImportDetail`, `ChangeDetail`, `Exclusions`, `BlockEditor`, `FieldRow`, `SourceFieldsMaintenance`, `CatalogCimaDocumentReader` y `CatalogCimaComparisonPanel`. Deben entrar en el inventario de capturas y pruebas; no asumir que toda superficie sea un modal.

## Mapa de componentes

| Capa | Componentes y función |
|---|---|
| Shell | `App`, `ModeBanner`, `ReviewerSelect`, `SectionWorkspace` |
| Consulta | `DashboardScreen`, `RealRecordListScreen`, `SourcesScreen`, `ImportsScreen`, `MaintenanceScreen`, `ExportsScreen` |
| Trabajo farmacéutico | `ReviewScreen`, `FieldRow`, `BlockEditor`, `SecondReviewScreen`, `QueueScreen`, `QuarantinedRecordsScreen` |
| Catálogo canónico | `CatalogIdentityScreen`, `SourceFieldsMaintenance`, `CatalogCimaDocumentReader`, `CatalogCimaComparisonPanel` |
| Soporte | `FilterWorkspace`, `AsyncBoundary`/`LoadingState`/`ErrorState`/`EmptyState`, `ValidationBadge`/`ReviewBadge`/`SoonBadge`, `OriginBadge`, `ProvenanceList`, `ContextualChat`, `RoadmapNote` |

Las clases `.button`, `.field`, `.panel`, `.table`, `.badge`, `.alert`, `.chip`, `.pagination` y `.screen` son reutilizables por CSS, pero no forman aún primitivas React con variantes y contratos accesibles. `ReviewerSelect` ya encapsula un selector complejo; `FilterWorkspace` conserva apertura en `localStorage`; `AsyncBoundary` centraliza tres estados. Tablas, paginación, botones, campos, paneles, alertas y cabeceras se componen directamente en pantallas. No se encontró un sistema de tooltips compartido ni diálogos nativos compartidos; `title` se usa puntualmente. Los detalles se muestran dentro de la pantalla.

## Hallazgos visuales y deuda UI

1. **Capas históricas de estilo.** `styles.css` redefine `:root` en varias zonas (verde inicial, azul y magenta posteriores) y vuelve a declarar botones, navegación, campos, paneles y tablas. El resultado depende de la cascada y dificulta saber qué token está activo. `review-workspace.css` usa variables antiguas o de respaldo (`--muted`, `--border`) distintas de las globales.
2. **Lenguaje visual inestable.** Radios observados de 3 a 15 px y píldoras, sombras de varios tamaños, gradientes en navegación/botón principal/métricas y colores literales. No hay escala única de espacio, tipografía, elevación y densidad. Predomina la estructura de paneles con borde, incluso para pares simples de datos.
3. **Densidad desigual.** El ancho `.screen` queda limitado a 1180 px: en 1920 y 2560 px deja mucho espacio libre mientras tablas y revisión necesitan ancho. Paneles y cabeceras consumen altura; listas y formularios usan densidades diferentes. El editor de revisión sí reserva columna persistente de evidencia, una buena base a conservar.
4. **Jerarquía.** `eyebrow`, título, `lede`, paneles y avisos se repiten; ayudan a orientar, pero en pantallas largas compiten con el dato operativo. Métricas del inicio y múltiples tarjetas pesan más que tareas pendientes. Estados y procedencia textual ya aportan jerarquía clínica útil.
5. **Duplicación.** Hay variantes de botones, filtros, tablas y estados vacíos implementadas por clase y por pantalla. Colores `#...`, paddings y radios aparecen también fuera de tokens. Las tablas de fuentes, importaciones, cola, validaciones y catálogo requieren auditoría de columnas y acciones antes de unificar presentación.
6. **Navegación.** El shell horizontal y las pestañas son comprensibles. `activeNavId` conserva contexto de secciones; sin embargo, una ruta desconocida queda en blanco y algunos detalles internos no tienen enlace directo. La navegación principal usa botones que cambian el hash, mientras la secundaria usa enlaces.

### Accesibilidad y responsive

Fortalezas comprobadas en código: `main` y `nav` con nombre, `aria-current`, etiquetas en muchos formularios, `role=status/alert` en estados compartidos, indicador textual REAL/DEMO, y estilos `:focus-visible`. La revisión tiene utilidades de foco y atajos en `domain/shortcuts.ts`; conservar su orden y significado.

Riesgos a validar con navegador: contraste de texto tenue (`--ink-faint`), badges y disabled sobre fondos claros; foco en `textarea`, enlaces y controles personalizados en todas las capas; tamaño de chips, iconos y acciones de fila; nombres accesibles de controles repetidos; comportamiento del selector de revisor, filtros ocultables y detalles abiertos con teclado. `review-workspace.css` contiene `--focus-ring` sin definición en su regla de foco específica. No se ha medido contraste ni realizado auditoría automática/manual de accesibilidad en esta fase.

Hay cortes CSS a 1180, 1100, 1000, 900, 860, 820, 720, 560 y 320 px. Se priorizan capturas y pruebas a 1440×900, 1920×1080 y 2560×1440; verificar después 1100/900/720 px para desbordamiento, tablas, filtros y columna de evidencia. Esta auditoría estática no acredita un resultado visual renderizado.

## Propuesta de design system

- **Tokens semánticos únicos:** superficies, texto primario/secundario, líneas discretas, acción, estados clínicos, foco, espaciado de 4/8 px, tipografía, radios y anchuras. Mantener etiquetas de estado junto al color y distinguir DEMO/REAL de forma visible.
- **Primitivas prioritarias:** `Button`, `IconButton`, `Field`/`TextInput`/`Select`/`Textarea`, `StatusBadge`, `Alert`, `PageHeader`, `Panel` sobrio, `DataTable`, `Pagination`, `FilterBar`/`FilterWorkspace`, `EmptyState`/`LoadingState`/`ErrorState`, `Tabs`, `DescriptionList`, `EvidencePanel` y confirmación de acción. Primero fijar contratos, estados, densidades y accesibilidad; después migrar usos.
- **Patrones específicos:** expediente con evidencia simultánea y estado de guardado; fila de campo y bloque repetible; comparación CIMA; procedencia literal/versionada; cola y discrepancia de segunda revisión. Estos patrones conservan comportamiento y no deben simplificarse a tarjetas genéricas.
- **Dirección visual:** neutros cálidos o fríos discretos, un acento sobrio, tipografía legible durante jornadas largas, separadores por agrupación en vez de borde en cada elemento, sin gradientes decorativos ni sombras grandes. Densidades compacta/regular explícitas para datos y formularios.

## Orden de impacto y estrategia de migración

1. Shell, navegación, tokens y estados compartidos: afectan a todas las rutas.
2. Catálogo/listados, filtros y tablas: alto uso y mayor beneficio de densidad.
3. Expediente `ReviewScreen`, `FieldRow`, `BlockEditor` y evidencia: máximo riesgo funcional; migración por secciones pequeñas.
4. Cola y segunda revisión; mantener estados, asignaciones y discrepancias.
5. Identidad canónica, campos fuente, CIMA y novedades.
6. Fuentes, importaciones, cuarentena, exportaciones y revisores.
7. Inicio: ajustar a señales operativas reales después de fijar patrones de trabajo.

Migrar por capas: congelar capturas y recorridos actuales; consolidar tokens sin alterar lógica; introducir primitivas compatibles; migrar pantalla por pantalla; comparar capturas y teclado; retirar CSS histórico sólo cuando no tenga consumidores. Mantener rutas y alias. Ninguna fase toca API, datos, reglas, importación/exportación o auditoría.

## Riesgos funcionales y checklist de no regresión

- [ ] Rutas principales y alias antiguos abren la misma pantalla; navegación atrás/adelante y enlaces profundos funcionan.
- [ ] Selección declarada de revisor persiste y condiciona las acciones igual que antes.
- [ ] Modo REAL/DEMO, fecha de actualización, carga, vacío y error siguen inequívocos.
- [ ] Filtros, orden, paginación, búsqueda y estado conservado del catálogo mantienen resultados.
- [ ] Teclado completo de revisión, foco visible, atajos y guardado/borradores permanecen intactos.
- [ ] Evidencia literal, versión documental y procedencia se ven junto al campo pertinente.
- [ ] Campos `proponer_opciones`/`solo_evidencia` no adquieren preselección; no se ocultan conflictos ni incertidumbre.
- [ ] Bloques repetibles, orden, fusión, motivos y estados `no_aplica` conservan todas las ocurrencias.
- [ ] Cola, asignación, segunda validación y discrepancias siguen bloqueando exportación cuando corresponde.
- [ ] Importaciones, cuarentena, novedades CIMA, exportación y sus detalles conservan acciones, confirmaciones y mensajes.
- [ ] Comparar a 1440×900, 1920×1080 y 2560×1440; comprobar desbordamientos en cortes menores.
- [ ] Ejecutar tests, lint, typecheck y build; añadir pruebas de interacción sólo donde cambie estructura interactiva.

Límite de esta auditoría: conclusiones visuales basadas en CSS y JSX; la fase de implementación debe completar capturas reales y mediciones de contraste antes de fijar valores definitivos.
