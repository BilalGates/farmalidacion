import { useState } from 'react'

import { ApiError, editBlock } from '../api/client'
import type { BlockOccurrence, BlockOperation, Reviewer } from '../api/types'

/**
 * Edición de las ocurrencias de un bloque repetible (DEV-507).
 *
 * Las reglas no viven aquí: las aplica `block_editing` en el backend y esta
 * pantalla se limita a ofrecer las operaciones y a mostrar literalmente el
 * motivo cuando una se rechaza. Duplicar aquí la comprobación crearía un
 * segundo sitio donde relajarla.
 *
 * Dos decisiones de interfaz que responden a reglas del dominio:
 *
 * - Eliminar y fusionar piden el motivo *antes* de enviarse, porque el backend
 *   los exige y descubrirlo con un 400 haría repetir el trabajo. El motivo se
 *   pide en línea y no en un modal: un modal que se cierre pierde lo escrito.
 * - Marcar «no aplicable» se ofrece junto a eliminar y con el mismo peso
 *   visual. Suele ser la operación correcta sobre una fila importada, y
 *   esconderla empujaría a borrar dato de origen.
 */

/** Operaciones que exigen un motivo declarado por el revisor. */
const NEEDS_COMMENT: readonly BlockOperation[] = [
  'eliminar',
  'fusionar',
  'marcar_no_aplicable',
  'revertir_no_aplicable',
]

interface PendingOperation {
  readonly operation: BlockOperation
  readonly occurrenceId: string
  /** Sólo en fusión: la ocurrencia que se absorbe. */
  readonly sourceId?: string
}

export function BlockEditor({
  recordId,
  blockType,
  occurrences,
  reviewer,
  onChange,
}: {
  recordId: string
  blockType: string
  occurrences: BlockOccurrence[]
  reviewer: Reviewer | null
  onChange: (occurrences: BlockOccurrence[]) => void
}) {
  const [pending, setPending] = useState<PendingOperation | null>(null)
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mergeTarget, setMergeTarget] = useState('')

  const disabled = reviewer === null || busy

  async function run(payload: {
    operation: BlockOperation
    occurrence_id?: string
    ordered_ids?: string[]
    source_id?: string
    target_id?: string
    values?: [string, string | null][]
    comment?: string
  }) {
    if (reviewer === null) return
    setBusy(true)
    setError(null)
    try {
      const result = await editBlock(recordId, blockType, {
        ...payload,
        reviewer_id: reviewer.identifier,
      })
      onChange(result)
      setPending(null)
      setComment('')
      setMergeTarget('')
    } catch (cause: unknown) {
      // El mensaje explica por qué la operación perdería datos: se muestra
      // literal, sin reformularlo.
      setError(cause instanceof ApiError ? cause.message : 'Error inesperado.')
    } finally {
      setBusy(false)
    }
  }

  function ask(operation: BlockOperation, occurrenceId: string, sourceId?: string) {
    setError(null)
    setComment('')
    setMergeTarget('')
    if (!NEEDS_COMMENT.includes(operation)) {
      void run({ operation, occurrence_id: occurrenceId })
      return
    }
    setPending({ operation, occurrenceId, sourceId })
  }

  function confirm() {
    if (pending === null) return
    if (pending.operation === 'fusionar') {
      void run({
        operation: 'fusionar',
        source_id: pending.occurrenceId,
        target_id: mergeTarget,
        comment,
      })
      return
    }
    void run({
      operation: pending.operation,
      occurrence_id: pending.occurrenceId,
      comment,
    })
  }

  function move(occurrenceId: string, direction: -1 | 1) {
    const order = occurrences.map((item) => item.occurrence_id)
    const index = order.indexOf(occurrenceId)
    const next = index + direction
    if (index === -1 || next < 0 || next >= order.length) return
    // Reordenar envía siempre la lista completa: omitir una ocurrencia la
    // eliminaría de hecho, y el backend lo rechaza por ese motivo.
    ;[order[index], order[next]] = [order[next], order[index]]
    void run({ operation: 'reordenar', ordered_ids: order })
  }

  return (
    <div className='block-editor'>
      <div className='block-editor__head'>
        <h3>Ocurrencias de {blockType}</h3>
        <button
          type='button'
          className='button'
          disabled={disabled}
          onClick={() => void run({ operation: 'crear', values: [] })}
        >
          Añadir ocurrencia
        </button>
      </div>

      {reviewer === null && (
        <p className='muted'>Seleccione un revisor para poder editar el bloque.</p>
      )}
      {error && (
        <p className='alert alert--error' role='alert'>
          {error}
        </p>
      )}

      <ul className='block-editor__list'>
        {occurrences.map((occurrence, index) => (
          <li
            key={occurrence.occurrence_id}
            className={occurrence.not_applicable ? 'occurrence--not-applicable' : undefined}
          >
            <div className='block-editor__row'>
              <span className='block-editor__ordinal'>#{occurrence.ordinal}</span>
              <span className='block-editor__origin'>
                {occurrence.from_source ? 'Importada' : 'Añadida por revisión'}
              </span>
              {occurrence.not_applicable && (
                <span className='badge badge--no_aplica'>No aplica</span>
              )}
              {occurrence.comment && (
                <span className='block-editor__comment'>{occurrence.comment}</span>
              )}
            </div>

            <div className='block-editor__actions'>
              <button
                type='button'
                className='button button--ghost'
                disabled={disabled || index === 0}
                aria-label={`Subir ocurrencia ${occurrence.ordinal}`}
                onClick={() => move(occurrence.occurrence_id, -1)}
              >
                ↑
              </button>
              <button
                type='button'
                className='button button--ghost'
                disabled={disabled || index === occurrences.length - 1}
                aria-label={`Bajar ocurrencia ${occurrence.ordinal}`}
                onClick={() => move(occurrence.occurrence_id, 1)}
              >
                ↓
              </button>
              {occurrence.not_applicable ? (
                <button
                  type='button'
                  className='button button--ghost'
                  disabled={disabled}
                  onClick={() => ask('revertir_no_aplicable', occurrence.occurrence_id)}
                >
                  Revertir no aplica
                </button>
              ) : (
                <button
                  type='button'
                  className='button button--ghost'
                  disabled={disabled}
                  onClick={() => ask('marcar_no_aplicable', occurrence.occurrence_id)}
                >
                  Marcar no aplica
                </button>
              )}
              <button
                type='button'
                className='button button--ghost'
                disabled={disabled || occurrences.length < 2}
                onClick={() => ask('fusionar', occurrence.occurrence_id)}
              >
                Fusionar
              </button>
              <button
                type='button'
                className='button button--ghost'
                disabled={disabled}
                onClick={() => ask('eliminar', occurrence.occurrence_id)}
              >
                Eliminar
              </button>
            </div>

            {pending?.occurrenceId === occurrence.occurrence_id && (
              <div className='block-editor__confirm'>
                {pending.operation === 'eliminar' && occurrence.from_source && (
                  <p className='note'>
                    Esta ocurrencia procede de una fuente importada. Marcarla «no aplica»
                    la conserva; eliminarla retira el dato de origen del modelo.
                  </p>
                )}
                {pending.operation === 'fusionar' && (
                  <label className='field'>
                    <span className='field__label'>Fusionar con la ocurrencia</span>
                    <select
                      aria-label='Ocurrencia de destino'
                      value={mergeTarget}
                      onChange={(event) => setMergeTarget(event.target.value)}
                    >
                      <option value=''>Seleccione una ocurrencia…</option>
                      {occurrences
                        .filter((item) => item.occurrence_id !== occurrence.occurrence_id)
                        .map((item) => (
                          <option key={item.occurrence_id} value={item.occurrence_id}>
                            #{item.ordinal}
                          </option>
                        ))}
                    </select>
                  </label>
                )}
                <label className='field field--wide'>
                  <span className='field__label'>Motivo</span>
                  <input
                    type='text'
                    aria-label='Motivo de la operación'
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                  />
                </label>
                <div className='block-editor__confirm-actions'>
                  <button
                    type='button'
                    className='button button--primary'
                    disabled={
                      busy ||
                      comment.trim() === '' ||
                      (pending.operation === 'fusionar' && mergeTarget === '')
                    }
                    onClick={confirm}
                  >
                    {busy ? 'Aplicando…' : 'Confirmar'}
                  </button>
                  <button
                    type='button'
                    className='button button--ghost'
                    disabled={busy}
                    onClick={() => setPending(null)}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
