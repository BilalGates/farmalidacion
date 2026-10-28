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
import { Check, FileText, Plus, RefreshCw, Search } from 'lucide-react'
import { FilterBar, FilterSelect, FilterText } from '../components/FilterBar'
import { PageHeader } from '../components/PageHeader'
import { useCapability } from '../auth/SessionContext'

const labels: Record<string, string> = {
  pendiente: 'Pendiente', asignado: 'Asignado', en_revision: 'En revisión',
  completado: 'Completado', requiere_segunda_revision: 'Segunda revisión', bloqueado: 'Bloqueado',
}

export function QueueScreen({ reviewer }: { reviewer: Reviewer | null }) {
  const canReview = useCapability('review.write')
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

  const filters = {
    state: filter,
    entity_type: entityFilter,
    block_type: blockFilter,
    review_set: setFilter,
    requires_second_review: secondFilter === '' ? undefined : secondFilter === 'true',
  }

  const activeFilterCount = [filter, entityFilter, blockFilter, setFilter, secondFilter].filter(Boolean).length
  const filterKey = JSON.stringify(filters)

  // Los filtros se aplican al cambiar, como en el resto de la aplicación.
  async function reload() {
    setLoading(true)
    try {
      const result = await fetchQueue(filters)
      setItems(result)
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
  }, []) // La recarga inicial no lleva filtros.

  const firstFilters = useRef(true)
  useEffect(() => {
    if (firstFilters.current) { firstFilters.current = false; return }
    void reload()
  }, [filterKey]) // Recarga sólo cuando cambian los filtros.

  async function act(operation: () => Promise<unknown>) {
    setBusy(true)
    setError('')
    try { await operation(); await reload() }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'No se pudo completar la operación.') }
    finally { setBusy(false) }
  }

  const visibleItems = items
  function clearFilters() {
    setStateFilter('')
    setEntityFilter('')
    setBlockFilter('')
    setReviewSetFilter('')
    setSecondFilter('')
  }

  return <div className='screen'>
    <PageHeader eyebrow='Trabajo del equipo' title='Cola de revisión' description='Filtra los pendientes, selecciónalos y asígnate un lote antes de abrir cada ficha.' actions={<div className='page-stat' aria-label={`${items.length} registros en la cola`}>
        <strong>{items.length}</strong><span>En cola</span>
      </div>} />
    {error && <div role='alert' className='alert alert--error'>{error} {stale && items.length > 0 && 'La lista muestra la última carga correcta y puede estar desactualizada.'} <button type='button' className='button button--secondary' disabled={loading || busy} onClick={() => void reload()}>Reintentar carga</button></div>}
    <form className='queue-add' aria-label='Añadir registro a la cola' onSubmit={(event) => {
                event.preventDefault()
                void act(async () => {
                  await enqueueRecord(recordId.trim(), reviewSet, requiresSecondReview)
                  setRecordId('')
                })
              }}>
                <span className='queue-add__title'>Añadir a la cola</span>
                <label className='field queue-add__record'><span className='field__label'>Registro</span>
                  <span className='input-with-icon'><Search size={16} aria-hidden='true' /><input placeholder='Identificador del registro' aria-label='Identificador del registro' value={recordId} onChange={(event) => setRecordId(event.target.value)} required /></span>
                </label>
                <label className='field'><span className='field__label'>Conjunto</span>
                  <select value={reviewSet} onChange={(event) => setReviewSet(event.target.value as QueueItem['review_set'])}>
                    <option value='corpus'>Corpus</option><option value='oro'>Oro</option><option value='medida'>Medida</option>
                  </select>
                </label>
                <label className='queue-check'><input type='checkbox' checked={requiresSecondReview} onChange={(event) => setRequiresSecondReview(event.target.checked)} /> Doble validación</label>
                <button className='button button--primary' disabled={!canReview || busy || !recordId.trim()}><Plus size={16} aria-hidden='true' />Añadir</button>
          </form>
    <FilterBar label='Filtrar la cola' activeCount={activeFilterCount} onClear={clearFilters}
      aside={<button type='button' className='button button--ghost button--sm' aria-label='Actualizar cola' disabled={busy || loading} onClick={() => void reload()}><RefreshCw size={15} aria-hidden='true' /> Actualizar</button>}>
      <FilterSelect label='Estado' value={filter} options={[{ value: '', label: 'Todos' }, ...Object.entries(labels).map(([value, label]) => ({ value, label }))]} onChange={setStateFilter} />
      <FilterText label='Entidad' value={entityFilter} placeholder='Todas' onCommit={setEntityFilter} />
      <FilterText label='Bloque' value={blockFilter} placeholder='Todos' onCommit={setBlockFilter} />
      <FilterSelect label='Conjunto' name='Filtrar por conjunto' value={setFilter} options={[{ value: '', label: 'Todos' }, { value: 'oro', label: 'Oro' }, { value: 'medida', label: 'Medida' }, { value: 'corpus', label: 'Corpus' }]} onChange={setReviewSetFilter} />
      <FilterSelect label='Doble validación' name='Filtrar doble validación' value={secondFilter} options={[{ value: '', label: 'Todas' }, { value: 'true', label: 'Sí' }, { value: 'false', label: 'No' }]} onChange={setSecondFilter} />
    </FilterBar>
    <section className='panel queue-panel'>
      {selected.length > 0 && <div className='queue-batch'>
        <span>{selected.length} seleccionados</span>
        <button className='button button--primary' disabled={!canReview || busy || !reviewer} onClick={() => void act(() => assignQueueBatch(items.filter((item) => selected.includes(item.target_record_id)), reviewer!.identifier))}>Asignarme lote</button>
      </div>}
      {loading && <div className='empty-state' role='status'><span className='empty-state__icon' aria-hidden='true'><RefreshCw size={18} /></span><h2>Cargando cola…</h2></div>}
      {!loading && !error && visibleItems.length === 0 && <div className='empty-state queue-empty'><span className='empty-state__icon' aria-hidden='true'><Check size={23} /></span><h2>{activeFilterCount > 0 ? 'No hay resultados' : 'La cola está al día'}</h2><p>{activeFilterCount > 0 ? 'Ningún registro coincide con los filtros aplicados.' : 'Cuando se añadan registros aparecerán aquí, listos para asignar.'}</p>{activeFilterCount > 0 && <button type='button' className='button button--secondary' onClick={() => void clearFilters()}>Limpiar filtros</button>}</div>}
      {!loading && visibleItems.length > 0 && <ul className='queue-list'>
        {visibleItems.map((item) => <li key={item.target_record_id}>
          <input type='checkbox' aria-label={`Seleccionar ${item.target_record_id}`} checked={selected.includes(item.target_record_id)} disabled={!['pendiente', 'asignado', 'en_revision'].includes(item.state)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, item.target_record_id] : current.filter((id) => id !== item.target_record_id))} />
          <div className='queue-list__identity'><span className='queue-list__icon' aria-hidden='true'><FileText size={15} /></span><span><strong>{item.target_record_id}</strong><small className='queue-list__meta'><span>{item.assignee_id ? `Asignado a ${item.assignee_id}` : 'Sin asignar'}</span><span>Conjunto {item.review_set ?? 'corpus'}</span>{item.requires_second_review && <span>Doble validación</span>}</small></span></div>
          <span className={`badge badge--${item.state}`}>{labels[item.state] ?? item.state}</span>
          <div className='queue-list__actions'>
          <button className='button' disabled={!canReview || busy || loading || !reviewer || ['completado', 'bloqueado'].includes(item.state)}
            onClick={() => void act(() => assignQueue(item.target_record_id, reviewer!.identifier))}>
            Asignarme
          </button>
          {canReview && item.assignee_id === reviewer?.identifier && ['asignado', 'en_revision'].includes(item.state) && <>
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
  </div>
}
