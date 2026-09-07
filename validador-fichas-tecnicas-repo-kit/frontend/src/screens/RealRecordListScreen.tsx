import { useState } from 'react'

import { fetchRealRecords } from '../api/client'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { OriginBadge } from '../components/OriginBadge'
import { orDash } from '../domain/format'
import { navigate } from '../navigation'

/**
 * Listado de registros reales importados desde los maestros.
 *
 * Esta ruta es exclusivamente REAL. Los registros ficticios viven en la ruta
 * separada «Revisión (DEMO)» y nunca se ofrecen como alternativa dentro del
 * listado de fichas técnicas.
 */

const PAGE_SIZE = 50

const ENTITY_LABELS: Record<string, string> = {
  medication: 'Medicamento',
  active_ingredient: 'Principio activo',
  specialty: 'Especialidad',
}

export function RealRecordListScreen() {
  const [term, setTerm] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [retryKey, setRetryKey] = useState(0)

  const { data, error, loading } = useQuery(
    () => fetchRealRecords({ origin: 'real', q: query || undefined, limit: PAGE_SIZE, offset }),
    [query, offset, retryKey],
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
          <p className='eyebrow'>Fichas técnicas</p>
          <h1>Registros</h1>
          <p className='lede'>
            Consulte los registros importados desde los maestros. El origen de los datos se elige
            de forma explícita y nunca se mezclan en una misma tabla.
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
            placeholder='Descripción o identificador del maestro'
            onChange={(event) => setTerm(event.target.value)}
          />
        </label>
        <button type='submit' className='button button--primary'>
          Buscar
        </button>
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
              {data.total.toLocaleString('es-ES')} registros · página {page} de {pages}
            </p>
            <table className='table'>
              <thead>
                <tr>
                  <th scope='col'>Descripción</th>
                  <th scope='col'>Identificador</th>
                  <th scope='col'>Tipo</th>
                  <th scope='col'>Origen</th>
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
