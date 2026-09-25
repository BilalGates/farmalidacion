import { useEffect, useState } from 'react'
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
import { Check, ChevronDown, Filter, Plus, RefreshCw, Search, SlidersHorizontal, X } from 'lucide-react'

const labels: Record<string, string> = {
  pendiente: 'Pendiente', asignado: 'Asignado', en_revision: 'En revisión',
  completado: 'Completado', requiere_segunda_revision: 'Segunda revisión', bloqueado: 'Bloqueado',
}

export function QueueScreen({ reviewer }: { reviewer: Reviewer | null }) {
  const [items, setItems] = useState<QueueItem[]>([])
  const [error, setError] = useState('')
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
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)

  const filters = {
    state: filter,
    entity_type: entityFilter,
    block_type: blockFilter,
    review_set: setFilter,
    requires_second_review: secondFilter === '' ? undefined : secondFilter === 'true',
  }
  const advancedFilterCount = [entityFilter, blockFilter, secondFilter].filter(Boolean).length
  const activeFilters = [
    filter && { key: 'state', label: `Estado: ${labels[filter] ?? filter}`, clear: () => setStateFilter('') },
    setFilter && { key: 'set', label: `Conjunto: ${setFilter}`, clear: () => setReviewSetFilter('') },
    entityFilter && { key: 'entity', label: `Entidad: ${entityFilter}`, clear: () => setEntityFilter('') },
    blockFilter && { key: 'block', label: `Bloque: ${blockFilter}`, clear: () => setBlockFilter('') },
    secondFilter && { key: 'second', label: `Doble validación: ${secondFilter === 'true' ? 'Sí' : 'No'}`, clear: () => setSecondFilter('') },
  ].filter(Boolean) as { key: string; label: string; clear: () => void }[]

  async function reload() {
    setLoading(true)
    try { setItems(await fetchQueue(filters)); setSelected([]); setError('') }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'No se pudo cargar la cola.') }
    finally { setLoading(false) }
  }

  async function clearFilters() {
    setStateFilter('')
    setEntityFilter('')
    setBlockFilter('')
    setReviewSetFilter('')
    setSecondFilter('')
    setLoading(true)
    try { setItems(await fetchQueue({})); setSelected([]); setError('') }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'No se pudo cargar la cola.') }
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

  return <div className='screen'>
    <div className='screen__head'>
      <div>
        <p className='eyebrow'>Trabajo del equipo</p>
        <h1>Cola de revisión</h1>
        <p className='lede'>Asigne, filtre y abra registros desde un único espacio de trabajo.</p>
      </div>
      <div className='page-stat' aria-label={`${items.length} registros en la cola`}>
        <strong>{items.length}</strong><span>En cola</span>
      </div>
    </div>
    {error && <p role='alert' className='alert alert--error'>{error} Recargue para consultar el estado actual.</p>}
    <section className='panel queue-panel'>
      <div className='queue-toolbar'>
        <form className='queue-add' onSubmit={(event) => {
          event.preventDefault()
          void act(async () => {
            await enqueueRecord(recordId.trim(), reviewSet, requiresSecondReview)
            setRecordId('')
          })
        }}>
          <div className='queue-toolbar__title'><Plus size={17} aria-hidden='true' /><span>Añadir a la cola</span></div>
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
        <form className='queue-filters' onSubmit={(event) => { event.preventDefault(); void reload() }}>
          <div className='queue-filters__head'>
            <div>
              <div className='queue-toolbar__title'><Filter size={17} aria-hidden='true' /><span>Encontrar registros</span></div>
              <p>Acote la cola por los criterios que utiliza con más frecuencia.</p>
            </div>
            <div className='queue-filters__utility'>
              <button type='button' className='button button--icon' aria-label='Actualizar cola' title='Actualizar cola' disabled={busy || loading} onClick={() => void reload()}><RefreshCw size={17} aria-hidden='true' /></button>
            </div>
          </div>
          <div className='queue-filters__primary'>
            <label className='field'><span className='field__label'>Estado</span><select value={filter} onChange={(event) => setStateFilter(event.target.value)}><option value=''>Cualquier estado</option>{Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
            <label className='field'><span className='field__label'>Conjunto</span><select aria-label='Filtrar por conjunto' value={setFilter} onChange={(event) => setReviewSetFilter(event.target.value)}><option value=''>Cualquier conjunto</option><option value='oro'>Oro</option><option value='medida'>Medida</option><option value='corpus'>Corpus</option></select></label>
            <button type='button' className={`button queue-filters__more${showAdvancedFilters ? ' is-open' : ''}`} aria-expanded={showAdvancedFilters} onClick={() => setShowAdvancedFilters((current) => !current)}><SlidersHorizontal size={16} aria-hidden='true' />Más filtros{advancedFilterCount > 0 && <span>{advancedFilterCount}</span>}<ChevronDown size={15} aria-hidden='true' /></button>
            <button className='button button--primary queue-filters__submit' aria-label='Aplicar filtros' disabled={busy || loading}>Aplicar</button>
          </div>
          {showAdvancedFilters && <div className='queue-filters__advanced'>
            <label className='field'><span className='field__label'>Entidad</span><input placeholder='Ej. medicamento' value={entityFilter} onChange={(event) => setEntityFilter(event.target.value)} /></label>
            <label className='field'><span className='field__label'>Bloque</span><input placeholder='Ej. general' value={blockFilter} onChange={(event) => setBlockFilter(event.target.value)} /></label>
            <label className='field'><span className='field__label'>Doble validación</span><select aria-label='Filtrar doble validación' value={secondFilter} onChange={(event) => setSecondFilter(event.target.value)}><option value=''>Indiferente</option><option value='true'>Sí</option><option value='false'>No</option></select></label>
          </div>}
          {activeFilters.length > 0 && <div className='queue-filters__active' aria-label='Filtros seleccionados'>
            <span>Seleccionados</span>
            {activeFilters.map((active) => <button type='button' key={active.key} onClick={active.clear}>{active.label}<X size={13} aria-hidden='true' /></button>)}
            <button type='button' className='queue-filters__clear' onClick={() => void clearFilters()} disabled={busy || loading}>Limpiar todo</button>
          </div>}
        </form>
      </div>
      {selected.length > 0 && <div className='queue-batch'>
        <span>{selected.length} seleccionados</span>
        <button className='button button--primary' disabled={busy || !reviewer} onClick={() => void act(() => assignQueueBatch(items.filter((item) => selected.includes(item.target_record_id)), reviewer!.identifier))}>Asignarme lote</button>
      </div>}
      {loading && <div className='empty-state' role='status'><span className='empty-state__icon'>↻</span><h2>Cargando cola…</h2></div>}
      {!loading && visibleItems.length === 0 && <div className='empty-state queue-empty'><span className='empty-state__icon' aria-hidden='true'><Check size={23} /></span><h2>{items.length === 0 ? 'La cola está al día' : 'No hay resultados'}</h2><p>{items.length === 0 ? 'Cuando se añadan registros aparecerán aquí, listos para asignar.' : 'Pruebe con otro filtro de estado.'}</p></div>}
      {!loading && visibleItems.length > 0 && <ul className='queue-list'>
        {visibleItems.map((item) => <li key={item.target_record_id}>
          <input type='checkbox' aria-label={`Seleccionar ${item.target_record_id}`} checked={selected.includes(item.target_record_id)} disabled={!['pendiente', 'asignado', 'en_revision'].includes(item.state)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, item.target_record_id] : current.filter((id) => id !== item.target_record_id))} />
          <div className='queue-list__identity'><span className='queue-list__icon' aria-hidden='true'>▤</span><span><strong>{item.target_record_id}</strong><small>{item.assignee_id ?? 'Sin asignar'} · {item.review_set ?? 'corpus'}{item.requires_second_review ? ' · doble validación' : ''}</small></span></div>
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
  </div>
}
