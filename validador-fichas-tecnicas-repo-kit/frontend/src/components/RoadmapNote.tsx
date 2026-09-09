import { useId, useState } from 'react'

import type { RoadmapNote as Note } from '../domain/vocabulary'

/**
 * Nota contextual sobre el grado de disponibilidad de una capacidad.
 *
 * Es plegable y discreta a propósito: debe explicar la visión del producto sin
 * competir con los datos. Distingue implementación técnica de activación o
 * validación clínica para no presentar trabajo terminado como inexistente.
 */
export function RoadmapNote({ title, note }: { title: string; note: Note }) {
  const [open, setOpen] = useState(false)
  const bodyId = useId()

  return (
    <div className='roadmap'>
      <button
        type='button'
        className='roadmap__toggle'
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden='true' className='roadmap__icon'>
          i
        </span>
        <span className='roadmap__title'>{title}</span>
        <span className={`badge badge--${note.status}`}>
          {note.status === 'disponible'
            ? 'Implementado'
            : note.status === 'preparado'
              ? 'Preparado'
              : 'Pendiente'}
        </span>
        <span aria-hidden='true' className='roadmap__chevron'>
          {open ? '−' : '+'}
        </span>
      </button>
      <div id={bodyId} className='roadmap__body' hidden={!open}>
        <dl>
          <dt>Ahora</dt>
          <dd>{note.now}</dd>
          <dt>Falta</dt>
          <dd>{note.missing}</dd>
          <dt>Cuando esté terminado</dt>
          <dd>{note.future}</dd>
          <dt>Depende de</dt>
          <dd className='roadmap__dependency'>{note.dependency}</dd>
        </dl>
      </div>
    </div>
  )
}
