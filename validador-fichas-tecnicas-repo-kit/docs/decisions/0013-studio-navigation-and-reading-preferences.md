# ADR-0013 — Estudio y preferencias de lectura

Fecha: 2026-10-05. Estado: aceptado por el responsable en esta conversación.

## Contexto

Los rediseños sucesivos conservaban demasiados apartados al mismo nivel y un
expediente largo que mezclaba lectura, edición, fuentes y auditoría. El responsable
acepta la dirección Estudio y solicita las dos densidades y el modo oscuro.

## Decisión

- Tres áreas principales: Catálogo, Trabajo y Datos. Resumen y Equipo permanecen
  como destinos secundarios. Exportaciones se sitúa en Datos; segunda lectura y
  novedades CIMA, en Trabajo. Se conservan las rutas anteriores.
- El expediente mantiene el modal y anterior/siguiente de ADR-0012. Dentro de él,
  Resumen, Fuentes, Relaciones y clasificación e Historial usan pestañas. Los
  paneles permanecen montados para conservar borradores; la edición se abre
  explícitamente desde el resumen de lectura.
- Densidad Cómoda y Compacta seleccionables, independientes del tema Claro,
  Oscuro o Según el sistema. Ambas preferencias se guardan localmente. Compacta
  reduce espacios y altura de filas sin reducir el texto de los datos.
- Fondo cálido, superficies sobrias y navegación ciruela; tipografía editorial
  en encabezados de área y tipografía de interfaz en los datos farmacéuticos.
- `studio.css` reúne el sistema activo. Los antiguos archivos visuales quedan
  sin importar para conservar el trabajo previo y su historia durante la migración.

## Alternativas e impacto

Se descarta obligar a todos a una única densidad. Se conserva la estructura de
componentes y los contratos existentes: no requiere migraciones de datos. La
consolidación visual es incremental; los estilos estructurales históricos y el
espacio de revisión siguen siendo dependencias, pendientes de depuración posterior.

## Verificación y límites

Pruebas de persistencia, independencia de preferencias, teclado de pestañas y
borradores. La aceptación de usabilidad farmacéutica y la revisión exhaustiva de
contraste en cada estado siguen pendientes. No se cambian reglas de propuesta,
procedencia, inferencia ni firma. El bloqueo de exportación con doble validación
abierta o desactualizada aplica una regla preexistente de AGENTS y la especificación.
