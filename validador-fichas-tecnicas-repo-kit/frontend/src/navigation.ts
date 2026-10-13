import { useEffect, useState } from 'react'

/**
 * Enrutado mínimo sobre `location.hash`.
 *
 * Se resuelve con la plataforma en lugar de añadir una dependencia. Las rutas
 * antiguas se traducen a las pestañas internas nuevas para conservar enlaces.
 */

export type Route =
  | { readonly name: 'inicio' }
  | { readonly name: 'fichas' }
  | { readonly name: 'ficha'; readonly id: string }
  | { readonly name: 'catalogo'; readonly id: string }
  | { readonly name: 'fuentes' }
  | { readonly name: 'importaciones' }
  | { readonly name: 'seccion'; readonly id: string }

const LEGACY_SECTION_PATHS: Record<string, string> = {
  cola: 'revision/cola',
  validaciones: 'revision/validaciones',
  cuarentena: 'datos/cuarentena',
  novedades: 'catalogo/novedades',
}

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#\/?/, '')
  if (path === '' || path === 'inicio') return { name: 'inicio' }
  if (path === 'fichas') return { name: 'fichas' }
  // `/registros` era el segundo listado, fusionado en `/fichas`. Los enlaces ya
  // repartidos deben seguir abriendo lo que abrían: se resuelven a la ruta que
  // queda en lugar de caer en «sección desconocida».
  if (path === 'registros') return { name: 'fichas' }
  if (path === 'fuentes' || path === 'datos/fuentes') return { name: 'fuentes' }
  if (path === 'importaciones' || path === 'datos/importaciones') return { name: 'importaciones' }
  const legacySection = LEGACY_SECTION_PATHS[path]
  if (legacySection) return { name: 'seccion', id: legacySection }
  if (path.startsWith('revision/') || path === 'datos/cuarentena' || path === 'catalogo/novedades' || path === 'catalogo/trabajo' || path === 'catalogo/segunda') {
    return { name: 'seccion', id: path }
  }
  const record = /^registros\/(.+)$/.exec(path)
  if (record) return { name: 'ficha', id: decodeURIComponent(record[1]) }
  const detail = /^fichas\/(.+)$/.exec(path)
  if (detail) return { name: 'ficha', id: decodeURIComponent(detail[1]) }
  const catalog = /^catalogo\/(.+)$/.exec(path)
  if (catalog) return { name: 'catalogo', id: decodeURIComponent(catalog[1]) }
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
