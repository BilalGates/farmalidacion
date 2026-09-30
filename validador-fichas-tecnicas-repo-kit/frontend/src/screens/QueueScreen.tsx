import { useEffect, useRef, useState } from 'react'
import {
  ApiError,
  assignQueue,
  assignQueueBatch,
  enqueueRecord,
  fetchQueue,
  transitionQueue,
} from '../api/client'
import type { QueueItem } from '../api/client'
import type { Reviewer } from '../api/types'
import { navigate } from '../navigation'
import { Check, Plus, RefreshCw, Search } from 'lucide-react'
import { FilterWorkspace } from '../components/FilterWorkspace'
import { PageHeader } from '../components/PageHeader'

const labels: Record<string, string> = {
  pendiente: 'Pendiente', asignado: 'Asignado', en_revision: 'En revisión',
  completado: 'Completado', requiere_segunda_revision: 'Segunda revisión', bloqueado: 'Bloqueado',
}

export function QueueScreen({ reviewer }: { reviewer: Reviewer | null }) {
  const [items, setItems] = useState<QueueItem[]>([])
  const [error, setError] = useState('')
  const [stale, setStale] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [recordId, setRecordId] = useState('')
  const [filter, setStateFilter] = useState('')
  const [entityFilter, setEntityFilter] = useState('')
  const [blockFilter, setBlockFilter] = useState('')
  const [setFilter, setReviewSetFilter] = useState('')
  const [secondFilter, setSecondFilter] = useState('')
  const [reviewSet, setReviewSet] = useState<QueueItem['review_set']>('corpus')
  const [requiresSecondReview, setRequiresSecondReview] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [appliedFilterCount, setAppliedFilterCount] = useState(0)
  const appliedFilters = useRef<NonNullable<Parameters<typeof fetchQueue>[0]>>({})

  const filters = {
    state: filter,
    entity_type: entityFilter,
    block_type: blockFilter,
    review_set: setFilter,
    requires_second_review: secondFilter === '' ? undefined : secondFilter === 'true',
  }

  const activeFilterCount = [filter, entityFilter, blockFilter, setFilter, secondFilter].filter(Boolean).length
  const filtersChanged = JSON.stringify(filters) !== JSON.stringify(appliedFilters.current)

  async function reload(applyDraft = false) {
    const requestedFilters = applyDraft ? filters : appliedFilters.current
    setLoading(true)
    try {
      const result = await fetchQueue(requestedFilters)
      setItems(result)
      if (applyDraft) {
        appliedFilters.current = requestedFilters
        setAppliedFilterCount(activeFilterCount)
      }
      setSelected([])
      setError('')
      setStale(false)
    }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'No se pudo cargar la cola.'); setStale(true) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    let active = true
    fetchQueue().then((result) => { if (active) setItems(result) })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof ApiError ? cause.message : 'No se pudo cargar la cola.')
      }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, []) // La recarga inicial no aplica filtros hasta que la persona los solicite.

  async function act(operation: () => Promise<unknown>) {
    setBusy(true)
    setError('')
    try { await operation(); await reload() }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'No se pudo completar la operación.') }
    finally { setBusy(false) }
  }

  const visibleItems = items
  async function clearFilters() {
    setStateFilter('')
    setEntityFilter('')
    setBlockFilter('')
    setReviewSetFilter('')
    setSecondFilter('')
    setLoading(true)
    try { setItems(await fetchQueue()); appliedFilters.current = {}; setAppliedFilterCount(0); setSelected([]); setError(''); setStale(false) }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'No se pudo cargar la cola.'); setStale(true) }
    finally { setLoading(false) }
  }

  return <div className='screen'>
    <PageHeader eyebrow='Trabajo del equipo' title='Cola de revisión' description='Asigne, filtre y abra registros desde un único espacio de trabajo.' actions={<div className='page-stat' aria-label={`${items.length} registros en la cola`}>
        <strong>{items.length}</strong><span>En cola</span>
      </div>} />
    {error && <div role='alert' className='alert alert--error'>{error} {stale && items.length > 0 && 'La lista muestra la última carga correcta y puede estar desactualizada.'} <button type='button' className='button button--secondary' disabled={loading || busy} onClick={() => void reload()}>Reintentar carga</button></div>}
    <form className='queue-add panel' onSubmit={(event) => {
          event.preventDefault()
          void act(async () => {
            await enqueueRecord(recordId.trim(), reviewSet, requiresSecondReview)
            setRecordId('')
          })
        }}>
          <div className='queue-toolbar__title'><Plus size={17} aria-hidden='true' /><span>Añadir registro a la cola</span></div>
          <label className='field queue-add__record'><span className='field__label'>Registro</span>
            <span className='input-with-icon'><Search size={16} aria-hidden='true' /><input placeholder='Identificador del registro' aria-label='Identificador del registro' value={recordId} onChange={(event) => setRecordId(event.target.value)} required /></span>
          </label>
          <label className='field'><span className='field__label'>Conjunto</span>
            <select value={reviewSet} onChange={(event) => setReviewSet(event.target.value as QueueItem['review_set'])}>
              <option value='corpus'>Corpus</option><option value='oro'>Oro</option><option value='medida'>Medida</option>
            </select>
          </label>
          <label className='queue-check'><input type='checkbox' checked={requiresSecondReview} onChange={(event) => setRequiresSecondReview(event.target.checked)} /> Doble validación</label>
          <button className='button button--primary' disabled={busy || !recordId.trim()}><Plus size={16} aria-hidden='true' />Añadir</button>
    </form>
    <FilterWorkspace
      title='Filtros de revisión'
      storageKey='farmalidacion.filters.queue.closed'
      activeCount={appliedFilterCount}
      className='queue-workspace'
      filters={
        <>
          <label className='field'><span className='field__label'>Estado</span><select value={filter} onChange={(event) => setStateFilter(event.target.value)}><option value=''>Todos</option>{Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label className='field'><span className='field__label'>Entidad</span><input placeholder='Todas' value={entityFilter} onChange={(event) => setEntityFilter(event.target.value)} /></label>
          <label className='field'><span className='field__label'>Bloque</span><input placeholder='Todos' value={blockFilter} onChange={(event) => setBlockFilter(event.target.value)} /></label>
          <label className='field'><span className='field__label'>Conjunto</span><select aria-label='Filtrar por conjunto' value={setFilter} onChange={(event) => setReviewSetFilter(event.target.value)}><option value=''>Todos</option><option value='oro'>Oro</option><option value='medida'>Medida</option><option value='corpus'>Corpus</option></select></label>
          <label className='field'><span className='field__label'>Doble validación</span><select aria-label='Filtrar doble validación' value={secondFilter} onChange={(event) => setSecondFilter(event.target.value)}><option value=''>Todas</option><option value='true'>Sí</option><option value='false'>No</option></select></label>
          <div className='filter-panel__actions'>
            {filtersChanged && <span role='status'>Filtros modificados sin aplicar</span>}
            <button type='button' className='button button--primary' aria-label='Aplicar filtros' disabled={busy || loading} onClick={() => void reload(true)}>Aplicar filtros</button>
            <button type='button' className='button button--secondary' disabled={busy || loading || (activeFilterCount === 0 && appliedFilterCount === 0)} onClick={() => void clearFilters()}>Limpiar filtros</button>
            <button type='button' className='button button--ghost' aria-label='Actualizar cola' disabled={busy || loading} onClick={() => void reload()}><RefreshCw size={17} aria-hidden='true' /> Actualizar</button>
          </div>
        </>
      }
    >
    <section className='panel queue-panel'>
      {selected.length > 0 && <div className='queue-batch'>
        <span>{selected.length} seleccionados</span>
        <button className='button button--primary' disabled={busy || !reviewer} onClick={() => void act(() => assignQueueBatch(items.filter((item) => selected.includes(item.target_record_id)), reviewer!.identifier))}>Asignarme lote</button>
      </div>}
      {loading && <div className='empty-state' role='status'><span className='empty-state__icon'>↻</span><h2>Cargando cola…</h2></div>}
      {!loading && !error && visibleItems.length === 0 && <div className='empty-state queue-empty'><span className='empty-state__icon' aria-hidden='true'><Check size={23} /></span><h2>{appliedFilterCount > 0 ? 'No hay resultados' : 'La cola está al día'}</h2><p>{appliedFilterCount > 0 ? 'Ningún registro coincide con los filtros aplicados.' : 'Cuando se añadan registros aparecerán aquí, listos para asignar.'}</p>{appliedFilterCount > 0 && <button type='button' className='button button--secondary' onClick={() => void clearFilters()}>Limpiar filtros</button>}</div>}
      {!loading && visibleItems.length > 0 && <ul className='queue-list'>
        {visibleItems.map((item) => <li key={item.target_record_id}>
          <input type='checkbox' aria-label={`Seleccionar ${item.target_record_id}`} checked={selected.includes(item.target_record_id)} disabled={!['pendiente', 'asignado', 'en_revision'].includes(item.state)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, item.target_record_id] : current.filter((id) => id !== item.target_record_id))} />
          <div className='queue-list__identity'><span className='queue-list__icon' aria-hidden='true'>▤</span><span><strong>{item.target_record_id}</strong><small className='queue-list__meta'><span>{item.assignee_id ? `Asignado a ${item.assignee_id}` : 'Sin asignar'}</span><span>Conjunto {item.review_set ?? 'corpus'}</span>{item.requires_second_review && <span>Doble validación</span>}</small></span></div>
          <span className={`badge badge--${item.state}`}>{labels[item.state] ?? item.state}</span>
          <div className='queue-list__actions'>
          <button className='button' disabled={busy || loading || !reviewer || ['completado', 'bloqueado'].includes(item.state)}
            onClick={() => void act(() => assignQueue(item.target_record_id, reviewer!.identifier))}>
            Asignarme
          </button>
          {item.assignee_id === reviewer?.identifier && ['asignado', 'en_revision'].includes(item.state) && <>
            {item.state === 'asignado' && <button className='button' disabled={busy || loading}
              onClick={() => void act(() => transitionQueue(item, reviewer.identifier, 'en_revision'))}>
              Iniciar revisión
            </button>}
            <button className='button' disabled={busy || loading}
              onClick={() => void act(() => transitionQueue(item, reviewer.identifier, 'pendiente'))}>
              Devolver a pendientes
            </button>
          </>}
          <button className='button' onClick={() => navigate(`/registros/${encodeURIComponent(item.target_record_id)}`)}>
            Abrir registro
          </button>
          </div>
        </li>)}
      </ul>}
    </section>
    </FilterWorkspace>
  </div>
}
