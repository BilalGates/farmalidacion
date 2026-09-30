# ADR-0012 — Registros como espacio compacto de revisión

- Estado: aceptado por instrucción del responsable, 2026-09-10.
- Evidencia: elección explícita de la alternativa compacta y petición «me mola, implementalo ya» tras revisar el prototipo.
- Alcance: presentación y navegación de Registros. Sin cambios al modelo, a las políticas clínicas ni a la exportación.

## Decisión

Integrar listado y ficha en una pantalla: listado a la izquierda; campos y fuente contextual en la zona de revisión. Mantener la ruta por registro y el montaje del listado para conservar búsqueda, estado, página y desplazamiento al seleccionar otro registro.

Mostrar nombres legibles conocidos junto al código original; los códigos sin etiqueta contrastada se conservan literalmente. Abrir un solo editor, manteniendo los demás campos montados para proteger borradores e historial. Buscar por nombre/código y filtrar por bloque o trabajo pendiente sin fusionar ocurrencias.

El avance al siguiente registro requiere pulsación explícita. La API aplica el filtro de estado después de paginar: recorrer páginas vacías con cancelación, sin presentar el total global como total de pendientes. La ficha elegida puede permanecer visible mientras se cambia la búsqueda del listado.

La evidencia Excel presenta la celda activa y sus vecinas. La fila completa, celdas vacías, fórmulas, procedencia, versión y fragmento original siguen accesibles. La evidencia no estructurada se muestra literal, sin resumir ni inventar contexto.

La revisión conserva las decisiones explícitas, el bloqueo sin revisor, las barreras del backend y los borradores locales. «Guardar y siguiente campo» avanza únicamente tras guardar y recargar correctamente; un rechazo conserva el borrador. No se incorpora el botón de copia del maestro del prototipo: debe respetarse la política de cada campo (ADR-0007 y especificación §9).

## Validación

Pruebas de selección, continuidad de filtros, cambio de ficha con carga tardía, paginación vacía, un único editor, recuperación de borradores, guardado rechazado/aceptado y recuperación de la fuente completa. Comprobación visual en portátil, monitor y anchura móvil. La aceptación farmacéutica y la medida de ahorro siguen pendientes conforme a ADR-0010.

## Extensión

Los estilos quedan limitados a Registros. Aplicar posteriormente la misma jerarquía y componentes a otras pantallas según su función; esta decisión no impone tres columnas a todos los módulos.
