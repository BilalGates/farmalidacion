import { useEffect, useState } from 'react'
import { ApiError, assignQueue, enqueueRecord, fetchQueue, transitionQueue } from '../api/client'
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
  const [filter, setFilter] = useState('')

  async function reload() {
    setLoading(true)
    try { setItems(await fetchQueue()); setError('') }
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
  }, [])

  async function act(operation: () => Promise<unknown>) {
    setBusy(true)
    setError('')
    try { await operation(); await reload() }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'No se pudo completar la operación.') }
    finally { setBusy(false) }
  }

  return <div className='screen'>
    <h1>Cola de revisión</h1>
    <p>Asigne registros para organizar el trabajo del equipo.</p>
    {error && <p role='alert' className='alert alert--error'>{error} Recargue para consultar el estado actual.</p>}
    <section className='panel'>
      <form onSubmit={(event) => {
        event.preventDefault()
        void act(async () => { await enqueueRecord(recordId.trim()); setRecordId('') })
      }}>
        <label className='field'>Identificador del registro
          <input value={recordId} onChange={(event) => setRecordId(event.target.value)} required />
        </label>
        <button className='button' disabled={busy || !recordId.trim()}>Añadir a la cola</button>
      </form>
      <label className='field'>Estado
        <select value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value=''>Todos</option>
          {Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <button className='button' disabled={busy || loading} onClick={() => void reload()}>Recargar</button>
      {loading && <p role='status'>Cargando cola…</p>}
      {!loading && items.length === 0 && <p>No hay registros en la cola.</p>}
      <ul>
        {items.filter((item) => !filter || item.state === filter).map((item) => <li key={item.target_record_id}>
          <p>{item.target_record_id} · {labels[item.state] ?? item.state} · {item.assignee_id ?? 'Sin asignar'}</p>
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
        </li>)}
      </ul>
    </section>
  </div>
}
