/**
 * Formato de los datos que se muestran tal cual llegan del backend.
 *
 * Ninguna de estas funciones transforma el dato: sólo lo presenta. Un hash
 * abreviado conserva el valor completo en el título para poder auditarlo.
 */

export function formatDateTime(value: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('es-ES', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatNumber(value: number | null): string {
  return value === null ? '—' : value.toLocaleString('es-ES')
}

/** Abrevia un hash largo sin perderlo: el valor completo va en `title`. */
export function shortHash(value: string | null): string {
  if (!value) return '—'
  return value.length <= 12 ? value : `${value.slice(0, 12)}…`
}

export function orDash(value: string | null | undefined): string {
  return value === null || value === undefined || value === '' ? '—' : value
}
