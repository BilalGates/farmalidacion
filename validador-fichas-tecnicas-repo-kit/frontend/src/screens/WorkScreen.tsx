import { useEffect, useState } from 'react'

import type { Reviewer } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { QueueScreen } from './QueueScreen'
import { SecondReviewScreen, type SecondReviewCounts } from './SecondReviewScreen'

/**
 * Revisión: la cola del equipo y las segundas lecturas en una sola página.
 *
 * Cada bloque conserva su carga, sus permisos y su lógica; esta página sólo
 * los compone y reúne sus cifras en la cabecera. Ningún dato cruza de un
 * bloque a otro: la segunda lectura sigue sin recibir la primera.
 */
export function WorkScreen({ reviewer, focusSecond = false }: { reviewer: Reviewer | null; focusSecond?: boolean }) {
  const [queued, setQueued] = useState<number | null>(null)
  const [second, setSecond] = useState<SecondReviewCounts | null>(null)

  // Los enlaces antiguos a «Segunda lectura» llevan a su bloque.
  useEffect(() => {
    if (focusSecond) document.getElementById('segunda-lectura')?.scrollIntoView({ block: 'start' })
  }, [focusSecond])

  const figure = (value: number | undefined | null) => value ?? '—'
  return <div className='screen work-screen'>
    <PageHeader eyebrow='Trabajo del equipo' title='Revisión'
      description='Asígnate registros de la cola y emite las segundas lecturas pendientes.'
      actions={<dl className='work-figures' aria-label='Resumen de la revisión'>
        <div><dt>En cola</dt><dd>{figure(queued)}</dd></div>
        <div><dt>Segunda lectura</dt><dd>{figure(second?.open)}</dd></div>
        <div data-alert={second && second.conflicts > 0 ? 'true' : undefined}><dt>Discrepancias</dt><dd>{figure(second?.conflicts)}</dd></div>
      </dl>} />
    <QueueScreen reviewer={reviewer} embedded onCount={setQueued} />
    <SecondReviewScreen reviewer={reviewer} embedded onCounts={setSecond} />
  </div>
}
