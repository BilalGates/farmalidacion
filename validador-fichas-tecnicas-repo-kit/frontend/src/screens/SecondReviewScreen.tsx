import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Archive, Check, Clock } from 'lucide-react'

import {
  ApiError,
  fetchBlindField,
  fetchSecondReviews,
  mutateSecondReview,
} from '../api/client'
import type { BlindField, Reviewer, SecondReviewItem } from '../api/types'
import { ASSIGNABLE_STATES, VALIDATION_STATE_LABELS } from '../domain/vocabulary'
import { PageHeader } from '../components/PageHeader'
import { EmptyState } from '../components/AsyncState'
import { useCapability } from '../auth/SessionContext'

/**
 * Segunda validación ciega y conciliación (DEV-607/608).
 *
 * Esta pantalla **no** oculta la primera decisión: no la recibe. El endpoint
 * ciego del backend no la consulta, así que aquí no hay nada que esconder.
 * La diferencia importa: una pantalla que ocultase un dato que la API sí
 * entrega dejaría la primera lectura a un `curl` de distancia.
 *
 * El estado de una asignación cambia el trabajo que ofrece:
 *
 * - `pendiente` / `en_revision`: emitir la propia lectura, a ciegas;
 * - `desacuerdo`: conciliar, ahora sí viendo ambas lecturas;
 * - `acuerdo` / `conciliado`: nada que hacer, sólo constancia.
 */

const OPEN_STATES = ['pendiente', 'en_revision']

export interface SecondReviewCounts { open: number; conflicts: number; closed: number }

export function SecondReviewScreen({ reviewer, embedded = false, onCounts }: {
  reviewer: Reviewer | null
  /** Dentro de la página de Revisión: bloque con título propio y cerradas plegadas. */
  embedded?: boolean
  onCounts?: (counts: SecondReviewCounts) => void
}) {
  const canReview = useCapability('review.write')
  const canReconcile = useCapability('review.reconcile')
  const [items, setItems] = useState<SecondReviewItem[]>([])
  const [active, setActive] = useState<BlindField | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [state, setState] = useState('')
  const [finalValue, setFinalValue] = useState('')
  const [comment, setComment] = useState('')
  const editorHeading = useRef<HTMLHeadingElement>(null)
  const pageHeading = useRef<HTMLHeadingElement>(null)
  const originButton = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (active !== null) editorHeading.current?.focus()
  }, [active])

  function closeEditor() {
    setActive(null)
    window.requestAnimationFrame(() => {
      if (originButton.current?.isConnected) originButton.current.focus()
      else pageHeading.current?.focus()
    })
  }

  const load = useCallback(() => {
    if (reviewer === null) return
    fetchSecondReviews(reviewer.identifier)
      .then((result) => {
        setItems(result)
        setError(null)
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : 'Error inesperado.'),
      )
  }, [reviewer])

  useEffect(load, [load])

  function openBlind(item: SecondReviewItem, origin: HTMLButtonElement) {
    if (reviewer === null) return
    originButton.current = origin
    setError(null)
    setNotice(null)
    setState('')
    setFinalValue('')
    setComment('')
    fetchBlindField(item.id, reviewer.identifier)
      .then(setActive)
      .catch((cause: unknown) => {
        setActive(null)
        setError(cause instanceof ApiError ? cause.message : 'Error inesperado.')
      })
  }

  async function submit(operation: 'claim' | 'decisions' | 'reconcile') {
    if (reviewer === null || active === null || (operation === 'reconcile' ? !canReconcile : !canReview)) return
    setBusy(true)
    setError(null)
    try {
      await mutateSecondReview(active.assignment_id, operation, {
        reviewer_id: reviewer.identifier,
        expected_version: active.version,
        state: state || 'confirmado',
        final_value: finalValue === '' ? null : finalValue,
        comment: comment === '' ? null : comment,
      })
      setNotice(
        operation === 'reconcile' ? 'Discrepancia conciliada.' : 'Lectura registrada.',
      )
      setActive(null)
      load()
      window.requestAnimationFrame(() => pageHeading.current?.focus())
    } catch (cause: unknown) {
      // El mensaje del backend explica qué barrera se ha aplicado.
      setError(cause instanceof ApiError ? cause.message : 'Error inesperado.')
    } finally {
      setBusy(false)
    }
  }

  const open = items.filter((item) => OPEN_STATES.includes(item.state))
  const conflicts = items.filter((item) => item.state === 'desacuerdo')
  const closed = items.filter((item) => ['acuerdo', 'conciliado'].includes(item.state))
  useEffect(() => { onCounts?.({ open: open.length, conflicts: conflicts.length, closed: closed.length }) }, [open.length, conflicts.length, closed.length, onCounts])

  const blockHead = <header className='work-block__head'><h2 id='work-block-second'>Segunda lectura</h2><p>Emite una segunda lectura sin ver la primera. Las discrepancias requieren conciliación explícita antes de exportar.</p></header>
  const Panel = embedded ? 'h3' : 'h2'

  if (reviewer === null && embedded) {
    return <section className='screen work-block' id='segunda-lectura' aria-labelledby='work-block-second'>
      {blockHead}
      <p className='work-block__note'>Identifícate en <a href='#/revisores'>Equipo y preferencias</a> para hacer segundas lecturas: cada una exige saber quién la firma.</p>
    </section>
  }

  // Sin nada que mostrar y con la API negándose (p. ej. segunda revisión
  // desactivada), el bloque se queda en una línea en vez de tres paneles vacíos.
  if (embedded && error && items.length === 0 && active === null) {
    return <section className='screen work-block' id='segunda-lectura' aria-labelledby='work-block-second'>
      {blockHead}
      <p className='work-block__note' role='status'>{error}</p>
    </section>
  }

  if (reviewer === null) {
    return (
      <div className='screen'>
        <PageHeader eyebrow='Segunda validación' title='Validaciones' />
        <EmptyState
          title='Identifícate para hacer segundas lecturas'
          detail='Una segunda lectura exige saber quién la firma.'
          action={<a className='button button--primary' href='#/revisores'>Ir a Equipo y preferencias</a>}
        />
      </div>
    )
  }

  const Root = embedded ? 'section' : 'div'
  const closedList = closed.length === 0 ? (
    <div className='empty-state empty-state--compact'><span className='empty-state__icon' aria-hidden='true'><Archive size={16} /></span><p>Todavía no hay segundas lecturas cerradas.</p></div>
  ) : (
    <ul className='conflicts'>
      {closed.map((item) => (
        <li key={item.id}>
          <span className='conflicts__field'>{item.target_record_id}<small>{item.field_name}</small></span>
          <span className='badge badge--confirmado'>{item.state}</span>
        </li>
      ))}
    </ul>
  )

  return (
    <Root className={embedded ? 'screen work-block' : 'screen'} id={embedded ? 'segunda-lectura' : undefined} aria-labelledby={embedded ? 'work-block-second' : undefined}>
      {embedded ? blockHead : <PageHeader eyebrow='Segunda validación' title='Validaciones' description='Emite una segunda lectura sin ver la primera. Las discrepancias requieren conciliación explícita antes de exportar.' />}
      <h2 className='visually-hidden' ref={pageHeading} tabIndex={-1}>Lista de validaciones</h2>

      {notice && (
        <p className='alert alert--ok' role='status'>
          {notice}
        </p>
      )}
      {error && (
        <p className='alert alert--error' role='alert'>
          {error}
        </p>
      )}

      {!embedded && <div className='validation-overview' aria-label='Resumen de validaciones'>
        <div><span className='validation-overview__icon' aria-hidden='true'><Clock size={16} /></span><strong>{open.length}</strong><small>Pendientes</small></div>
        <div><span className='validation-overview__icon validation-overview__icon--danger' aria-hidden='true'><AlertTriangle size={16} /></span><strong>{conflicts.length}</strong><small>Discrepancias</small></div>
        <div><span className='validation-overview__icon validation-overview__icon--success' aria-hidden='true'><Check size={16} /></span><strong>{closed.length}</strong><small>Cerradas</small></div>
      </div>}

      <div className='validation-grid'>
      <section className='panel validation-panel'>
        <Panel>Pendientes de segunda lectura ({open.length})</Panel>
        {open.length === 0 ? (
          <div className='empty-state empty-state--compact'><span className='empty-state__icon' aria-hidden='true'><Clock size={16} /></span><p>No hay campos esperando una segunda lectura tuya.</p></div>
        ) : (
          <ul className='conflicts'>
            {open.map((item) => (
              <li key={item.id}>
                <span className='conflicts__field'>{item.target_record_id}<small>{item.field_name}</small></span>
                <span className='badge badge--pendiente'>{item.state}</span>
                <button
                  type='button'
                  className='button button--ghost'
                  onClick={(event) => openBlind(item, event.currentTarget)}
                >
                  Revisar a ciegas
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {active !== null && (
        <section className='panel validation-editor'>
          <h2 ref={editorHeading} tabIndex={-1}>Lectura ciega · {active.field_name}</h2>
          <p className='note'>{active.instruction}</p>
          <dl className='pairs'>
            <div>
              <dt>Valor de origen</dt>
              <dd className='cell--mono'>{active.literal_value ?? '—'}</dd>
            </div>
            <div>
              <dt>Tipo observado</dt>
              <dd>{active.observed_type}</dd>
            </div>
          </dl>

          <div className='review__grid'>
            <label className='field'>
              <span className='field__label'>Tu decisión</span>
              <select
                aria-label='Decisión de segunda lectura'
                value={state}
                onChange={(event) => setState(event.target.value)}
              >
                <option value=''>Elige una decisión…</option>
                {ASSIGNABLE_STATES.map((item) => (
                  <option key={item} value={item}>
                    {VALIDATION_STATE_LABELS[item]}
                  </option>
                ))}
              </select>
            </label>
            <label className='field'>
              <span className='field__label'>Valor final</span>
              <input
                type='text'
                aria-label='Valor final de segunda lectura'
                value={finalValue}
                onChange={(event) => setFinalValue(event.target.value)}
              />
            </label>
            <label className='field field--wide'>
              <span className='field__label'>Comentario</span>
              <input
                type='text'
                aria-label='Comentario de segunda lectura'
                value={comment}
                onChange={(event) => setComment(event.target.value)}
              />
            </label>
          </div>

          <div className='review__actions'>
            <button
              type='button'
              className='button button--primary'
              disabled={!canReview || busy || state === ''}
              onClick={() => void submit('decisions')}
            >
              {busy ? 'Registrando…' : 'Registrar lectura'}
            </button>
            <button
              type='button'
              className='button button--ghost'
              disabled={busy}
              onClick={closeEditor}
            >
              Cancelar
            </button>
          </div>
        </section>
      )}

      <section className='panel validation-panel'>
        <Panel>Discrepancias por conciliar ({conflicts.length})</Panel>
        {conflicts.length === 0 ? (
          <div className='empty-state empty-state--compact'><span className='empty-state__icon' aria-hidden='true'><Check size={16} /></span><p>No hay discrepancias abiertas.</p></div>
        ) : (
          <ul className='conflicts'>
            {conflicts.map((item) => (
              <li key={item.id}>
                <span className='conflicts__field'>{item.target_record_id}<small>{item.field_name}</small></span>
                <span className='badge badge--requiere_revision'>Desacuerdo</span>
                <button
                  type='button'
                  className='button button--ghost'
                  onClick={(event) => openBlind(item, event.currentTarget)}
                >
                  Abrir
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className='note'>
          Conciliar exige justificación y no sobrescribe ninguna de las dos lecturas:
          ambas se conservan en el historial del campo.
        </p>
      </section>

      {embedded ? (
        <details className='panel validation-panel work-block__closed'>
          <summary>Cerradas ({closed.length})</summary>
          {closedList}
        </details>
      ) : (
        <section className='panel validation-panel'>
          <h2>Cerradas ({closed.length})</h2>
          {closedList}
        </section>
      )}
      </div>
    </Root>
  )
}
