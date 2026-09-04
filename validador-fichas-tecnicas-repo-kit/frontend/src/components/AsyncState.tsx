import type { ReactNode } from 'react'

/**
 * Estados de carga, error y vacío, resueltos en un único lugar.
 *
 * El caso vacío exige un texto que explique *por qué* no hay nada: una tabla
 * sin filas y sin explicación se lee como un fallo de la aplicación, y en esta
 * herramienta la diferencia entre «no hay datos cargados» y «la consulta no
 * devuelve nada» es información, no decoración.
 */

export function LoadingState({ label = 'Cargando…' }: { label?: string }) {
  return (
    <p className='state state--loading' role='status'>
      {label}
    </p>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <p className='state state--error' role='alert'>
      {message}
    </p>
  )
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className='state state--empty'>
      <p className='state__title'>{title}</p>
      <p className='state__detail'>{detail}</p>
    </div>
  )
}

/** Envoltura que decide entre los tres estados sin repetir la lógica. */
export function AsyncBoundary({
  loading,
  error,
  empty,
  emptyTitle,
  emptyDetail,
  children,
}: {
  loading: boolean
  error: string | null
  empty: boolean
  emptyTitle: string
  emptyDetail: string
  children: ReactNode
}) {
  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} />
  if (empty) return <EmptyState title={emptyTitle} detail={emptyDetail} />
  return <>{children}</>
}
