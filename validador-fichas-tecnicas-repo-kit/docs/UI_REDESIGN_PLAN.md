# Plan de implementación del rediseño visual

Estado: preparado, sin implementación visual en esta fase. Objetivo: interfaz de trabajo farmacéutico sobria y coherente, con funcionalidad y contratos intactos. Referencia: `UI_REDESIGN_AUDIT.md`.

## Fase 0 — Línea base

Capturar todas las rutas y superficies internas en REAL y DEMO con datos representativos; documentar recorridos de teclado y capturas a 1440×900, 1920×1080 y 2560×1440. Registrar contrastes y densidad de tablas. Salida: referencia visual y funcional revisable.

## Fase 1 — Fundamentos

Definir escala de tipografía, espacios, radios, colores semánticos, foco y densidad. Consolidar `styles.css` y la relación con `review-workspace.css` por cambios pequeños. Sin alterar DOM funcional. Salida: tokens únicos, estilos de foco y estados verificables.

## Fase 2 — Shell y primitivas

Unificar navegación, cabecera, pestañas, botones, campos, badges, avisos, estados asíncronos, tablas, paginación y paneles. Mantener API de componentes y rutas; migrar consumidores gradualmente. Salida: catálogo de variantes con estados hover, focus, disabled, loading y error; pruebas de teclado.

## Fase 3 — Superficies de consulta

Migrar catálogo/listado, filtros, fuentes, importaciones y cuarentena. Ajustar ancho y densidad desktop, preservar columnas, selección, filtros, orden, paginación y detalles. Salida: comparación de capturas y recorridos aprobados por pantalla.

## Fase 4 — Revisión y evidencia

Migrar expediente, editor de campo, bloque repetible, evidencia, cola y segunda revisión en unidades pequeñas. Preservar atajos, foco, borradores, guardado, mensajes, discrepancias, procedencia y estados de validación. Salida: suite de interacción y revisión farmacéutica de equivalencia visual/operativa.

## Fase 5 — Catálogo canónico y operaciones

Migrar identidad, mantenimiento de campos fuente, comparación/documento CIMA, novedades, exportaciones y revisores. Conservar autoría, versiones, motivos, exclusiones y trazabilidad. Salida: recorridos completos sin diferencias funcionales.

## Fase 6 — Pulido y retirada de deuda

Revisar inicio con métricas útiles; eliminar reglas CSS obsoletas sólo tras comprobar consumidores; resolver accesibilidad y responsive. Ejecutar tests, lint, typecheck y build; comparar capturas finales. Salida: checklist del auditado cerrado y ninguna regresión funcional conocida.

## Reglas de cada entrega

Una pantalla o patrón por cambio revisable. Antes y después a tres resoluciones desktop; verificación de teclado y estados loading/error/vacío. Mantener URLs, APIs, modelo, reglas clínicas, importadores, exportadores, auditoría y trazabilidad. Cualquier cambio de comportamiento requiere decisión separada y no forma parte de este plan visual.
