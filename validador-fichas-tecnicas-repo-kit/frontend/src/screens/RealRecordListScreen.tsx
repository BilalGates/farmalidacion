import { useState } from 'react'

import { fetchRealRecords } from '../api/client'
import type { ReviewState } from '../api/types'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { OriginBadge } from '../components/OriginBadge'
import { ReviewBadge } from '../components/StateBadge'
import { orDash } from '../domain/format'
import { REVIEW_STATE_LABELS } from '../domain/vocabulary'
import { navigate } from '../navigation'

/**
 * Listado único de registros, con su origen y su estado de revisión.
 *
 * Antes había dos listados: éste y «Revisión (DEMO)», que consultaban endpoints
 * distintos y llevaban a la misma pantalla de detalle. Dos puertas a lo mismo
 * obligan a saber cuál abrir, así que se fusionan aquí y el estado de revisión
 * pasa a ser una columna y un filtro más.
 *
 * El origen sigue siendo explícito: REAL y DEMO nunca se mezclan en la misma
 * tabla, que es lo que esta vertical debe impedir.
 */

const PAGE_SIZE = 50

/** Filtros de estado, en el orden en que avanza una revisión. */
const ESTADOS: readonly ReviewState[] = ['pendiente', 'en_revision', 'validado']

const ENTITY_FILTERS = [
  { value: null, label: 'Todo el catálogo' },
  { value: 'specialty', label: 'Presentaciones' },
  { value: 'medication', label: 'Medicamentos' },
  { value: 'active_ingredient', label: 'Principios activos' },
] as const

const ENTITY_LABELS: Record<string, string> = {
  medication: 'Medicamento',
  active_ingredient: 'Principio activo',
  specialty: 'Especialidad',
}

export function RealRecordListScreen() {
  const [term, setTerm] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [estado, setEstado] = useState<ReviewState | null>(null)
  const [entityType, setEntityType] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  const { data, error, loading } = useQuery(
    () =>
      fetchRealRecords({
        origin: 'real',
        q: query || undefined,
        entityType: entityType ?? undefined,
        estado: estado ?? undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [query, entityType, estado, offset, retryKey],
  )

  function search(event: React.FormEvent) {
    event.preventDefault()
    setOffset(0)
    setQuery(term.trim())
  }

  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const pages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Catálogo</p>
          <h1>Catálogo de medicamentos</h1>
          <p className='lede'>
            Localice primero el nivel que necesita: presentación, medicamento o principio activo.
            Los datos originales y su procedencia permanecen visibles al abrir la ficha.
          </p>
        </div>
      </div>

      <p className='origin-notice origin-notice--real'>
        Datos reales importados de los maestros Excel, con su procedencia registrada.
      </p>

      <form className='toolbar' onSubmit={search} role='search'>
        <label className='field'>
          <span className='field__label'>Buscar</span>
          <input
            type='search'
            value={term}
            placeholder='CN, nombre, identificador o principio activo'
            onChange={(event) => setTerm(event.target.value)}
          />
        </label>
        <button type='submit' className='button button--primary'>
          Buscar
        </button>
        <div className='filters' role='group' aria-label='Nivel del catálogo'>
          {ENTITY_FILTERS.map((item) => (
            <button
              key={item.label}
              type='button'
              className={`chip${entityType === item.value ? ' chip--active' : ''}`}
              aria-pressed={entityType === item.value}
              onClick={() => {
                setOffset(0)
                setEntityType(item.value)
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className='filters' role='group' aria-label='Estado de revisión'>
          <button
            type='button'
            className={`chip${estado === null ? ' chip--active' : ''}`}
            aria-pressed={estado === null}
            onClick={() => {
              setOffset(0)
              setEstado(null)
            }}
          >
            Todos
          </button>
          {ESTADOS.map((name) => (
            <button
              key={name}
              type='button'
              className={`chip${estado === name ? ' chip--active' : ''}`}
              aria-pressed={estado === name}
              onClick={() => {
                setOffset(0)
                setEstado(name)
              }}
            >
              {REVIEW_STATE_LABELS[name] ?? name}
            </button>
          ))}
        </div>
      </form>

      <AsyncBoundary
        loading={loading}
        error={error}
        empty={(data?.total ?? 0) === 0}
        emptyTitle={query ? 'La búsqueda no devuelve resultados' : 'No hay registros de este origen'}
        emptyDetail={
          query
            ? `Ningún registro real contiene «${query}» en su descripción o identificador.`
            : 'No hay registros importados. Ejecute scripts/ingest_master_files.py para cargar los maestros Excel.'
        }
        onRetry={() => setRetryKey((k) => k + 1)}
      >
        {data && (
          <>
            <p className='muted'>
              {estado === null ? (
                <>
                  {data.total.toLocaleString('es-ES')} registros · página {page} de {pages}
                </>
              ) : (
                /* Con filtro de estado el total no se recalcula: contarlo exigiría
                   recorrer el maestro entero. Se dice cuántos trae esta página en
                   lugar de presentar como total lo que no lo es. */
                <>
                  {data.items.length} en esta página · página {page} de {pages}
                </>
              )}
            </p>
            <table className='table'>
              <thead>
                <tr>
                  <th scope='col'>Descripción</th>
                  <th scope='col'>Identificador</th>
                  <th scope='col'>Tipo</th>
                  <th scope='col'>Origen</th>
                  <th scope='col'>Estado</th>
                  <th scope='col'>Bloques</th>
                  <th scope='col'>Campos</th>
                  <th scope='col'>
                    <span className='visually-hidden'>Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <th scope='row'>{orDash(item.display_name)}</th>
                    <td>
                      <code>{orDash(item.identifier)}</code>
                    </td>
                    <td>{ENTITY_LABELS[item.entity_type] ?? item.entity_type}</td>
                    <td>
                      <OriginBadge origin={item.origin} />
                    </td>
                    <td>
                      <ReviewBadge state={item.review_state} />
                    </td>
                    <td>{item.block_count}</td>
                    <td>{item.field_count}</td>
                    <td>
                      <button
                        type='button'
                        className='button'
                        onClick={() => navigate(`/fichas/${encodeURIComponent(item.id)}`)}
                      >
                        Abrir ficha
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className='pagination'>
              <button
                type='button'
                className='button'
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                Anterior
              </button>
              <button
                type='button'
                className='button'
                disabled={offset + PAGE_SIZE >= data.total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Siguiente
              </button>
            </div>
          </>
        )}
      </AsyncBoundary>
    </div>
  )
}
