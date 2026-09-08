import { useEffect, useRef, useState } from 'react'


import type { FieldValue, Reviewer, ValidationState } from '../api/types'
import { ValidationBadge } from '../components/StateBadge'
import { clearDraft, isEmptyDraft, readDraft, saveDraft } from '../domain/drafts'
import { isTypingTarget, resolveShortcut } from '../domain/shortcuts'
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
 * escribe, aunque exista un valor de fuente.
 *
 * La política de pre-relleno la decide `prefill_policy` en el backend
 * (especificación 9, DEV-512) y aquí se obedece, no se reinterpreta. Bajo la
 * política conservadora vigente ningún campo llega con `proposed_value`, así
 * que precargarlo es imposible por construcción y no por disciplina de quien
 * escriba esta pantalla. El aviso que acompaña al campo se muestra literal.
 */
export function FieldRow({
  value,
  recordId,
  reviewer,
  saving,
  saveError,
  onSave,
}: {
  value: FieldValue
  recordId: string
  reviewer: Reviewer | null
  saving: boolean
  saveError: boolean
  onSave: (state: ValidationState, finalValue: string | null, comment: string | null) => void
}) {
  // El borrador se recupera al montar: recargar a mitad de una edición no
  // puede hacer que el revisor repita lo que ya había escrito.
  const restored = useRef(readDraft(recordId, value.id)).current
  const [open, setOpen] = useState(restored !== null)
  const [state, setState] = useState<ValidationState | ''>(
    (restored?.state ?? '') as ValidationState | '',
  )
  const [finalValue, setFinalValue] = useState(
    restored?.finalValue ?? value.proposed_value ?? '',
  )
  const [comment, setComment] = useState(restored?.comment ?? '')
  const [recovered, setRecovered] = useState(restored !== null)

  const draft = { state, finalValue, comment }
  const dirty = !isEmptyDraft(draft)

  // Autoguardado local del borrador. No se envía nada al backend: una decisión
  // clínica se firma cuando el revisor la guarda, no cuando deja de teclear.
  useEffect(() => {
    saveDraft(recordId, value.id, draft)
    // `draft` se recrea en cada render; sus campos son las dependencias reales.
  }, [recordId, value.id, state, finalValue, comment])

  const needsValue = state === 'confirmado' || state === 'corregido'
  const needsComment = state === 'no_aplica'
  const missingValue = needsValue && finalValue.trim() === ''
  const missingComment = needsComment && comment.trim() === ''
  const canSubmit =
    state !== '' && reviewer !== null && !saving && !missingValue && !missingComment

  const historyLength = value.history.length
  const previousHistory = useRef(historyLength)
  useEffect(() => {
    if (historyLength > previousHistory.current) {
      // La decisión está firmada en el backend: el borrador ya no protege nada.
      clearDraft(recordId, value.id)
      setState('')
      setFinalValue('')
      setComment('')
      setRecovered(false)
      setOpen(false)
    }
    previousHistory.current = historyLength
  }, [historyLength, recordId, value.id])

  /**
   * Atiende los atajos que dependen del estado del formulario del campo.
   *
   * `guardar` no fuerza nada: si la decisión todavía no es admisible, el atajo
   * no puede saltarse la misma comprobación que bloquea el botón. Un atajo que
   * guardase una decisión incompleta firmaría por el revisor.
   */
  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const action = resolveShortcut(event, isTypingTarget(event.target))
    if (action === 'editar') {
      event.preventDefault()
      setOpen((current) => !current)
      return
    }
    if (action === 'cancelar' && open) {
      event.preventDefault()
      setOpen(false)
      return
    }
    if (action === 'guardar' && open && canSubmit) {
      event.preventDefault()
      onSave(
        state as ValidationState,
        needsValue ? finalValue : null,
        comment.trim() === '' ? null : comment,
      )
    }
  }

  return (
    <div
      className={`field-row${value.has_conflict ? ' field-row--conflict' : ''}`}
      onKeyDown={handleKeyDown}
    >
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
            <span className='sources__locator'>{item.locator}</span>
            <span className='sources__version'>Versión {item.document_version_id}</span>
            {item.literal_text && (
              <blockquote className='sources__evidence'>{item.literal_text}</blockquote>
            )}
          </li>
        ))}
        {value.provenance.length === 0 && (
          <li className='muted'>Sin procedencia declarada.</li>
        )}
      </ul>

      {open && (
        <div className='review'>
          {value.prefill_warning !== null && (
            <p className='field__warning' role='note'>
              {value.prefill_warning}
            </p>
          )}
          {recovered && (
            <p className='alert alert--info' role='status'>
              Se ha recuperado lo que había escrito sin guardar. Revíselo antes de firmar.
            </p>
          )}
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
                aria-label='Comentario de revisión'
                value={comment}
                onChange={(event) => setComment(event.target.value)}
              />
            </label>
          </div>

          <div className='review__actions'>
            <p className='review__status' role='status'>
              {saving
                ? 'Guardando…'
                : saveError
                  ? 'No se ha guardado.'
                  : dirty
                    ? 'Cambios sin guardar.'
                    : 'Sin cambios pendientes.'}
            </p>
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
            {missingValue && (
              <span className='field-error'>Escriba el valor final antes de guardar.</span>
            )}
            {missingComment && (
              <span className='field-error'>«No aplica» exige un comentario.</span>
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
