import { useEffect, useState } from 'react'

import { ApiError } from './client'

/**
 * Carga asíncrona con estados explícitos.
 *
 * Se cancela al desmontar y al cambiar las dependencias: una respuesta tardía
 * de una consulta anterior no debe sobrescribir la actual, porque en un listado
 * filtrado eso mostraría datos que no corresponden al filtro visible.
 */
export interface QueryState<T> {
  readonly data: T | null
  readonly error: string | null
  readonly loading: boolean
}

export function useQuery<T>(run: () => Promise<T>, deps: readonly unknown[]): QueryState<T> {
  const [state, setState] = useState<QueryState<T>>({
    data: null,
    error: null,
    loading: true,
  })

  useEffect(() => {
    let cancelled = false
    setState((previous) => ({ ...previous, loading: true }))
    run()
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false })
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setState({
          data: null,
          error: cause instanceof ApiError ? cause.message : 'Error inesperado.',
          loading: false,
        })
      })
    return () => {
      cancelled = true
    }
    // Las dependencias son las que declara quien llama: `run` se recrea en cada
    // render y usarla como dependencia provocaría una recarga infinita.
  }, deps)

  return state
}
