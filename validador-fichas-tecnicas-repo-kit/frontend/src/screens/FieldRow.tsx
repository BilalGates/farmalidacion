import { useState } from 'react'

import type { FieldValue, Reviewer, ValidationState } from '../api/types'
import { ValidationBadge } from '../components/StateBadge'
import {
  ASSIGNABLE_STATES,
  VALIDATION_STATE_LABELS,
  conflictLabel,
  sourceLabel,
} from '../domain/vocabulary'

/**
 * Un campo con sus fuentes, su estado y su acción de revisión.
 *
 * Regla que este componente no puede romper: no se preselecciona ningún valor
 * para el revisor. El desplegable de estado arranca vacío y el valor final se
 * escribe, aunque exista un valor de fuente. La política de pre-relleno de la
 * especificación 9 vive en `prefill_policy` en el backend y esta vertical no la
 * consume todavía; hasta entonces, no precargar es el comportamiento seguro.
 */
export function FieldRow({
  value,
  reviewer,
  saving,
  onSave,
}: {
  value: FieldValue
  reviewer: Reviewer | null
  saving: boolean
  onSave: (state: ValidationState, finalValue: string | null, comment: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [state, setState] = useState<ValidationState | ''>('')
  const [finalValue, setFinalValue] = useState('')
  const [comment, setComment] = useState('')

  const needsValue = state === 'confirmado' || state === 'corregido'
  const canSubmit = state !== '' && reviewer !== null && !saving

  return (
    <div className={`field-row${value.has_conflict ? ' field-row--conflict' : ''}`}>
      <div className='field-row__main'>
        <div className='field-row__identity'>
          <span className='field-row__name'>{value.field_name}</span>
          <span className='field-row__type'>{value.observed_type}</span>
        </div>
        <div className='field-row__value'>
          {value.literal_value === null ? (
            <span className='muted'>Sin valor en la fuente</span>
          ) : (
            <span className='value'>{value.literal_value}</span>
          )}
        </div>
        <div className='field-row__states'>
          <ValidationBadge state={value.validation_state} />
          {value.has_conflict && (
            <span className='badge badge--requiere_revision'>
              {conflictLabel(value.conflict_status)}
            </span>
          )}
        </div>
        <button
          type='button'
          className='button button--ghost'
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          {open ? 'Cerrar' : 'Revisar'}
        </button>
      </div>

      <ul className='sources'>
        {value.provenance.map((item) => (
          <li key={item.source_fragment_id}>
            <span className='sources__role'>{sourceLabel(item.provenance_role)}</span>
            <span className='sources__locator' title={item.literal_text ?? undefined}>
              {item.locator}
            </span>
          </li>
        ))}
        {value.provenance.length === 0 && (
          <li className='muted'>Sin procedencia declarada.</li>
        )}
      </ul>

      {open && (
        <div className='review'>
          <div className='review__grid'>
            <label className='field'>
              <span className='field__label'>Decisión</span>
              <select
                aria-label='Decisión de revisión'
                value={state}
                onChange={(event) => setState(event.target.value as ValidationState | '')}
              >
                <option value=''>Seleccione una decisión…</option>
                {ASSIGNABLE_STATES.map((item) => (
                  <option key={item} value={item}>
                    {VALIDATION_STATE_LABELS[item]}
                  </option>
                ))}
              </select>
            </label>

            {needsValue && (
              <label className='field'>
                <span className='field__label'>Valor final</span>
                <input
                  type='text'
                  aria-label='Valor final'
                  value={finalValue}
                  placeholder='Escriba el valor que valida'
                  onChange={(event) => setFinalValue(event.target.value)}
                />
              </label>
            )}

            <label className='field field--wide'>
              <span className='field__label'>
                Comentario
                <span className='field__hint'>
                  Obligatorio en «No aplica» y en «No consta» de campo obligatorio.
                </span>
              </span>
              <input
                type='text'
                value={comment}
                onChange={(event) => setComment(event.target.value)}
              />
            </label>
          </div>

          <div className='review__actions'>
            <button
              type='button'
              className='button button--primary'
              disabled={!canSubmit}
              onClick={() =>
                onSave(
                  state as ValidationState,
                  needsValue ? finalValue : null,
                  comment.trim() === '' ? null : comment,
                )
              }
            >
              {saving ? 'Guardando…' : 'Guardar decisión'}
            </button>
            {reviewer === null && (
              <span className='muted'>Seleccione un revisor para poder firmar.</span>
            )}
          </div>
        </div>
      )}

      {value.history.length > 0 && (
        <details className='history'>
          <summary>Historial ({value.history.length})</summary>
          <ol>
            {value.history.map((item) => (
              <li key={item.sequence}>
                <strong>{VALIDATION_STATE_LABELS[item.state]}</strong>
                {item.final_value !== null && <> · {item.final_value}</>} ·{' '}
                {item.reviewer_id} (firma {item.reviewer_assurance}) ·{' '}
                {new Date(item.decided_at).toLocaleString('es-ES')}
                {item.comment && <> · {item.comment}</>}
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  )
}
