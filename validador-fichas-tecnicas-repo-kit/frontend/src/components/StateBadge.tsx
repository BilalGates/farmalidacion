import type { ReviewState, ValidationState } from '../api/types'
import { REVIEW_STATE_LABELS, VALIDATION_STATE_LABELS } from '../domain/vocabulary'

/**
 * Distintivo de estado.
 *
 * El color acompaña a la etiqueta, nunca la sustituye: un estado que solo se
 * distinguiese por el color sería ilegible para quien no lo perciba.
 */
export function ValidationBadge({ state }: { state: ValidationState }) {
  return (
    <span className={`badge badge--${state}`}>{VALIDATION_STATE_LABELS[state]}</span>
  )
}

export function ReviewBadge({ state }: { state: ReviewState }) {
  return <span className={`badge badge--${state}`}>{REVIEW_STATE_LABELS[state]}</span>
}

/** Distintivo de módulo todavía no desarrollado. */
export function SoonBadge({ label = 'Próximamente' }: { label?: string }) {
  return <span className='badge badge--soon'>{label}</span>
}
