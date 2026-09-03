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
  | { readonly name: 'seccion'; readonly id: string }

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#\/?/, '')
  if (path === '' || path === 'inicio') return { name: 'inicio' }
  if (path === 'fichas') return { name: 'fichas' }
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
