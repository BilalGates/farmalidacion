import { useEffect, useState } from 'react'

import { ApiError, fetchRecords } from '../api/client'
import type { RecordList, ReviewState } from '../api/types'
import { RoadmapNote } from '../components/RoadmapNote'
import { ReviewBadge } from '../components/StateBadge'
import { REVIEW_STATE_LABELS, ROADMAP_NOTES } from '../domain/vocabulary'
import { navigate } from '../navigation'

const FILTERS: readonly (ReviewState | 'todos')[] = [
  'todos',
  'pendiente',
  'en_revision',
  'requiere_revision',
  'validado',
]

export function RecordListScreen() {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<ReviewState | 'todos'>('todos')
  const [data, setData] = useState<RecordList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchRecords({ q: query || undefined, estado: filter === 'todos' ? undefined : filter })
      .then((result) => {
        if (cancelled) return
        setData(result)
        setError(null)
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setError(cause instanceof ApiError ? cause.message : 'Error inesperado.')
        setData(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [query, filter])

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Fichas técnicas</p>
          <h1>Registros en revisión</h1>
          <p className='lede'>
            Cada fila es un registro destino. El estado resume la revisión de sus campos y no
            sustituye a la decisión campo a campo.
          </p>
        </div>
      </div>

      <div className='toolbar'>
        <label className='field'>
          <span className='field__label'>Buscar</span>
          <input
            type='search'
            value={query}
            placeholder='Medicamento, principio activo o identificador'
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className='filters' role='group' aria-label='Filtrar por estado'>
          {FILTERS.map((item) => (
            <button
              key={item}
              type='button'
              className={`chip${filter === item ? ' chip--active' : ''}`}
              aria-pressed={filter === item}
              onClick={() => setFilter(item)}
            >
              {item === 'todos' ? 'Todos' : REVIEW_STATE_LABELS[item]}
            </button>
          ))}
        </div>
      </div>

      {error && <p className='alert alert--error'>{error}</p>}
      {loading && !data && <p className='muted'>Cargando registros…</p>}

      {data && (
        <>
          <p className='muted'>
            {data.total} {data.total === 1 ? 'registro' : 'registros'}
          </p>
          <div className='table-wrap'>
            <table className='table'>
              <thead>
                <tr>
                  <th scope='col'>Medicamento</th>
                  <th scope='col'>Principio activo</th>
                  <th scope='col'>Identificador</th>
                  <th scope='col'>Estado</th>
                  <th scope='col'>Campos</th>
                  <th scope='col'>Discrepancias</th>
                  <th scope='col'>Última revisión</th>
                  <th scope='col'>
                    <span className='sr-only'>Acción</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td className='cell--strong'>{item.display_name ?? '—'}</td>
                    <td>{item.active_ingredient ?? '—'}</td>
                    <td className='cell--mono'>{item.primary_identifier ?? '—'}</td>
                    <td>
                      <ReviewBadge state={item.review_state} />
                    </td>
                    <td className='cell--num'>
                      {item.resolved_count}/{item.field_count}
                    </td>
                    <td className='cell--num'>
                      {item.conflict_count > 0 ? (
                        <span className='badge badge--requiere_revision'>
                          {item.conflict_count}
                        </span>
                      ) : (
                        <span className='muted'>0</span>
                      )}
                    </td>
                    <td className='cell--date'>
                      {item.last_reviewed_at
                        ? new Date(item.last_reviewed_at).toLocaleString('es-ES')
                        : '—'}
                    </td>
                    <td>
                      <button
                        type='button'
                        className='button button--ghost'
                        onClick={() => navigate(`/fichas/${encodeURIComponent(item.id)}`)}
                      >
                        Abrir ficha
                      </button>
                    </td>
                  </tr>
                ))}
                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={8} className='muted'>
                      Ningún registro coincide con la búsqueda.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      <RoadmapNote title='Cola de trabajo y asignación' note={ROADMAP_NOTES.teclado} />
    </div>
  )
}
