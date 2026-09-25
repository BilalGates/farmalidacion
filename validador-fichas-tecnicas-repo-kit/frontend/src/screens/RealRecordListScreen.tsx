import { useEffect, useRef, useState } from 'react'

import { fetchCatalogIdentities } from '../api/client'
import type { CatalogIdentitySort, CatalogIdentityType, CatalogSourceWorkbook } from '../api/types'
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

const SOURCE_VIEWS: { value: CatalogSourceWorkbook; label: string; identityType: CatalogIdentityType }[] = [
  { value: 'especialidades', label: 'Especialidades · CN', identityType: 'presentation' },
  { value: 'medicamentos', label: 'Medicamentos · DCP', identityType: 'dcp' },
  { value: 'principios_activos', label: 'Principios activos · PA', identityType: 'active_ingredient' },
]
const SOURCE_LABELS: Record<CatalogSourceWorkbook, string> = {
  especialidades: 'Especialidades', medicamentos: 'Medicamentos', principios_activos: 'Principios activos',
}
const SORT_OPTIONS: { value: CatalogIdentitySort; label: string }[] = [
  { value: 'name_asc', label: 'Nombre · A–Z' },
  { value: 'name_desc', label: 'Nombre · Z–A' },
  { value: 'code_asc', label: 'Código · ascendente' },
  { value: 'code_desc', label: 'Código · descendente' },
]

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

const LIST_STATE_KEY = 'farmalidacion.catalog-list-state'
interface CatalogListState {
  term: string
  query: string
  offset: number
  entityType: CatalogIdentityType | null
  sourceWorkbook: CatalogSourceWorkbook | null
  showArchived: boolean
  commercialClass: string | null
  conditions: string[]
  sortBy: CatalogIdentitySort
  tableScrollTop: number
  tableScrollLeft: number
  windowScrollY: number
}

function readListState(): Partial<CatalogListState> {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(LIST_STATE_KEY) ?? 'null')
    if (!value || typeof value !== 'object') return {}
    const saved = value as Partial<CatalogListState>
    const sourceView = SOURCE_VIEWS.find((item) => item.value === saved.sourceWorkbook)
    const entityFilter = ENTITY_FILTERS.find((item) => item.value === saved.entityType)
    const savedEntityType = sourceView?.identityType ?? entityFilter?.value ?? null
    const supportsPresentationFilters = savedEntityType === null || savedEntityType === 'presentation'
    const savedClass = CLASSIFICATION_FILTERS.some((item) => item.value === saved.commercialClass)
      ? saved.commercialClass ?? null
      : null
    const savedConditions = Array.isArray(saved.conditions)
      ? saved.conditions.filter((entry): entry is string => CONDITION_FILTERS.some((item) => item.value === entry))
      : []
    return {
      term: typeof saved.term === 'string' ? saved.term : '',
      query: typeof saved.query === 'string' ? saved.query : '',
      offset: typeof saved.offset === 'number' && saved.offset >= 0 ? saved.offset : 0,
      entityType: savedEntityType,
      sourceWorkbook: sourceView?.value ?? null,
      showArchived: saved.showArchived === true,
      commercialClass: supportsPresentationFilters ? savedClass : null,
      conditions: supportsPresentationFilters ? savedConditions : [],
      sortBy: SORT_OPTIONS.some((item) => item.value === saved.sortBy)
        ? saved.sortBy ?? 'name_asc'
        : 'name_asc',
      tableScrollTop: typeof saved.tableScrollTop === 'number' && saved.tableScrollTop >= 0 ? saved.tableScrollTop : 0,
      tableScrollLeft: typeof saved.tableScrollLeft === 'number' && saved.tableScrollLeft >= 0 ? saved.tableScrollLeft : 0,
      windowScrollY: typeof saved.windowScrollY === 'number' && saved.windowScrollY >= 0 ? saved.windowScrollY : 0,
    }
  } catch {
    return {}
  }
}

export function RealRecordListScreen() {
  const [initialState] = useState(readListState)
  const [term, setTerm] = useState(initialState.term ?? '')
  const [query, setQuery] = useState(initialState.query ?? '')
  const [offset, setOffset] = useState(initialState.offset ?? 0)
  const [entityType, setEntityType] = useState<CatalogIdentityType | null>(initialState.entityType ?? null)
  const [sourceWorkbook, setSourceWorkbook] = useState<CatalogSourceWorkbook | null>(initialState.sourceWorkbook ?? null)
  const [showArchived, setShowArchived] = useState(initialState.showArchived ?? false)
  const [commercialClass, setCommercialClass] = useState<string | null>(initialState.commercialClass ?? null)
  const [conditions, setConditions] = useState<string[]>(initialState.conditions ?? [])
  const [sortBy, setSortBy] = useState<CatalogIdentitySort>(initialState.sortBy ?? 'name_asc')
  const [retryKey, setRetryKey] = useState(0)
  const resultsRef = useRef<HTMLDivElement>(null)
  const requestedOffset = useRef(offset)
  const restoredPosition = useRef(false)

  useEffect(() => {
    const state: CatalogListState = {
      term, query, offset, entityType, sourceWorkbook, showArchived, commercialClass, conditions, sortBy,
      tableScrollTop: initialState.tableScrollTop ?? 0,
      tableScrollLeft: initialState.tableScrollLeft ?? 0,
      windowScrollY: initialState.windowScrollY ?? 0,
    }
    try { sessionStorage.setItem(LIST_STATE_KEY, JSON.stringify(state)) } catch { /* almacenamiento opcional */ }
  }, [term, query, offset, entityType, sourceWorkbook, showArchived, commercialClass, conditions, sortBy])

  function toggleCondition(value: string) {
    setOffset(0)
    setEntityType('presentation')
    setConditions((selected) => selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])
  }

  function clearFilters() {
    setTerm('')
    setQuery('')
    setOffset(0)
    setEntityType(null)
    setSourceWorkbook(null)
    setShowArchived(false)
    setCommercialClass(null)
    setConditions((selected) => selected.length ? [] : selected)
    setSortBy('name_asc')
  }

  function selectCommercialClass(value: string | null) {
    setOffset(0)
    setEntityType('presentation')
    setCommercialClass(value)
  }

  function selectEntityType(value: CatalogIdentityType | null) {
    setOffset(0)
    setEntityType(value)
    setSourceWorkbook(null)
    if (value !== null && value !== 'presentation') {
      setCommercialClass(null)
      setConditions([])
    }
  }

  function selectSourceView(item: typeof SOURCE_VIEWS[number] | null) {
    setOffset(0)
    setSourceWorkbook(item?.value ?? null)
    setEntityType(item?.identityType ?? null)
    if (item?.identityType !== 'presentation') {
      setCommercialClass(null)
      setConditions([])
    }
  }

  const { data, error, loading } = useQuery(
    () =>
      fetchCatalogIdentities({
        q: query || undefined,
        identityType: entityType ?? undefined,
        sourceWorkbook: sourceWorkbook ?? undefined,
        sortBy,
        commercialClass: commercialClass ?? undefined,
        conditions: conditions.length ? conditions : undefined,
        active: showArchived ? undefined : true,
        limit: PAGE_SIZE,
        offset,
      }),
    [query, entityType, sourceWorkbook, sortBy, showArchived, commercialClass, conditions, offset, retryKey],
  )

  useEffect(() => {
    requestedOffset.current = offset
  }, [offset])

  function search(event: React.FormEvent) {
    event.preventDefault()
    setOffset(0)
    setQuery(term.trim())
    window.requestAnimationFrame(() => resultsRef.current?.focus())
  }

  function changePage(nextOffset: number) {
    setOffset(nextOffset)
    window.requestAnimationFrame(() => resultsRef.current?.focus())
  }

  function openIdentity(identityId: string) {
    const table = resultsRef.current?.querySelector<HTMLElement>('.catalog-table-scroll')
    try {
      const saved = JSON.parse(sessionStorage.getItem(LIST_STATE_KEY) ?? '{}') as Partial<CatalogListState>
      sessionStorage.setItem(LIST_STATE_KEY, JSON.stringify({
        ...saved,
        tableScrollTop: table?.scrollTop ?? 0,
        tableScrollLeft: table?.scrollLeft ?? 0,
        windowScrollY: window.scrollY,
      }))
    } catch { /* recuperar filtros y posición es una mejora, no bloquea la navegación */ }
    navigate(`/catalogo/${encodeURIComponent(identityId)}`)
  }

  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const pages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const firstResult = data && data.total > 0 ? data.offset + 1 : 0
  const lastResult = data ? Math.min(data.offset + data.items.length, data.total) : 0
  const activeFilterCount = Number(Boolean(query)) + Number(Boolean(sourceWorkbook || entityType)) + Number(showArchived) + Number(Boolean(commercialClass)) + conditions.length

  useEffect(() => {
    if (!loading && data && data.offset === requestedOffset.current && (data.total === 0 ? data.offset > 0 : data.offset >= data.total)) {
      const validOffset = data.total === 0 ? 0 : Math.floor((data.total - 1) / PAGE_SIZE) * PAGE_SIZE
      requestedOffset.current = validOffset
      setOffset(validOffset)
    }
  }, [data, loading])

  useEffect(() => {
    if (loading || !data || data.offset !== requestedOffset.current || restoredPosition.current) return
    restoredPosition.current = true
    window.requestAnimationFrame(() => {
      const table = resultsRef.current?.querySelector<HTMLElement>('.catalog-table-scroll')
      if (table) {
        table.scrollTop = initialState.tableScrollTop ?? 0
        table.scrollLeft = initialState.tableScrollLeft ?? 0
      }
      const savedWindowScrollY = initialState.windowScrollY ?? 0
      if (savedWindowScrollY > 0) window.scrollTo(0, savedWindowScrollY)
    })
  }, [data, initialState.tableScrollLeft, initialState.tableScrollTop, initialState.windowScrollY, loading])

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Catálogo</p>
          <h1>Catálogo de medicamentos</h1>
          <p className='lede'>
            Elija primero el libro original —Especialidades, Medicamentos o Principios activos—
            para trabajar en una vista separada. La tabla se pagina en el servidor.
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
        <label className='field catalog-sort-control'>
          <span className='field__label'>Ordenar por</span>
          <select value={sortBy} onChange={(event) => { setOffset(0); setSortBy(event.target.value as CatalogIdentitySort) }}>
            {SORT_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <div className='filters catalog-source-views' role='group' aria-label='Libro Excel de origen'>
          <button type='button' className={`chip${sourceWorkbook === null ? ' chip--active' : ''}`} aria-pressed={sourceWorkbook === null} onClick={() => selectSourceView(null)}>Todo el catálogo</button>
          {SOURCE_VIEWS.map((item) => (
            <button
              key={item.value}
              type='button'
              className={`chip${sourceWorkbook === item.value ? ' chip--active' : ''}`}
              aria-pressed={sourceWorkbook === item.value}
              onClick={() => selectSourceView(item)}
            >
              {item.label}
            </button>
          ))}
          <span className='catalog-source-views__future'>Interacciones · pendiente de incorporar</span>
        </div>
        {sourceWorkbook === null ? <div className='filters' role='group' aria-label='Nivel farmacéutico del catálogo'>
          {ENTITY_FILTERS.map((item) => <button key={item.label} type='button' className={`chip${entityType === item.value ? ' chip--active' : ''}`} aria-pressed={entityType === item.value} onClick={() => selectEntityType(item.value)}>{item.label}</button>)}
        </div> : <p className='catalog-source-context'>Vista del libro: <strong>{SOURCE_LABELS[sourceWorkbook]}</strong> · tipo de registro: <strong>{ENTITY_LABELS[entityType ?? ''] ?? entityType}</strong></p>}
        {(entityType === null || entityType === 'presentation') && <>
          <div className='filters' role='group' aria-label='Clase comercial'>
            {CLASSIFICATION_FILTERS.map((item) => <button
              key={item.label}
              type='button'
              className={`chip${commercialClass === item.value ? ' chip--active' : ''}`}
              aria-pressed={commercialClass === item.value}
              onClick={() => selectCommercialClass(item.value)}
            >{item.label}</button>)}
          </div>
          <fieldset className='catalog-condition-filter'>
            <legend>Condiciones</legend>
            <div className='catalog-condition-filter__options'>
              {CONDITION_FILTERS.map((item) => <label key={item.value}>
                <input type='checkbox' checked={conditions.includes(item.value)} onChange={() => toggleCondition(item.value)} />
                {item.label}
              </label>)}
            </div>
            <small className='field__hint'>Al marcar varias, se muestran los registros que cumplen todas.</small>
          </fieldset>
        </>}
        <label className='catalog-toggle'>
          <input
            type='checkbox'
            checked={showArchived}
            onChange={(event) => { setOffset(0); setShowArchived(event.target.checked) }}
          />
          Incluir archivados
        </label>
        <button type='button' className='button button--ghost' onClick={clearFilters} disabled={activeFilterCount === 0 && !term}>
          Limpiar filtros{activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}
        </button>
      </form>

      <div ref={resultsRef} tabIndex={-1} aria-label='Resultados del catálogo' className='catalog-results'>
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
            <p className='muted catalog-list-summary' aria-live='polite' aria-atomic='true'>
              <span><strong>{data.total.toLocaleString('es-ES')}</strong> registros{activeFilterCount > 0 ? ` · ${activeFilterCount} filtros activos` : ''}</span>
              <span>Mostrando {firstResult.toLocaleString('es-ES')}–{lastResult.toLocaleString('es-ES')} · página {page} de {pages}</span>
            </p>
            <div className='catalog-table-scroll' role='region' aria-label='Tabla de registros; desplazamiento horizontal disponible' tabIndex={0}>
              <table className='table'>
                <caption className='visually-hidden'>Resultados del catálogo de medicamentos</caption>
                <thead>
                  <tr>
                    <th scope='col'>Descripción</th>
                    <th scope='col'>Identificador</th>
                    <th scope='col'>Tipo</th>
                    <th scope='col'>Libro de origen</th>
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
                      <td>{item.source_workbook ? SOURCE_LABELS[item.source_workbook] : 'Sin libro maestro asociado'}</td>
                      <td><span className={`badge ${item.active ? 'badge--validado' : 'badge--descartado'}`}>{item.active ? 'Vigente' : 'Archivado'}</span></td>
                      <td>
                        <button
                          type='button'
                          className='button'
                          onClick={() => openIdentity(item.id)}
                        >
                          Abrir expediente
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className='pagination'>
              <button
                type='button'
                className='button'
                disabled={offset === 0}
                onClick={() => changePage(Math.max(0, offset - PAGE_SIZE))}
              >
                Anterior
              </button>
              <button
                type='button'
                className='button'
                disabled={offset + PAGE_SIZE >= data.total}
                onClick={() => changePage(offset + PAGE_SIZE)}
              >
                Siguiente
              </button>
            </div>
          </>
        )}
        </AsyncBoundary>
      </div>
    </div>
  )
}
