import type { DataOrigin } from '../api/types'

/**
 * Distintivo de origen del dato.
 *
 * Se muestra siempre, también cuando el dato es real: si sólo se marcase lo
 * DEMO, la ausencia de marca tendría que interpretarse, y una marca ausente por
 * error pasaría por dato real.
 */
export function OriginBadge({ origin }: { origin: DataOrigin }) {
  return (
    <span className={`badge badge--origin-${origin}`}>
      {origin === 'real' ? 'Real' : 'DEMO'}
    </span>
  )
}
