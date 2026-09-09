import { useEffect, useState } from 'react'

/**
 * Enrutado mínimo sobre `location.hash`.
 *
 * Se resuelve con la plataforma en lugar de añadir una dependencia de routing:
 * la vertical tiene dos rutas reales y el resto son secciones anunciadas. Si el
 * producto crece, sustituir esto por un router es un cambio localizado en este
 * fichero y en `App`.
 */

export type Route =
  | { readonly name: 'inicio' }
  | { readonly name: 'fichas' }
  | { readonly name: 'ficha'; readonly id: string }
  | { readonly name: 'fuentes' }
  | { readonly name: 'importaciones' }
  | { readonly name: 'seccion'; readonly id: string }

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#\/?/, '')
  if (path === '' || path === 'inicio') return { name: 'inicio' }
  if (path === 'fichas') return { name: 'fichas' }
  // `/registros` era el segundo listado, fusionado en `/fichas`. Los enlaces ya
  // repartidos deben seguir abriendo lo que abrían: se resuelven a la ruta que
  // queda en lugar de caer en «sección desconocida».
  if (path === 'registros') return { name: 'fichas' }
  if (path === 'fuentes') return { name: 'fuentes' }
  if (path === 'importaciones') return { name: 'importaciones' }
  const record = /^registros\/(.+)$/.exec(path)
  if (record) return { name: 'ficha', id: decodeURIComponent(record[1]) }
  const detail = /^fichas\/(.+)$/.exec(path)
  if (detail) return { name: 'ficha', id: decodeURIComponent(detail[1]) }
  return { name: 'seccion', id: path }
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export function navigate(path: string): void {
  window.location.hash = path
}
