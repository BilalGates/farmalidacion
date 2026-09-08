import { useCallback, useEffect, useState } from 'react'

import {
  ApiError,
  fetchBlindField,
  fetchSecondReviews,
  mutateSecondReview,
} from '../api/client'
import type { BlindField, Reviewer, SecondReviewItem } from '../api/types'
import { ASSIGNABLE_STATES, VALIDATION_STATE_LABELS } from '../domain/vocabulary'

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

export function SecondReviewScreen({ reviewer }: { reviewer: Reviewer | null }) {
  const [items, setItems] = useState<SecondReviewItem[]>([])
  const [active, setActive] = useState<BlindField | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [state, setState] = useState('')
  const [finalValue, setFinalValue] = useState('')
  const [comment, setComment] = useState('')

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

  function openBlind(item: SecondReviewItem) {
    if (reviewer === null) return
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
    if (reviewer === null || active === null) return
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
    } catch (cause: unknown) {
      // El mensaje del backend explica qué barrera se ha aplicado.
      setError(cause instanceof ApiError ? cause.message : 'Error inesperado.')
    } finally {
      setBusy(false)
    }
  }

  if (reviewer === null) {
    return (
      <div className='screen'>
        <div className='screen__head'>
          <div>
            <p className='eyebrow'>Segunda validación</p>
            <h1>Validaciones</h1>
          </div>
        </div>
        <p className='muted'>
          Seleccione un revisor: una segunda lectura exige saber quién la firma.
        </p>
      </div>
    )
  }

  const open = items.filter((item) => OPEN_STATES.includes(item.state))
  const conflicts = items.filter((item) => item.state === 'desacuerdo')
  const closed = items.filter((item) => ['acuerdo', 'conciliado'].includes(item.state))

  return (
    <div className='screen'>
      <div className='screen__head'>
        <div>
          <p className='eyebrow'>Segunda validación</p>
          <h1>Validaciones</h1>
          <p className='lede'>
            Las lecturas pendientes se emiten sin ver la decisión del primer revisor.
          </p>
        </div>
      </div>

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

      <section className='panel'>
        <h2>Pendientes de segunda lectura ({open.length})</h2>
        {open.length === 0 ? (
          <p className='muted'>No hay campos esperando una segunda lectura suya.</p>
        ) : (
          <ul className='conflicts'>
            {open.map((item) => (
              <li key={item.id}>
                <span className='conflicts__field'>{item.target_record_id}</span>
                <span className='badge badge--pendiente'>{item.state}</span>
                <button
                  type='button'
                  className='button button--ghost'
                  onClick={() => openBlind(item)}
                >
                  Revisar a ciegas
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {active !== null && (
        <section className='panel'>
          <h2>Lectura ciega · {active.field_name}</h2>
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
              <span className='field__label'>Su decisión</span>
              <select
                aria-label='Decisión de segunda lectura'
                value={state}
                onChange={(event) => setState(event.target.value)}
              >
                <option value=''>Seleccione una decisión…</option>
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
              disabled={busy || state === ''}
              onClick={() => void submit('decisions')}
            >
              {busy ? 'Registrando…' : 'Registrar lectura'}
            </button>
            <button
              type='button'
              className='button button--ghost'
              disabled={busy}
              onClick={() => setActive(null)}
            >
              Cancelar
            </button>
          </div>
        </section>
      )}

      <section className='panel'>
        <h2>Discrepancias por conciliar ({conflicts.length})</h2>
        {conflicts.length === 0 ? (
          <p className='muted'>No hay discrepancias abiertas.</p>
        ) : (
          <ul className='conflicts'>
            {conflicts.map((item) => (
              <li key={item.id}>
                <span className='conflicts__field'>{item.target_record_id}</span>
                <span className='badge badge--requiere_revision'>Desacuerdo</span>
                <button
                  type='button'
                  className='button button--ghost'
                  onClick={() => openBlind(item)}
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

      <section className='panel'>
        <h2>Cerradas ({closed.length})</h2>
        {closed.length === 0 ? (
          <p className='muted'>Todavía no hay segundas lecturas cerradas.</p>
        ) : (
          <ul className='conflicts'>
            {closed.map((item) => (
              <li key={item.id}>
                <span className='conflicts__field'>{item.target_record_id}</span>
                <span className='badge badge--confirmado'>{item.state}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
