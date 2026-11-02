import { useState } from 'react'

import { decideMaintenanceAction, sendActionsToReview } from '../api/client'
import type {
  MaintenanceAction,
  MaintenanceActionKind,
  MaintenanceActionPage,
} from '../api/client'
import type { Reviewer } from '../api/types'
import { useCapability } from '../auth/SessionContext'
import { formatDateTime, orDash } from '../domain/format'

export const KIND_ORDER: readonly MaintenanceActionKind[] = [
  'proponer_activo_n', 'revisar_estado', 'revisar_comercializacion', 'revisar_archivo', 'proponer_alta',
]

export const KIND_LABELS: Record<MaintenanceActionKind, string> = {
  proponer_activo_n: 'Desactivar en el maestro (ACTIVO=N)',
  revisar_estado: 'Revisar estado en CIMA',
  revisar_comercializacion: 'Revisar comercialización en CIMA',
  revisar_archivo: 'Revisar si se archiva',
  proponer_alta: 'Proponer alta',
}

const ACCEPT_LABELS: Record<MaintenanceActionKind, string> = {
  proponer_activo_n: 'Aceptar ACTIVO = N',
  revisar_estado: 'Marcar revisada',
  revisar_comercializacion: 'Marcar revisada',
  revisar_archivo: 'Archivar',
  proponer_alta: 'Crear borrador',
}

const STATE_LABELS: Record<string, string> = {
  pendiente: 'Pendiente', aceptada: 'Aceptada', descartada: 'Descartada',
  enviada_revision: 'Enviada a Revisión',
}

function noticeDate(epoch: number): string {
  return formatDateTime(new Date(epoch).toISOString())
}

function MasterAndCima({ action }: { action: MaintenanceAction }) {
  if (action.diagnostic_code === 'cima_no_disponible') {
    return <p className='action-row__pending'>Pendiente de consultar CIMA. No se puede decidir hasta que CIMA responda.</p>
  }
  const masterLabel = action.kind === 'revisar_archivo'
    ? 'Estado en el catálogo'
    : action.master_field_name ? `Maestro · ${action.master_field_name}` : 'Maestro'
  return (
    <dl className='action-row__values'>
      <div><dt>{masterLabel}</dt><dd><code>{orDash(action.master_value_literal)}</code></dd></div>
      <div>
        <dt>Valor en CIMA a fecha {action.cima_fetched_at ? formatDateTime(action.cima_fetched_at) : 'desconocida'}</dt>
        <dd>
          <code>{orDash(action.cima_value_literal)}</code>
          {action.cima_source_url && <> <a href={action.cima_source_url} target='_blank' rel='noreferrer'>Ver procedencia</a></>}
        </dd>
      </div>
      <div>
        <dt>Valor propuesto</dt>
        <dd>
          {action.proposed_value !== null
            ? <><code>{action.master_field_name} = {action.proposed_value}</code> <small>Regla {action.rule_id}</small></>
            : 'Sin valor propuesto: no hay correspondencia aceptada'}
        </dd>
      </div>
    </dl>
  )
}

function AltaTable({ action }: { action: MaintenanceAction }) {
  const columns = action.proposal?.columns ?? []
  if (columns.length === 0) {
    return <p className='action-row__pending'>No hay cabecera del maestro importada: no se puede preparar el alta.</p>
  }
  return (
    <div className='table-wrap' role='region' aria-label={`Estructura del alta ${action.national_code ?? ''}`} tabIndex={0}>
      <table className='table'>
        <thead><tr>{columns.map(column => <th key={column.column} scope='col'>{column.name}</th>)}</tr></thead>
        <tbody><tr>{columns.map(column => (
          <td key={column.column}>
            {column.value !== null
              ? <span title={column.provenance?.pointer}>{column.value}</span>
              : <span className='action-row__empty'>sin fuente</span>}
            {column.diagnostic === 'excede_longitud' && <small> · supera la longitud declarada</small>}
          </td>
        ))}</tr></tbody>
      </table>
    </div>
  )
}

export function ActionRow({ action, reviewer, selected, onSelect, onChanged }: {
  readonly action: MaintenanceAction
  readonly reviewer: Reviewer | null
  readonly selected?: boolean
  readonly onSelect?: (selected: boolean) => void
  readonly onChanged: () => void
}) {
  const canDecide = useCapability('review.write') && reviewer !== null
  const [asking, setAsking] = useState<'aceptada' | 'descartada' | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const unavailable = action.diagnostic_code === 'cima_no_disponible'
  const name = action.identity_name ?? (action.national_code ? `CN ${action.national_code}` : `Registro ${action.nregistro}`)
  const needsReason = (decision: 'aceptada' | 'descartada') =>
    decision === 'descartada' || (decision === 'aceptada' && action.kind === 'revisar_archivo')

  async function submit(decision: 'aceptada' | 'descartada', text: string) {
    if (!reviewer) return
    setBusy(true)
    setError('')
    try {
      await decideMaintenanceAction(action.id, {
        actor_id: reviewer.identifier, decision, reason: text.trim(), expected_sequence: action.sequence,
      })
      setAsking(null)
      setReason('')
      onChanged()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo registrar la decisión.')
    } finally { setBusy(false) }
  }

  function choose(decision: 'aceptada' | 'descartada') {
    if (needsReason(decision)) { setAsking(decision); return }
    void submit(decision, '')
  }

  return (
    <li className='action-row' aria-label={`Novedad de ${name}`}>
      <div className='action-row__head'>
        {onSelect && <input type='checkbox' aria-label={`Seleccionar ${name}`} checked={selected === true}
          onChange={event => onSelect(event.target.checked)} />}
        <div>
          <strong>
            {action.identity_id
              ? <a href={`#/catalogo/${encodeURIComponent(action.identity_id)}`}>{name}</a>
              : name}
          </strong>
          <small> · CN {orDash(action.national_code)} · registro {action.nregistro} · aviso del {noticeDate(action.event_occurred_at_epoch)}</small>
        </div>
        <span className={`badge badge--${action.state}`}>{STATE_LABELS[action.state] ?? action.state}</span>
      </div>
      {action.kind === 'proponer_alta' ? <AltaTable action={action} /> : <MasterAndCima action={action} />}
      {action.kind === 'proponer_activo_n' && action.master_value_literal === 'N' && action.state === 'pendiente' && (
        <p className='action-row__pending'>El maestro ya dice ACTIVO = N: aceptar solo registra tu decisión, no hay nada que escribir.</p>
      )}
      {action.last_decision?.reason && <p className='action-row__reason'>Última decisión: {action.last_decision.reason}</p>}
      {action.state === 'pendiente' && !unavailable && (
        <div className='action-row__actions'>
          <button type='button' className='button button--primary' disabled={!canDecide || busy}
            onClick={() => choose('aceptada')}>{ACCEPT_LABELS[action.kind]}</button>
          <button type='button' className='button' disabled={!canDecide || busy}
            onClick={() => choose('descartada')}>Descartar</button>
          {!canDecide && <small>Identifícate con permiso de revisión para decidir.</small>}
        </div>
      )}
      {asking && (
        <form className='action-row__reason-form' onSubmit={event => { event.preventDefault(); void submit(asking, reason) }}>
          <label className='field'>
            <span className='field__label'>Justificación</span>
            <textarea rows={2} value={reason} onChange={event => setReason(event.target.value)}
              placeholder={asking === 'descartada' ? 'Por qué descartas esta novedad' : 'Por qué lo archivas'} />
          </label>
          <button type='submit' className='button button--primary' disabled={busy || !reason.trim()}>Confirmar</button>
          <button type='button' className='button button--ghost' onClick={() => setAsking(null)}>Cancelar</button>
        </form>
      )}
      {error && <p className='alert alert--error' role='alert'>{error}</p>}
    </li>
  )
}

export function ActionGroups({ page, reviewer, onChanged }: {
  readonly page: MaintenanceActionPage
  readonly reviewer: Reviewer | null
  readonly onChanged: () => void
}) {
  const canSend = useCapability('review.write') && reviewer !== null
  const [selection, setSelection] = useState<ReadonlySet<string>>(new Set())
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const items = (page.items ?? []).filter(item => KIND_ORDER.includes(item.kind))
  const counts = page.counts ?? {}

  function toggle(ids: readonly string[], selected: boolean) {
    setSelection(current => {
      const next = new Set(current)
      ids.forEach(id => selected ? next.add(id) : next.delete(id))
      return next
    })
  }

  async function send(ids: readonly string[]) {
    if (!reviewer) return
    setError('')
    setMessage('')
    try {
      const result = await sendActionsToReview(reviewer.identifier, [...ids])
      setMessage(
        `${result.enqueued.length} registros encolados, ${result.already_queued.length} ya estaban en la cola`
        + (result.rejected.length ? ` y ${result.rejected.length} acciones rechazadas.` : '.'),
      )
      toggle(ids, false)
      onChanged()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo enviar a Revisión.')
    }
  }

  return (
    <div className='action-groups'>
      {message && <p className='alert alert--ok' role='status'>{message}</p>}
      {error && <p className='alert alert--error' role='alert'>{error}</p>}
      {KIND_ORDER.map(kind => {
        const rows = items.filter(item => item.kind === kind)
        if (rows.length === 0) return null
        const selectable = rows.filter(row => row.target_record_id && row.diagnostic_code !== 'cima_no_disponible')
        const chosen = selectable.filter(row => selection.has(row.id)).map(row => row.id)
        return (
          <details key={kind} className='action-group panel' open>
            <summary><h3>{KIND_LABELS[kind]}</h3><span className='action-group__count'>{counts[kind] ?? rows.length}</span></summary>
            {selectable.length > 0 && (
              <div className='action-group__bar'>
                <label><input type='checkbox' aria-label={`Seleccionar todas: ${KIND_LABELS[kind]}`}
                  checked={chosen.length === selectable.length}
                  onChange={event => toggle(selectable.map(row => row.id), event.target.checked)} /> Seleccionar todas</label>
                <button type='button' className='button' disabled={!canSend || chosen.length === 0}
                  onClick={() => void send(chosen)}>Enviar a Revisión ({chosen.length})</button>
              </div>
            )}
            <ul className='action-list'>
              {rows.map(row => (
                <ActionRow key={row.id} action={row} reviewer={reviewer} onChanged={onChanged}
                  selected={selection.has(row.id)}
                  onSelect={row.target_record_id && row.diagnostic_code !== 'cima_no_disponible'
                    ? selected => toggle([row.id], selected) : undefined} />
              ))}
            </ul>
          </details>
        )
      })}
    </div>
  )
}

/** Bloque del expediente: solo existe si hay novedades sin atender. */
export function IdentityActions({ actions, reviewer, onChanged }: {
  readonly actions: readonly MaintenanceAction[]
  readonly reviewer: Reviewer | null
  readonly onChanged: () => void
}) {
  if (actions.length === 0) return null
  return (
    <section className='panel identity-actions' aria-label='Novedades CIMA sin atender'>
      <div className='panel__head'>
        <div><p className='eyebrow'>Mantenimiento continuo</p><h2>Novedades CIMA sin atender</h2></div>
        <span className='action-group__count'>{actions.length}</span>
      </div>
      <ul className='action-list'>
        {actions.map(action => (
          <ActionRow key={action.id} action={action} reviewer={reviewer} onChanged={onChanged} />
        ))}
      </ul>
    </section>
  )
}
