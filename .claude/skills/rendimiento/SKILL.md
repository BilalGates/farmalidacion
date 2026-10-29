---
name: rendimiento
description: Medir antes de optimizar — consultas lentas, N+1, esperas en serie, render de React, tamaño del bundle y caché. Cárgala cuando algo vaya lento, al revisar avisos de rendimiento (p. ej. React Doctor) o al diseñar algo con volumen.
---

# rendimiento

## Regla

**Sin medida no hay optimización.** Anota el número antes y después.

## Base de datos

- `EXPLAIN (ANALYZE, BUFFERS)` de la consulta real con datos realistas.
- Índice que soporte el filtro y el orden reales del listado (catálogo, cola, histórico).
- N+1: una consulta por fila en un bucle → una consulta con JOIN o `IN`.
- Paginar siempre listados; nunca `SELECT *` de tablas anchas para pintar una lista.

## Servidor

- Esperas independientes en paralelo: `Promise.all([a(), b()])`. **Solo si de verdad son independientes**: si la segunda usa el resultado de la primera, o la primera es una comprobación de acceso que debe cortar antes, el orden es correcto y el aviso es falso positivo — dilo.
- Caché con clave que incluya todo lo que cambia el resultado (usuario, filtros, versión del dato).

## React / cliente

- Componentes de servidor por defecto; cliente solo para interacción.
- No traer datos dentro de `useEffect` si pueden venir del servidor.
- No copiar props a `useState` (estado derivado): calcúlalo en el render.
- Animaciones de propiedades concretas (`transition: opacity`), no `transition: all`.
- Listas largas virtualizadas; imágenes con tamaño declarado.
- Funciones de componente muy complejas: extraer subcomponentes o hooks, sin cambiar comportamiento.

## Bundle

- Importar solo lo usado; carga diferida de lo pesado y no inicial (mapas, editores, gráficas).
- Ninguna dependencia nueva para lo que resuelven diez líneas.

## Entrega

`métrica → antes → después → cómo se midió`.
