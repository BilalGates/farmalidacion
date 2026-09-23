import { useState } from 'react'

import { fetchCatalogIdentities } from '../api/client'
import type { CatalogIdentityType } from '../api/types'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { orDash } from '../domain/format'
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

const ENTITY_FILTERS = [
  { value: null, label: 'Todo el catálogo' },
  { value: 'presentation', label: 'Presentaciones' },
  { value: 'dcpf', label: 'DCPF' },
  { value: 'dcp', label: 'DCP' },
  { value: 'dcsa', label: 'DCSA' },
  { value: 'active_ingredient', label: 'Sustancias activas' },
] as const

const ENTITY_LABELS: Record<string, string> = {
  commercial_product: 'Producto comercial',
  authorization: 'Autorización',
  presentation: 'Presentación',
  dcpf: 'DCPF',
  dcp: 'DCP',
  dcsa: 'DCSA',
  active_ingredient: 'Sustancia activa',
}

const CLASSIFICATION_FILTERS = [
  { type: null, value: null, label: 'Todas las clases' },
  { type: 'commercial_class', value: 'original', label: 'Original' },
  { type: 'commercial_class', value: 'generico', label: 'Genérico' },
  { type: 'commercial_class', value: 'biosimilar', label: 'Biosimilar' },
] as const
const CONDITION_FILTERS = [
  { value: 'huerfano', label: 'Huérfano' },
  { value: 'estupefaciente', label: 'Estupefaciente' },
  { value: 'psicotropico', label: 'Psicotrópico' },
  { value: 'especial_control_medico', label: 'Control especial' },
  { value: 'uso_hospitalario', label: 'Uso hospitalario' },
] as const
const CLASS_LABELS: Record<string, string> = {
  original: 'Original', generico: 'Genérico', biosimilar: 'Biosimilar',
  sin_clasificar: 'Sin clasificar',
}
const CONDITION_LABELS: Record<string, string> = {
  huerfano: 'Huérfano', estupefaciente: 'Estupefaciente',
  psicotropico: 'Psicotrópico', especial_control_medico: 'Control especial',
  uso_hospitalario: 'Uso hospitalario',
}

export function RealRecordListScreen() {
  const [term, setTerm] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [entityType, setEntityType] = useState<CatalogIdentityType | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [commercialClass, setCommercialClass] = useState<string | null>(null)
  const [conditions, setConditions] = useState<string[]>([])
  const [retryKey, setRetryKey] = useState(0)

  const { data, error, loading } = useQuery(
    () =>
      fetchCatalogIdentities({
        q: query || undefined,
        identityType: entityType ?? undefined,
        commercialClass: commercialClass ?? undefined,
        conditions: conditions.length ? conditions : undefined,
        active: showArchived ? undefined : true,
        limit: PAGE_SIZE,
        offset,
      }),
    [query, entityType, showArchived, commercialClass, conditions, offset, retryKey],
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
            Navegue por nivel farmacéutico y abra sólo el registro que necesita. La tabla se
            pagina en el servidor para seguir siendo manejable con miles de elementos.
          </p>
        </div>
      </div>

      <p className='origin-notice origin-notice--real'>
        Estado canónico editable. El valor fuente y su historial se conservan por separado.
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
        {(entityType === null || entityType === 'presentation') && <>
          <div className='filters' role='group' aria-label='Clase comercial'>
            {CLASSIFICATION_FILTERS.map((item) => <button
              key={item.label}
              type='button'
              className={`chip${commercialClass === item.value ? ' chip--active' : ''}`}
              aria-pressed={commercialClass === item.value}
              onClick={() => { setOffset(0); setCommercialClass(item.value) }}
            >{item.label}</button>)}
          </div>
          <label className='field catalog-condition-filter'>
            <span className='field__label'>Condición</span>
            <select multiple value={conditions} onChange={(event) => { setOffset(0); setConditions(Array.from(event.target.selectedOptions, (option) => option.value)) }}>
              {CONDITION_FILTERS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <small className='field__hint'>Puedes seleccionar varias; se mostrarán las presentaciones que cumplan todas.</small>
          </label>
        </>}
        <label className='catalog-toggle'>
          <input
            type='checkbox'
            checked={showArchived}
            onChange={(event) => { setOffset(0); setShowArchived(event.target.checked) }}
          />
          Incluir archivados
        </label>
      </form>

      <AsyncBoundary
        loading={loading}
        error={error}
        empty={(data?.total ?? 0) === 0}
        emptyTitle={query ? 'La búsqueda no devuelve resultados' : 'No hay identidades en este nivel'}
        emptyDetail={
          query
            ? `Ninguna identidad del catálogo contiene «${query}» en su descripción o código.`
            : 'Este nivel todavía no se ha podido proyectar desde una fuente fiable.'
        }
        onRetry={() => setRetryKey((k) => k + 1)}
      >
        {data && (
          <>
            <p className='muted'>
              {data.total.toLocaleString('es-ES')} identidades · página {page} de {pages}
            </p>
            <table className='table'>
              <thead>
                <tr>
                  <th scope='col'>Descripción</th>
                  <th scope='col'>Identificador</th>
                  <th scope='col'>Tipo</th>
                  <th scope='col'>Fuente</th>
                  <th scope='col'>Estado</th>
                  <th scope='col'>
                    <span className='visually-hidden'>Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <th scope='row'><span className='catalog-row__name'>{orDash(item.display_name)}</span>{item.identity_type === 'presentation' && <span className='catalog-row__tags'>{item.commercial_class && <span className='catalog-row__tag'>{CLASS_LABELS[item.commercial_class] ?? item.commercial_class}</span>}{item.conditions?.map((value) => <span className='catalog-row__tag catalog-row__tag--condition' key={value}>{CONDITION_LABELS[value] ?? value}</span>)}</span>}</th>
                    <td><code>{orDash(item.code)}</code></td>
                    <td>{ENTITY_LABELS[item.identity_type] ?? item.identity_type}</td>
                    <td>{item.source_system}</td>
                    <td><span className={`badge ${item.active ? 'badge--validado' : 'badge--descartado'}`}>{item.active ? 'Vigente' : 'Archivado'}</span></td>
                    <td>
                      <button
                        type='button'
                        className='button'
                        onClick={() => navigate(`/catalogo/${encodeURIComponent(item.id)}`)}
                      >
                        Abrir expediente
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
