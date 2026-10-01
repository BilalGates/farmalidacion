import { useEffect, useRef, useState } from 'react'

import { assignQueue, enqueueRecord, fetchCatalogIdentities, fetchQueue, transitionQueue } from '../api/client'
import type { QueueItem } from '../api/client'
import type { CatalogIdentitySort, CatalogIdentityType, CatalogSourceWorkbook } from '../api/types'
import { useQuery } from '../api/useQuery'
import { AsyncBoundary } from '../components/AsyncState'
import { FilterWorkspace } from '../components/FilterWorkspace'
import { PageHeader } from '../components/PageHeader'
import { orDash } from '../domain/format'
import { CATALOG_LIST_STATE_KEY } from '../domain/catalogSourceNavigation'
import { RecordDialog } from '../components/RecordDialog'
import { ReviewerSelect } from '../components/ReviewerSelect'
import { CatalogIdentityScreen } from './CatalogIdentityScreen'
import { ReviewScreen } from './ReviewScreen'
import { SecondReviewScreen } from './SecondReviewScreen'
import type { CatalogIdentityPage, Reviewer } from '../api/types'

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
const REVIEW_LABELS: Record<string, string> = {
  pendiente: 'Pendiente', asignado: 'Asignado', en_revision: 'En revisión',
  completado: 'Completado', requiere_segunda_revision: 'Segunda revisión', bloqueado: 'Bloqueado',
}
type ReviewScope = 'all' | 'pending' | 'unassigned' | 'mine' | 'second' | 'completed'
const REVIEW_FILTERS: { value: ReviewScope; label: string }[] = [
  { value: 'all', label: 'Todos' }, { value: 'pending', label: 'Pendientes' },
  { value: 'unassigned', label: 'Sin asignar' }, { value: 'mine', label: 'Mis tareas' },
  { value: 'second', label: 'Doble validación' }, { value: 'completed', label: 'Completados' },
]

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
  reviewScope: ReviewScope
  tableScrollTop: number
  tableScrollLeft: number
  windowScrollY: number
}

function readListState(): Partial<CatalogListState> {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(CATALOG_LIST_STATE_KEY) ?? 'null')
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
      reviewScope: REVIEW_FILTERS.some((item) => item.value === saved.reviewScope) ? saved.reviewScope ?? 'all' : 'all',
      tableScrollTop: typeof saved.tableScrollTop === 'number' && saved.tableScrollTop >= 0 ? saved.tableScrollTop : 0,
      tableScrollLeft: typeof saved.tableScrollLeft === 'number' && saved.tableScrollLeft >= 0 ? saved.tableScrollLeft : 0,
      windowScrollY: typeof saved.windowScrollY === 'number' && saved.windowScrollY >= 0 ? saved.windowScrollY : 0,
    }
  } catch {
    return {}
  }
}

export function RealRecordListScreen({ reviewer = null, reviewers = [], onReviewerChange, initialReviewScope = 'all', initialSecondReviewOpen = false }: { reviewer?: Reviewer | null; reviewers?: Reviewer[]; onReviewerChange?: (id: string) => void; initialReviewScope?: ReviewScope; initialSecondReviewOpen?: boolean }) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [visited, setVisited] = useState<string[]>([])
  const [recordId, setRecordId] = useState<string | null>(null)
  const [navigationPage, setNavigationPage] = useState<CatalogIdentityPage | null>(null)
  const [navigating, setNavigating] = useState(false)
  const [navigationError, setNavigationError] = useState('')
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
  const [reviewScope, setReviewScope] = useState<ReviewScope>(initialReviewScope === 'all' ? initialState.reviewScope ?? 'all' : initialReviewScope)
  const [secondReviewOpen, setSecondReviewOpen] = useState(initialSecondReviewOpen)
  const [retryKey, setRetryKey] = useState(0)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [queueError, setQueueError] = useState('')
  const [queueLoading, setQueueLoading] = useState(true)
  const [queueBusy, setQueueBusy] = useState<string | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)
  const tableScrollRef = useRef<HTMLDivElement>(null)
  const [tableOverflows, setTableOverflows] = useState(false)
  const requestedOffset = useRef(offset)
  const restoredPosition = useRef(false)

  async function addToQueue(recordId: string) {
    setQueueBusy(recordId)
    setQueueError('')
    try { const item = await enqueueRecord(recordId); setQueue((current) => [...current.filter((entry) => entry.target_record_id !== recordId), item]); if (reviewScope !== 'all') setRetryKey((key) => key + 1) }
    catch (cause) { setQueueError(cause instanceof Error ? cause.message : 'No se pudo añadir el registro a revisión.') }
    finally { setQueueBusy(null) }
  }

  async function updateQueue(operation: () => Promise<QueueItem>) {
    setQueueBusy('updating')
    setQueueError('')
    try { const item = await operation(); setQueue((current) => [...current.filter((entry) => entry.target_record_id !== item.target_record_id), item]); setRetryKey((key) => key + 1) }
    catch (cause) { setQueueError(cause instanceof Error ? cause.message : 'No se pudo actualizar la revisión.') }
    finally { setQueueBusy(null) }
  }

  useEffect(() => {
    const state: CatalogListState = {
      term, query, offset, entityType, sourceWorkbook, showArchived, commercialClass, conditions, sortBy, reviewScope,
      tableScrollTop: initialState.tableScrollTop ?? 0,
      tableScrollLeft: initialState.tableScrollLeft ?? 0,
      windowScrollY: initialState.windowScrollY ?? 0,
    }
    try { sessionStorage.setItem(CATALOG_LIST_STATE_KEY, JSON.stringify(state)) } catch { /* almacenamiento opcional */ }
  }, [term, query, offset, entityType, sourceWorkbook, showArchived, commercialClass, conditions, sortBy, reviewScope])

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
    setReviewScope('all')
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
        reviewScope,
        reviewerId: reviewScope === 'mine' ? reviewer?.identifier : undefined,
        commercialClass: commercialClass ?? undefined,
        conditions: conditions.length ? conditions : undefined,
        active: showArchived ? undefined : true,
        limit: PAGE_SIZE,
        offset,
      }),
    [query, entityType, sourceWorkbook, sortBy, reviewScope, reviewer?.identifier, showArchived, commercialClass, conditions, offset, retryKey],
  )

  useEffect(() => {
    if (!data?.items.some((item) => item.target_record_id)) return
    let active = true
    setQueueLoading(true)
    fetchQueue().then((items) => { if (active) { if (!Array.isArray(items)) throw new Error('La respuesta de revisión no es válida.'); setQueue(items); setQueueError('') } })
      .catch((cause: unknown) => { if (active) setQueueError(cause instanceof Error ? cause.message : 'No se pudo consultar el estado de revisión.') })
      .finally(() => { if (active) setQueueLoading(false) })
    return () => { active = false }
  }, [data])

  useEffect(() => {
    const table = tableScrollRef.current
    if (!table) return
    const measure = () => setTableOverflows(table.scrollWidth > table.clientWidth + 1)
    measure()
    window.addEventListener('resize', measure)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    observer?.observe(table)
    return () => { window.removeEventListener('resize', measure); observer?.disconnect() }
  }, [data, loading])

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
      const saved = JSON.parse(sessionStorage.getItem(CATALOG_LIST_STATE_KEY) ?? '{}') as Partial<CatalogListState>
      sessionStorage.setItem(CATALOG_LIST_STATE_KEY, JSON.stringify({
        ...saved,
        tableScrollTop: table?.scrollTop ?? 0,
        tableScrollLeft: table?.scrollLeft ?? 0,
        windowScrollY: window.scrollY,
      }))
    } catch { /* recuperar filtros y posición es una mejora, no bloquea la navegación */ }
    setNavigationPage(data)
    showIdentity(identityId)
  }

  function showIdentity(id: string) {
    setVisited(ids => ids.includes(id) ? ids : [...ids, id])
    setSelectedId(id)
    setRecordId(null)
    setNavigationError('')
  }

  const selectedIndex = navigationPage?.items.findIndex(item => item.id === selectedId) ?? -1
  async function adjacent(direction: -1 | 1) {
    if (!navigationPage || selectedIndex < 0 || navigating) return
    const index = selectedIndex + direction
    if (index >= 0 && index < navigationPage.items.length) {
      showIdentity(navigationPage.items[index].id)
      return
    }
    setNavigating(true)
    setNavigationError('')
    try {
      const nextOffset = navigationPage.offset + direction * PAGE_SIZE
      const next = await fetchCatalogIdentities({
        q: query || undefined, identityType: entityType ?? undefined,
        sourceWorkbook: sourceWorkbook ?? undefined, sortBy,
        commercialClass: commercialClass ?? undefined,
        conditions: conditions.length ? conditions : undefined,
        active: showArchived ? undefined : true, reviewScope,
        reviewerId: reviewScope === 'mine' ? reviewer?.identifier : undefined,
        limit: PAGE_SIZE, offset: nextOffset,
      })
      const candidate = direction === 1 ? next.items[0] : next.items.at(-1)
      if (!candidate) { setNavigationError('No hay más registros en esta dirección.'); return }
      setNavigationPage(next)
      setOffset(nextOffset)
      showIdentity(candidate.id)
    } catch (cause) {
      setNavigationError(cause instanceof Error ? cause.message : 'No se pudo abrir el registro.')
    } finally { setNavigating(false) }
  }

  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const pages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const firstResult = data && data.total > 0 ? data.offset + 1 : 0
  const lastResult = data ? Math.min(data.offset + data.items.length, data.total) : 0
  const activeFilterCount = Number(Boolean(query)) + Number(Boolean(sourceWorkbook || entityType)) + Number(showArchived) + Number(Boolean(commercialClass)) + Number(reviewScope !== 'all') + conditions.length

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
    <div className='screen catalog-screen'>
      <FilterWorkspace
        title='Filtros del catálogo'
        storageKey='farmalidacion.filters.catalog.closed'
        className='catalog-filter-workspace'
        activeCount={activeFilterCount}
        filters={
          <>
            <form className='toolbar catalog-search-toolbar' onSubmit={search} role='search'>
              <label className='field'>
                <span className='field__label'>Buscar</span>
                <input type='search' value={term} placeholder='CN, nombre o principio activo' onChange={(event) => setTerm(event.target.value)} />
              </label>
              <button type='submit' className='button button--primary'>Buscar</button>
              <label className='field catalog-sort-control'>
                <span className='field__label'>Ordenar por</span>
                <select value={sortBy} onChange={(event) => { setOffset(0); setSortBy(event.target.value as CatalogIdentitySort) }}>
                  {SORT_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
            </form>
            <div className='filter-group'>
              <span className='field__label'>Trabajo de revisión</span>
              <div className='filter-choice-list' role='group' aria-label='Filtrar trabajo de revisión'>
                {REVIEW_FILTERS.map((item) => <button key={item.value} type='button' className={`chip${reviewScope === item.value ? ' chip--active' : ''}`} aria-pressed={reviewScope === item.value} disabled={item.value === 'mine' && !reviewer} onClick={() => { setOffset(0); setReviewScope(item.value) }}>{item.label}</button>)}
              </div>
              {!reviewer && <small className='field__hint'>Seleccione un revisor para ver «Mis tareas».</small>}
            </div>
            <div className='filter-group'>
              <span className='field__label'>Libro de origen</span>
              <div className='filter-choice-list' role='group' aria-label='Libro Excel de origen'>
                <button type='button' className={`chip${sourceWorkbook === null ? ' chip--active' : ''}`} aria-pressed={sourceWorkbook === null} onClick={() => selectSourceView(null)}>Todo el catálogo</button>
                {SOURCE_VIEWS.map((item) => <button key={item.value} type='button' className={`chip${sourceWorkbook === item.value ? ' chip--active' : ''}`} aria-pressed={sourceWorkbook === item.value} onClick={() => selectSourceView(item)}>{item.label}</button>)}
              </div>
            </div>
            {sourceWorkbook === null ? (
              <div className='filter-group'>
                <span className='field__label'>Nivel farmacéutico</span>
                <div className='filter-choice-list' role='group' aria-label='Nivel farmacéutico del catálogo'>
                  {ENTITY_FILTERS.map((item) => <button key={item.label} type='button' className={`chip${entityType === item.value ? ' chip--active' : ''}`} aria-pressed={entityType === item.value} onClick={() => selectEntityType(item.value)}>{item.label}</button>)}
                </div>
              </div>
            ) : <p className='catalog-source-context'>Libro: <strong>{SOURCE_LABELS[sourceWorkbook]}</strong><br />Tipo: <strong>{ENTITY_LABELS[entityType ?? ''] ?? entityType}</strong></p>}
            {(entityType === null || entityType === 'presentation') && <>
              <div className='filter-group'>
                <span className='field__label'>Clase comercial</span>
                <div className='filter-choice-list' role='group' aria-label='Clase comercial'>
                  {CLASSIFICATION_FILTERS.map((item) => <button key={item.label} type='button' className={`chip${commercialClass === item.value ? ' chip--active' : ''}`} aria-pressed={commercialClass === item.value} onClick={() => selectCommercialClass(item.value)}>{item.label}</button>)}
                </div>
              </div>
              <fieldset className='filter-group catalog-condition-filter'>
                <legend>Condiciones</legend>
                <div className='catalog-condition-filter__options'>
                  {CONDITION_FILTERS.map((item) => <label key={item.value}>
                    <input type='checkbox' checked={conditions.includes(item.value)} onChange={() => toggleCondition(item.value)} />
                    {item.label}
                  </label>)}
                </div>
                <small className='field__hint'>Al marcar varias, se muestran registros que cumplen todas.</small>
              </fieldset>
            </>}
            <label className='catalog-toggle'>
              <input type='checkbox' checked={showArchived} onChange={(event) => { setOffset(0); setShowArchived(event.target.checked) }} />
              Incluir archivados
            </label>
            <button type='button' className='button button--secondary filter-reset' onClick={clearFilters} disabled={activeFilterCount === 0 && !term}>
              Limpiar filtros{activeFilterCount > 0 ? ` · ${activeFilterCount}` : ''}
            </button>
          </>
        }
      >
      <div ref={resultsRef} tabIndex={-1} aria-label='Resultados del catálogo' className='catalog-results'>
        <PageHeader className='catalog-results__head' title='Catálogo' description='Explora y revisa medicamentos, presentaciones y principios activos.' actions={<button type='button' className='button button--secondary' onClick={() => setSecondReviewOpen(true)}>Segundas validaciones</button>} />
        {queueError && <div className='alert alert--error' role='alert'>{queueError} <button type='button' className='button' onClick={() => setRetryKey((key) => key + 1)}>Reintentar</button></div>}
        {activeFilterCount > 0 && <div className='catalog-active-filters' aria-label='Filtros activos' onClickCapture={() => window.requestAnimationFrame(() => resultsRef.current?.focus({ preventScroll: true }))}>
          <span className='catalog-active-filters__label'>Filtros activos</span>
          {query && <button type='button' className='chip' onClick={() => { setQuery(''); setTerm(''); setOffset(0) }}>Búsqueda: {query} ×</button>}
          {sourceWorkbook && <button type='button' className='chip' onClick={() => selectSourceView(null)}>Libro: {SOURCE_LABELS[sourceWorkbook]} ×</button>}
          {entityType && !sourceWorkbook && <button type='button' className='chip' onClick={() => selectEntityType(null)}>Nivel: {ENTITY_LABELS[entityType] ?? entityType} ×</button>}
          {commercialClass && <button type='button' className='chip' onClick={() => { setCommercialClass(null); setOffset(0) }}>Clase: {CLASS_LABELS[commercialClass] ?? commercialClass} ×</button>}
          {conditions.map((value) => <button key={value} type='button' className='chip' onClick={() => toggleCondition(value)}>Condición: {CONDITION_LABELS[value] ?? value} ×</button>)}
          {showArchived && <button type='button' className='chip' onClick={() => { setShowArchived(false); setOffset(0) }}>Incluye archivados ×</button>}
          {reviewScope !== 'all' && <button type='button' className='chip' onClick={() => { setReviewScope('all'); setOffset(0) }}>Revisión: {REVIEW_FILTERS.find((item) => item.value === reviewScope)?.label} ×</button>}
        </div>}
        <AsyncBoundary
        loading={loading}
        error={error}
        empty={(data?.total ?? 0) === 0}
        emptyTitle={activeFilterCount > 0 ? 'No hay resultados con estos filtros' : 'No hay identidades en el catálogo'}
        emptyDetail={
          activeFilterCount > 0
            ? 'Pruebe con otros criterios o limpie los filtros para consultar todo el catálogo.'
            : 'Todavía no hay identidades disponibles. Consulte el estado de las fuentes de datos.'
        }
        emptyAction={activeFilterCount > 0 ? <button type='button' className='button button--secondary' onClick={clearFilters}>Limpiar filtros</button> : undefined}
        onRetry={() => setRetryKey((k) => k + 1)}
      >
        {data && (
          <>
            <div ref={tableScrollRef} className='catalog-table-scroll' role='region' aria-label={tableOverflows ? 'Tabla de registros; desplazamiento horizontal disponible' : 'Tabla de registros'} tabIndex={tableOverflows ? 0 : undefined}>
              <table className='table'>
                <caption className='visually-hidden'>Resultados del catálogo de medicamentos</caption>
                <thead>
                  <tr>
                    <th scope='col'>Descripción</th>
                    <th scope='col'>Identificador</th>
                    <th scope='col'>Tipo</th>
                    <th scope='col'>Libro de origen</th>
                    <th scope='col'>Estado</th>
                    <th scope='col'>Revisión</th>
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
                      <td className='catalog-review-cell'>{(() => {
                        const work = queue.find((entry) => entry.target_record_id === item.target_record_id)
                        return work ? <><span>{REVIEW_LABELS[work.state] ?? work.state}{work.assignee_id ? ` · ${work.assignee_id}` : ''}</span>
                          {reviewer && work.assignee_id === reviewer.identifier && work.state === 'asignado' && <button type='button' className='button button--secondary' disabled={queueBusy !== null} onClick={() => void updateQueue(() => transitionQueue(work, reviewer.identifier, 'en_revision'))}>Iniciar</button>}
                          {reviewer && !work.assignee_id && work.state === 'pendiente' && <button type='button' className='button button--secondary' disabled={queueBusy !== null} onClick={() => void updateQueue(() => assignQueue(work.target_record_id, reviewer.identifier))}>Asignarme</button>}
                        </> : item.target_record_id ? queueLoading ? <span className='muted'>Consultando…</span> : <button type='button' className='button button--secondary' disabled={queueBusy !== null || Boolean(queueError)} onClick={() => void addToQueue(item.target_record_id!)}>+ Revisar</button>
                            : <span className='muted'>Sin registro asociado</span>
                      })()}</td>
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

            <div className='catalog-results__footer'>
              <p className='muted catalog-list-summary' aria-live='polite' aria-atomic='true'>
                <span><strong>{data.total.toLocaleString('es-ES')}</strong> registros{activeFilterCount > 0 ? ` · ${activeFilterCount} filtros activos` : ''}</span>
                <span>Mostrando {firstResult.toLocaleString('es-ES')}–{lastResult.toLocaleString('es-ES')} · página {page} de {pages}</span>
              </p>
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
            </div>
          </>
        )}
        </AsyncBoundary>
      </div>
      </FilterWorkspace>
      <RecordDialog open={selectedId !== null} onClose={() => { if (!navigating) { setSelectedId(null); setRecordId(null) } }}>
        <header className='record-dialog__header'>
          <h2 id='record-dialog-title'>Expediente del registro</h2>
          {onReviewerChange && <ReviewerSelect reviewers={reviewers} value={reviewer?.identifier ?? ''} onChange={onReviewerChange} />}
          <nav aria-label='Navegación entre registros'>
            <button type='button' className='button' disabled={navigating || selectedIndex < 0 || (selectedIndex === 0 && navigationPage?.offset === 0)} onClick={() => void adjacent(-1)}>← Anterior registro</button>
            <button type='button' className='button' disabled={navigating || selectedIndex < 0 || !navigationPage || navigationPage.offset + selectedIndex + 1 >= navigationPage.total} onClick={() => void adjacent(1)}>Siguiente registro →</button>
            <button type='button' className='button button--secondary' disabled={navigating} onClick={() => { setSelectedId(null); setRecordId(null) }}>Cerrar</button>
          </nav>
          {selectedIndex >= 0 && navigationPage && <span className='muted'>Registro {navigationPage.offset + selectedIndex + 1} de {navigationPage.total}</span>}
          {navigating && <span role='status'>Cargando registro…</span>}
          {navigationError && <p role='alert'>{navigationError}</p>}
        </header>
        <div className='record-dialog__body'>
          {recordId && <><button type='button' className='button' onClick={() => setRecordId(null)}>← Volver al expediente</button><ReviewScreen key={recordId} recordId={recordId} reviewer={reviewer} compact /></>}
          {visited.map(id => <div key={id} hidden={id !== selectedId || recordId !== null}>
            <CatalogIdentityScreen identityId={id} reviewer={reviewer} embedded onOpenIdentity={showIdentity} onOpenRecord={setRecordId} />
          </div>)}
        </div>
      </RecordDialog>
      <RecordDialog open={secondReviewOpen} onClose={() => setSecondReviewOpen(false)} titleId='second-review-dialog-title'>
        <header className='record-dialog__header'><h2 id='second-review-dialog-title'>Segundas validaciones</h2><button type='button' className='button button--secondary' onClick={() => setSecondReviewOpen(false)}>Cerrar</button></header>
        <div className='record-dialog__body'><SecondReviewScreen reviewer={reviewer} /></div>
      </RecordDialog>
    </div>
  )
}
