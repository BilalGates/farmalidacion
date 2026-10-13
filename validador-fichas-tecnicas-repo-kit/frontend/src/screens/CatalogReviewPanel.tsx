import { useEffect, useState } from 'react'
import { assignQueue, enqueueRecord, fetchQueue, transitionQueue } from '../api/client'
import type { QueueItem } from '../api/client'
import type { Reviewer } from '../api/types'

const LABELS: Record<string, string> = {
  pendiente: 'Pendiente', asignado: 'Asignado', en_revision: 'En revisión',
  completado: 'Completado', requiere_segunda_revision: 'Segunda revisión', bloqueado: 'Bloqueado',
}

export function CatalogReviewPanel({ recordId, reviewer }: { recordId: string | null; reviewer: Reviewer | null }) {
  const [item, setItem] = useState<QueueItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [second, setSecond] = useState(false)

  useEffect(() => {
    if (!recordId) { setLoading(false); return }
    let active = true
    fetchQueue().then((items) => { if (active) { setItem(items.find((entry) => entry.target_record_id === recordId) ?? null); setError('') } })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : 'No se pudo consultar la revisión.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [recordId])

  async function act(operation: () => Promise<QueueItem>) {
    setBusy(true)
    setError('')
    try { setItem(await operation()) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo actualizar la revisión.') }
    finally { setBusy(false) }
  }

  return <section className='panel catalog-review-panel' aria-labelledby='catalog-review-title'>
    <div className='panel__head'><div><p className='eyebrow'>Trabajo del equipo</p><h2 id='catalog-review-title'>Revisión</h2></div></div>
    {!recordId ? <p className='muted'>Esta identidad no tiene un registro importado asociado para revisar.</p> : <>
      {loading ? <p role='status'>Cargando estado de revisión…</p> : <p>Estado: <strong>{item ? LABELS[item.state] ?? item.state : 'Sin asignar'}</strong>{item?.assignee_id ? ` · Responsable: ${item.assignee_id}` : ''}{item?.requires_second_review ? ' · Doble validación' : ''}</p>}
      {error && <p className='alert alert--error' role='alert'>{error}</p>}
      {!item && !loading && <div className='catalog-actions'>
        <label className='queue-check'><input type='checkbox' checked={second} onChange={(event) => setSecond(event.target.checked)} /> Solicitar doble validación</label>
        <button type='button' className='button button--primary' disabled={busy} onClick={() => void act(() => enqueueRecord(recordId, 'corpus', second))}>Añadir a revisión</button>
      </div>}
      {item && !loading && <div className='catalog-actions'>
        {reviewer && !['completado', 'bloqueado'].includes(item.state) && item.assignee_id !== reviewer.identifier && <button type='button' className='button' disabled={busy} onClick={() => void act(() => assignQueue(recordId, reviewer.identifier))}>Asignarme</button>}
        {reviewer && item.assignee_id === reviewer.identifier && item.state === 'asignado' && <button type='button' className='button button--primary' disabled={busy} onClick={() => void act(() => transitionQueue(item, reviewer.identifier, 'en_revision'))}>Iniciar revisión</button>}
        {reviewer && item.assignee_id === reviewer.identifier && ['asignado', 'en_revision'].includes(item.state) && <button type='button' className='button' disabled={busy} onClick={() => void act(() => transitionQueue(item, reviewer.identifier, 'pendiente'))}>Devolver a pendientes</button>}
      </div>}
      {!reviewer && item && <p className='muted'>Seleccione un revisor para asignar o iniciar la revisión.</p>}
    </>}
  </section>
}
