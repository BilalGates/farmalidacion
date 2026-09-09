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

  const filters = {
    state: filter,
    entity_type: entityFilter,
    block_type: blockFilter,
    review_set: setFilter,
    requires_second_review: secondFilter === '' ? undefined : secondFilter === 'true',
  }

  async function reload() {
    setLoading(true)
    try { setItems(await fetchQueue(filters)); setSelected([]); setError('') }
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
        <label className='field'><span className='field__label'>Añadir registro</span>
          <span className='input-with-icon'><span aria-hidden='true'>⌕</span><input placeholder='Identificador del registro' aria-label='Identificador del registro' value={recordId} onChange={(event) => setRecordId(event.target.value)} required /></span>
        </label>
        <button className='button button--primary' disabled={busy || !recordId.trim()}>Añadir a la cola</button>
        <label className='field'><span className='field__label'>Conjunto al añadir</span>
          <select value={reviewSet} onChange={(event) => setReviewSet(event.target.value as QueueItem['review_set'])}>
            <option value='corpus'>Corpus</option><option value='oro'>Oro</option><option value='medida'>Medida</option>
          </select>
        </label>
        <label><input type='checkbox' checked={requiresSecondReview} onChange={(event) => setRequiresSecondReview(event.target.checked)} /> Requiere doble validación</label>
      </form>
      <label className='field queue-filter'><span className='field__label'>Filtrar por estado</span>
        <select value={filter} onChange={(event) => setStateFilter(event.target.value)}>
          <option value=''>Todos</option>
          {Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <label className='field'><span className='field__label'>Entidad</span><input value={entityFilter} onChange={(event) => setEntityFilter(event.target.value)} /></label>
      <label className='field'><span className='field__label'>Bloque</span><input value={blockFilter} onChange={(event) => setBlockFilter(event.target.value)} /></label>
      <label className='field'><span className='field__label'>Filtrar por conjunto</span><select value={setFilter} onChange={(event) => setReviewSetFilter(event.target.value)}><option value=''>Todos</option><option value='oro'>Oro</option><option value='medida'>Medida</option><option value='corpus'>Corpus</option></select></label>
      <label className='field'><span className='field__label'>Filtrar doble validación</span><select value={secondFilter} onChange={(event) => setSecondFilter(event.target.value)}><option value=''>Todas</option><option value='true'>Sí</option><option value='false'>No</option></select></label>
      <button className='button' aria-label='Aplicar filtros' disabled={busy || loading} onClick={() => void reload()}>Filtrar</button>
      <button className='button button--icon' aria-label='Actualizar cola' disabled={busy || loading} onClick={() => void reload()}>↻</button>
      </div>
      {selected.length > 0 && <div className='queue-batch'>
        <span>{selected.length} seleccionados</span>
        <button className='button button--primary' disabled={busy || !reviewer} onClick={() => void act(() => assignQueueBatch(items.filter((item) => selected.includes(item.target_record_id)), reviewer!.identifier))}>Asignarme lote</button>
      </div>}
      {loading && <div className='empty-state' role='status'><span className='empty-state__icon'>↻</span><h2>Cargando cola…</h2></div>}
      {!loading && visibleItems.length === 0 && <div className='empty-state'><span className='empty-state__icon' aria-hidden='true'>✓</span><h2>{items.length === 0 ? 'La cola está al día' : 'No hay resultados'}</h2><p>{items.length === 0 ? 'Cuando se añadan registros aparecerán aquí, listos para asignar.' : 'Pruebe con otro filtro de estado.'}</p></div>}
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
